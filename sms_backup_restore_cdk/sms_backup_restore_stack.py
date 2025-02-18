from aws_cdk import CfnOutput, Duration, RemovalPolicy, Size, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from constructs import Construct


class SMSBackupRestoreECR(Construct):
    """ECR Registry Configuration for SMSBackupRestoreStack"""

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope=scope, id=id)
        stack = Stack.of(self)
        # account = self.node.get_context('aws:cdk:toolkit:default-account')
        # region = self.node.get_context('aws:cdk:toolkit:default-region')

        self.ecr_repository = ecr.Repository(
            scope=scope,
            id="ECRRepository",
            repository_name=stack.stack_name,
            lifecycle_registry_id=stack.account,
            lifecycle_rules=[
                ecr.LifecycleRule(
                    rule_priority=1,
                    description="Remove images that are not latest",
                    tag_status=ecr.TagStatus.ANY,
                    max_image_count=3,
                )
            ],
        )
        self.ecr_repository.add_to_resource_policy(
            iam.PolicyStatement(
                sid="LambdaECRImageRetrievalPolicy",
                principals=[iam.ServicePrincipal("lambda.amazonaws.com")],
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                ],
                conditions={
                    "StringLike": {
                        "aws:sourceArn": f"arn:aws:lambda:{stack.region}:{stack.account}:function:*"
                    }
                },
            )
        )


class SMSBackupRestoreS3(Construct):
    """S3 Bucket Configuration for SMSBackupRestoreStack"""

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope=scope, id=id)
        stack = Stack.of(self)

        self.s3_bucket = s3.Bucket(
            scope=self,
            id="S3Bucket",
            bucket_name=stack.stack_name,
            encryption=s3.BucketEncryption.KMS_MANAGED,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            event_bridge_enabled=True,
        )
        self.event_rule = events.Rule(
            scope=self,
            id="EventBridgeEventRuleS3ObjectCreated",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                region=[stack.region],
                detail_type=["Object Created"],
                detail={
                    "bucket": {"name": [self.s3_bucket.bucket_name]},
                    "object": {"key": [{"suffix": {"equals-ignore-case": ".xml"}}]},
                },
            ),
        )

    @property
    def access_policy_document(self) -> iam.PolicyDocument:
        """Returns Policy Document for Lambda S3 Access"""
        lambda_access_s3_policy_document = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    sid="AllowLambdaToAccessBucket",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "s3:PutObject",
                        "s3:GetObject",
                        "s3:GetObjectAttributes",
                        "s3:GetObjectTagging",
                        "s3:PutObjectTagging",
                        "s3:GetObjectVersion",
                    ],
                    resources=[
                        self.s3_bucket.bucket_arn,
                        self.s3_bucket.arn_for_objects("*"),
                    ],
                )
            ]
        )
        return lambda_access_s3_policy_document


class SMSBackupRestoreLogGroup(Construct):
    """Log Group Configuration for SMSBackupRestoreStack"""

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope=scope, id=id)
        stack = Stack.of(self)

        self.log_group = logs.CfnLogGroup(
            scope=self,
            id="LogsLogGroup",
            log_group_name=f"/aws/lambda/{stack.stack_name}",
            retention_in_days=180,
        )

    @property
    def access_policy_document(self) -> iam.PolicyDocument:
        """Returns Policy Document for Log Stream and Log Events Access"""
        lambda_create_put_log_policy_document = iam.PolicyDocument(
            statements=[
                # Policy Document for Log Group Creation
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["logs:CreateLogGroup"],
                    resources=[self.log_group.attr_arn],
                ),
                # Policy Document for Log Group Logging
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    resources=[self.log_group.attr_arn],
                ),
            ]
        )
        return lambda_create_put_log_policy_document


