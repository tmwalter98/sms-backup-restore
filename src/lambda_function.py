import boto3
import os
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from models import metadata, Call
from utils import S3XMLTagIterator, get_db_url
import schemas


s3 = boto3.client("s3")
rds_client = boto3.client('rds')
secrets_manager_client = boto3.client('secretsmanager')


def handler(event: dict, context: dict):
    s3_event = event['Records'][0]['s3']
    bucket_name = s3_event['bucket']['name']
    object_key = s3_event['object']['key']
    
    # Perform your desired operations with the S3 object
    print(f"Received event for object: s3://{bucket_name}/{object_key}")
    
    # Example: Get the content of the S3 object
    tag_iterator = S3XMLTagIterator(s3, bucket_name, object_key)
    
    # url = get_db_url(os.environ['RDS_SECRET_ID'], os.environ['RDS_INSTANCE_IDENTIFIER'])
    url = os.environ['DATABASE_URL']

    engine = create_engine(os.environ['DATABASE_URL'])
    metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    for elem in tag_iterator:
        data = dict(elem.attrib.items())

        try:
            record = None
            match elem.tag:
                case "call":
                    call = schemas.Call(**elem.attrib)
                    record = Call(**call.dict())
            
            session.add(record)
            session.commit()
        except Exception as exc:
            print(exc)
            
