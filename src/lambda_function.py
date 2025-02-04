import os
from itertools import batched
from urllib.parse import unquote_plus

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.data_classes import S3Event, event_source
from aws_lambda_powertools.utilities.typing import LambdaContext
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource
from mypy_boto3_s3 import S3Client
from mypy_boto3_s3.service_resource import S3ServiceResource

from backup_processor import BackupRestoreProcessor

tracer = Tracer()
logger = Logger()
metrics = Metrics(namespace="sms-backup-restore")


s3_client: S3Client = boto3.client("s3")
s3_resource: S3ServiceResource = boto3.resource("s3")
dynamodb_resource: DynamoDBServiceResource = boto3.resource("dynamodb")

DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "sms-backup-restore")


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
@event_source(data_class=S3Event)  # pylint: disable=no-value-for-parameter
def handler(event: S3Event, context: LambdaContext) -> None:
    """Lambda function to handle S3 events"""

    logger.info("Received event")
    bucket_name = event.bucket_name
    object_keys = [unquote_plus(record.s3.get_object.key) for record in event.records]

    logger.info("Received event for objects: {}".format(",".join(object_keys)))

    backup_processor = BackupRestoreProcessor(
        s3_client=s3_client, s3_resource=s3_resource
    )

    for object_key in object_keys:
        logger.info(f"Processing s3://{bucket_name}/{object_key}")
        processed_backup = backup_processor.process_backup(
            bucket_name=bucket_name, backup_key=object_key
        )
        logger.info(f"Processed backup located at s3://{bucket_name}/{object_key}")
        records = {r["id"]: r for r in processed_backup}

        batches = list(batched(records.values(), 25))
        for batch in batches:
            put_requests = [{"PutRequest": {"Item": e}} for e in batch]
            dynamodb_resource.batch_write_item(
                RequestItems={"sms-backup-restore": put_requests}
            )
