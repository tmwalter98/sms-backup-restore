from aws_cdk import Duration, RemovalPolicy, Size, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from constructs import Construct


class SMSBackupRestoreStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.tags.set_tag(
            key=self.stack_name, value=" ", apply_to_launched_instances=True
        )

        lambda_timeout = Duration.minutes(10)

        dynamodb_table = dynamodb.TableV2(
            scope=self,
            id="DynamoDBTable",
            table_name=self.stack_name,
            partition_key=dynamodb.Attribute(
                name="id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp", type=dynamodb.AttributeType.NUMBER
            ),
            billing=dynamodb.Billing.provisioned(
                read_capacity=dynamodb.Capacity.autoscaled(max_capacity=1000),
                write_capacity=dynamodb.Capacity.autoscaled(max_capacity=1000),
            ),
            removal_policy=RemovalPolicy.RETAIN,
        )

        s3_bucket = s3.Bucket(
            scope=self,
            id="S3Bucket",
            bucket_name=self.stack_name,
            encryption=s3.BucketEncryption.KMS_MANAGED,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            event_bridge_enabled=True,
        )

        ecr_repository = ecr.Repository(
            scope=self,
            id="ECRRepository",
            repository_name=self.stack_name,
            lifecycle_registry_id=self.account,
            lifecycle_rules=[
                ecr.LifecycleRule(
                    rule_priority=1,
                    description="Remove images that are not latest",
                    tag_status=ecr.TagStatus.UNTAGGED,
                    max_image_age=Duration.days(1),
                )
            ],
        )
        ecr_repository.add_to_resource_policy(
            iam.PolicyStatement(
                sid="LambdaECRImageRetrievalPolicy",
                principals=[iam.ServicePrincipal("lambda.amazonaws.com")],
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:SetRepositoryPolicy",
                    "ecr:DeleteRepositoryPolicy",
                    "ecr:GetRepositoryPolicy",
                ],
                conditions={
                    "StringLike": {
                        "aws:sourceArn": f"arn:aws:lambda:us-east-1:{self.account}:function:*"
                    }
                },
            )
        )

        # Policy Document for Lambda S3 Access
        lambda_access_s3_policy_document = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    sid="VisualEditor0",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "s3:PutObject",
                        "s3:GetObject",
                        "s3:GetObjectAttributes",
                        "s3:GetObjectTagging",
                        "s3:PutObjectTagging",
                        "s3:GetObjectVersion",
                    ],
                    resources=["arn:aws:s3:::sms-backup-restore/*"],
                )
            ]
        )

        # Policy Document for Lambda DynamoDB Access
        lambda_access_dynamodb_policy_document = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    sid="VisualEditor0",
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
                        dynamodb_table.table_arn,
                        f"arn:aws:dynamodb:*:{self.account}:table/sms-backup-restore/index/*",
                        f"arn:aws:dynamodb:*:{self.account}:table/sms-backup-restore/stream/*",
                    ],
                ),
                iam.PolicyStatement(
                    sid="VisualEditor1",
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

        # Policy Document for Lambda Log Group Creation
        lambda_create_log_group_policy_document = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["logs:CreateLogGroup"],
                    resources=[f"arn:aws:logs:us-east-1:{self.account}:*"],
                )
            ]
        )

        # Policy Document for Lambda Log Stream and Log Events
        lambda_create_put_log_policy_document = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                    resources=[
                        f"arn:aws:logs:us-east-1:{self.account}:log-group:/aws/lambda/sms-backup-restore:*"
                    ],
                )
            ]
        )

        lambda_iam_role = iam.Role(
            scope=self,
            id="IAMRoleLambdaExecutionRole",
            path="/service-role/",
            role_name="sms-backup-restore",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            max_session_duration=Duration.hours(1),
            inline_policies={
                "LambdaAccessS3": lambda_access_s3_policy_document,
                "LambdaAccessDynamoDB": lambda_access_dynamodb_policy_document,
                "LambdaCreateLogGroup": lambda_create_log_group_policy_document,
                "LambdaCreatePutLog": lambda_create_put_log_policy_document,
            },
        )

        log_group = logs.CfnLogGroup(
            scope=self,
            id="LogsLogGroup",
            log_group_name="/aws/lambda/sms-backup-restore",
            retention_in_days=180,
        )

        lambda_function = _lambda.DockerImageFunction(
            scope=self,
            id="BackupProcessingLambdaFunction",
            function_name=self.stack_name,
            description="SMS Backup Restore backup processing lambda",
            role=lambda_iam_role,
            architecture=_lambda.Architecture.ARM_64,
            memory_size=512,
            ephemeral_storage_size=Size.mebibytes(1024),
            application_log_level_v2=_lambda.ApplicationLogLevel.INFO,
            code=_lambda.DockerImageCode.from_ecr(ecr_repository),
            environment={"DYNAMODB_TABLE": dynamodb_table.table_name},
            timeout=lambda_timeout,
            tracing=_lambda.Tracing.PASS_THROUGH,
            logging_format=_lambda.LoggingFormat.JSON,
            log_group=log_group,
        )

        event_rule = events.Rule(
            scope=self,
            id="EventBridgeEventRuleS3ObjectCreated",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                region=["us-east-1"],
                detail_type=["Object Created"],
                detail={
                    "bucket": {"name": [s3_bucket.bucket_name]},
                    "object": {"key": [{"suffix": {"equals-ignore-case": ".xml"}}]},
                },
            ),
        )

        event_rule.add_target(
            targets.LambdaFunction(handler=lambda_function, retry_attempts=3)
        )
