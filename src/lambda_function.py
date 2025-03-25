import os
import re
from collections import Counter
from itertools import batched

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.data_classes import (
    S3EventBridgeNotificationEvent,
    event_source,
)
from aws_lambda_powertools.utilities.typing import LambdaContext
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource
from mypy_boto3_s3 import S3Client
from mypy_boto3_s3.service_resource import S3ServiceResource

from backup_processor import BackupRestoreProcessor

# Initialize AWS Lambda Powertools components
tracer = Tracer()
logger = Logger()
metrics = Metrics(namespace="sms-backup-restore")

# Initialize AWS clients
s3_client: S3Client = boto3.client("s3")
s3_resource: S3ServiceResource = boto3.resource("s3")
dynamodb_resource: DynamoDBServiceResource = boto3.resource("dynamodb")

DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "sms-backup-restore")
ENV = os.environ.get("ENV", "prod")


def process_s3_backup(event: S3EventBridgeNotificationEvent):
    """Process S3 backup event"""

    bucket_name = event.detail.bucket.name
    object_key = event.detail.object.key
    backup_type_patt = re.compile(r"\b(calls|sms)\b")
    backup_type = backup_type_patt.search(object_key).group(0)

    logger.info(f"Received event for object: {object_key} in {bucket_name}")

    metrics.add_metric(name="ProcessBackup", unit=MetricUnit.Count, value=1)
    metrics.add_metric(name=backup_type, unit=MetricUnit.Count, value=1)

    backup_processor = BackupRestoreProcessor(
        s3_client=s3_client, s3_resource=s3_resource
    )

    logger.info(f"Processing s3://{bucket_name}/{object_key}")
    backup_processor.tag_object(
        bucket_name=bucket_name,
        object_key=object_key,
        tags={"processed": "STARTED"},
    )
    processed_backup = backup_processor.process_backup(
        bucket_name=bucket_name, backup_key=object_key
    )
    logger.info(f"Processed backup located at s3://{bucket_name}/{object_key}")
    records = {r["id"]: r for r in processed_backup}

    logger.info(f"Writing {len(records)} records")
    batches = list(batched(records.values(), 25))
    for batch in batches:
        print(batch)
        put_requests = [{"PutRequest": {"Item": e}} for e in batch]
        dynamodb_resource.batch_write_item(
            RequestItems={"sms-backup-restore": put_requests}
        )

    tags = {"processed": "COMPLETE", "record_count": len(records)}
    backup_processor.tag_object(
        bucket_name=bucket_name, object_key=object_key, tags=tags
    )

    record_counts = Counter([r["record_type"] for _, r in records.items()])
    for record_type, count in record_counts.items():
        metrics.add_metric(
            name=f"RecordType/{record_type}",
            unit=MetricUnit.Count,
            value=count,
        )


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
@event_source(data_class=S3EventBridgeNotificationEvent)
def handler(event: S3EventBridgeNotificationEvent, context: LambdaContext) -> None:
    """Lambda function to handle S3 events"""

    metrics.add_dimension(name="environment", value=ENV)

    process_s3_backup(event)