class SMSBackupRestoreDynamoDB(Construct):
    """DynamoDB Configuration for SMSBackupRestoreStack"""

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope=scope, id=id)
        stack = Stack.of(self)

        self.dynamodb_table = dynamodb.TableV2(
            scope=self,
            id="DynamoDBTable",
            table_name=stack.stack_name,
            partition_key=dynamodb.Attribute(
                name="id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp", type=dynamodb.AttributeType.NUMBER
            ),
            billing=dynamodb.Billing.on_demand(
                max_read_request_units=1000,
                max_write_request_units=1000,
            ),
            removal_policy=RemovalPolicy.RETAIN,
        )

    @property
    def access_policy_document(self) -> iam.PolicyDocument:
        """Returns Policy Document for DynamoDB Access."""

        # Policy Document for Lambda DynamoDB Access
        lambda_access_dynamodb_policy_document = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    sid="DynamoDBAccess",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "dynamodb:BatchGetItem",
                        "dynamodb:BatchWriteItem",
                        "dynamodb:UpdateTimeToLive",
                        "dynamodb:ConditionCheckItem",
                        "dynamodb:PutItem",
                        "dynamodb:DeleteItem",
                        "dynamodb:PartiQLUpdate",
                        "dynamodb:Scan",
                        "dynamodb:ListTagsOfResource",
                        "dynamodb:Query",
                        "dynamodb:DescribeStream",
                        "dynamodb:UpdateItem",
                        "dynamodb:DescribeTimeToLive",
                        "dynamodb:PartiQLSelect",
                        "dynamodb:DescribeTable",
                        "dynamodb:GetShardIterator",
                        "dynamodb:PartiQLInsert",
                        "dynamodb:GetItem",
                        "dynamodb:GetResourcePolicy",
                        "dynamodb:UpdateTable",
                        "dynamodb:GetRecords",
                        "dynamodb:PartiQLDelete",
                    ],
                    resources=[
                        self.dynamodb_table.table_arn,
                    ],
                ),
                iam.PolicyStatement(
                    sid="DynamoDBTablesInfoAccess",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "dynamodb:ListTables",
                        "dynamodb:DescribeReservedCapacity",
                        "dynamodb:GetAbacStatus",
                        "dynamodb:DescribeLimits",
                        "dynamodb:DescribeEndpoints",
                        "dynamodb:ListStreams",
                    ],
                    resources=["*"],
                ),
            ]
        )
        return lambda_access_dynamodb_policy_document


class SMSBackupRestoreStack(Stack):
    """AWS CDK Stack for sms-backup-restore processing resources."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.tags.set_tag(
            key=self.stack_name, value=" ", apply_to_launched_instances=True
        )

        ecr_repository_node = SMSBackupRestoreECR(scope=self, id="SMSBackupRestoreECR")
        s3_bucket_node = SMSBackupRestoreS3(scope=self, id="SMSBackupRestoreS3")
        log_group_node = SMSBackupRestoreLogGroup(
            scope=self, id="SMSBackupRestoreLogGroup"
        )
        dynamodb_node = SMSBackupRestoreDynamoDB(
            scope=self, id="SMSBackupRestoreDynamoDB"
        )

        lambda_iam_role = iam.Role(
            scope=self,
            id="IAMRoleLambdaExecutionRole",
            path="/service-role/",
            role_name="sms-backup-restore",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            max_session_duration=Duration.hours(1),
            inline_policies={
                "LambdaAccessS3": s3_bucket_node.access_policy_document,
                "LambdaAccessDynamoDB": dynamodb_node.access_policy_document,
                "LambdaCreatePutLog": log_group_node.access_policy_document,
            },
        )

        lambda_function = _lambda.DockerImageFunction(
            scope=self,
            id="BackupProcessingLambdaFunction",
            function_name=self.stack_name,
            description="SMS Backup Restore backup processing lambda",
            role=lambda_iam_role,
            architecture=_lambda.Architecture.ARM_64,
            memory_size=8192,
            ephemeral_storage_size=Size.mebibytes(1024),
            application_log_level_v2=_lambda.ApplicationLogLevel.INFO,
            code=_lambda.DockerImageCode.from_ecr(ecr_repository_node.ecr_repository),
            environment={"DYNAMODB_TABLE": dynamodb_node.dynamodb_table.table_name},
            timeout=Duration.minutes(15),
            tracing=_lambda.Tracing.PASS_THROUGH,
            logging_format=_lambda.LoggingFormat.JSON,
            log_group=log_group_node.log_group,
        )

        s3_bucket_node.event_rule.add_target(
            targets.LambdaFunction(handler=lambda_function, retry_attempts=3)
        )

        CfnOutput(
            self,
            id="SMSBackupRestoreBucketArn",
            value=s3_bucket_node.s3_bucket.bucket_arn,
            description="S3 Bucket ARN",
        )
        CfnOutput(
            self,
            id="SMSBackupRestoreDynamoDBTableArn",
            value=dynamodb_node.dynamodb_table.table_arn,
            description="DynamoDB Table ARN",
        )
        CfnOutput(
            self,
            id="SMSBackupRestoreLambdaArn",
            value=lambda_function.function_arn,
            description="Lambda Function ARN",
        )
