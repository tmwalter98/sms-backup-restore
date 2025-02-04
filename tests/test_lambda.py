import json
import uuid
from typing import Optional

# from moto import mock_dynamodb2
import boto3
import pytest

import lambda_function


@pytest.fixture
def lambda_context():
    """Generate lambda context with random request ID."""

    class LambdaContext:
        def __init__(
            self,
            function_name: str,
            memory_limit_in_mb: int,
            invoked_function_arn: str,
            request_id: Optional[str],
        ):
            self.function_name = function_name
            self.memory_limit_in_mb = memory_limit_in_mb
            self.invoked_function_arn = invoked_function_arn
            self.aws_request_id = request_id

        def get_remaining_time_in_millis(self) -> int:
            """Returns remaining time in milliseconds"""
            return 1000

    return LambdaContext(
        function_name="sms-backup-restore",
        memory_limit_in_mb=512,
        invoked_function_arn="arn:aws:lambda:us-east-1:093896728566:function:sms-backup-restore",
        request_id=uuid.uuid4(),
    )


@pytest.fixture
def sms_event():
    with open("./tests/sms_payload.json", "r") as fp:
        event = json.load(fp)
    return event


@pytest.fixture
def calls_event():
    with open("./tests/calls_payload.json", "r") as fp:
        event = json.load(fp)
    return event


# @pytest.yield_fixture(scope="function")
# def dynamo_db_fixture():
#     mock_dynamodb2().start()
#     dynamodb_client = boto3.client("dynamodb", region_name="eu-east-2")
#     dynamodb_resource = boto3.resource("dynamodb", region_name="eu-east-2")

#     # Create the table
#     dynamodb_resource.create_table(
#         TableName="sms-backup-restore",
#         KeySchema=[
#             {"AttributeName": "id", "KeyType": "HASH"},  # Partition_key
#             {"AttributeName": "timestamp", "KeyType": "RANGE"},  # Sort_key
#         ],
#         AttributeDefinitions=[
#             {"AttributeName": "id", "AttributeType": "N"},
#             {"AttributeName": "timestamp", "AttributeType": "S"},
#         ],
#         BillingMode="PAY_PER_REQUEST",
#     )
#     yield dynamodb_client, dynamodb_resource

#     mock_dynamodb2().stop()


def test_calls(calls_event, lambda_context):
    lambda_function.handler(event=calls_event, context=lambda_context)


def test_sms(sms_event, lambda_context):
    lambda_function.handler(event=sms_event, context=lambda_context)
