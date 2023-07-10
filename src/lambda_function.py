import json
import os

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker

import schemas
from models import SMS, Call, metadata
from utils import S3XMLTagIterator, get_db_url

logger = Logger()

s3_client = boto3.client("s3")
rds_client = boto3.client('rds')
secrets_manager_client = boto3.client('secretsmanager')

 
@logger.inject_lambda_context
def handler(event: dict, context: LambdaContext):
    s3_event = event['Records'][0]['s3']
    bucket_name = s3_event['bucket']['name']
    object_key = s3_event['object']['key']
    
    # Perform your desired operations with the S3 object
    print(f"Received event for object: s3://{bucket_name}/{object_key}")
    
    # Example: Get the content of the S3 object
    tag_iterator = S3XMLTagIterator(s3_client, bucket_name, object_key)
    
    # url = get_db_url(os.environ['RDS_SECRET_ID'], os.environ['RDS_INSTANCE_IDENTIFIER'])
    url = os.environ['DATABASE_URL']

    engine = create_engine(os.environ['DATABASE_URL'])
    metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    element_count = {}
    for elem in tag_iterator:
        stmt = None
        match elem.tag:
            count = element_count.get(elem.tag, 0)
            case "call":
                call = schemas.Call(**elem.attrib)
                stmt = insert(Call).values(**call.dict()).on_conflict_do_nothing()
                count += 1
            case "sms":
                sms = schemas.SMS(**elem.attrib)
                stmt = insert(SMS).values(**sms.dict()).on_conflict_do_nothing()
                count += 1
            element_count.update({elem.tag: count})
        try:
            if stmt != None: 
                session.execute(stmt)
        except Exception as exc:
            logger.exception(str(exc))
        if sum(list(element_count.values())) % 100 == 0:
            print(json.dumps(element_count))

    """ s3_client.put_object_tagging(
        Bucket=bucket_name,
        Key=object_key,
        Tagging={
            'TagSet': [
                {
                    'Key': 'processed',
                    'Value': 'true'
                },
            ]
        },
    ) """