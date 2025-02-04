import json

#from moto import mock_dynamodb2
import boto3
import pytest

import lambda_function


@pytest.fixture
def lambda_context():
    with open("./tests/lambda_context.json", "r") as fp:
        context = json.load(fp)
    return context


@pytest.fixture
def sms_payload():
    with open("./tests/sms_payload.json", "r") as fp:
        event = json.load(fp)
    return event


@pytest.fixture
def calls_payload():
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


def test_calls(calls_payload, lambda_context):
    lambda_function.handler(event=calls_payload, context=lambda_context)


def test_sms(sms_payload, lambda_context):
    lambda_function.handler(event=sms_payload, context=lambda_context)
