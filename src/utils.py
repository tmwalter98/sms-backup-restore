import copy
from lxml import etree
import json


rds_client = boto3.client('rds')
secrets_manager_client = boto3.client('secretsmanager')

def get_db_url(secret_id: str, db_instance_identifier: str):
    response = secrets_manager_client.get_secret_value(SecretId=secret_id)
    rds_credentials = json.loads(response['SecretString'])
    username, password = rds_credentials['username'], rds_credentials['password']

    response = rds_client.describe_db_instances()
    filter = lambda x: x['Endpoint'] if x['DBInstanceIdentifier'] == db_instance_identifier else None
    endpoint = map(filter, response['DBInstances']).__iter__().__next__()
    address, port = endpoint['Address'], endpoint['Port']

    return f'postgresql+psycopg2://{username}:{password}@{address}:{port}/postgres'


class S3XMLTagIterator:
    def __init__(self, s3_client, bucket_name: str, object_key: str):
        self.bucket_name = bucket_name
        self.object_key = object_key
        self.s3 = s3_client
        self.streaming_body = None
        self.context = None
        self.root = None

    def __iter__(self):
        response = self.s3.get_object(Bucket=self.bucket_name, Key=self.object_key)
        self.streaming_body = response["Body"]

        # Create an iterator for the XML streaming body
        self.context = etree.iterparse(
            self.streaming_body, events=("start", "end"), recover=True
        )

        # Disable loading of elements into memory
        self.context = iter(self.context)
        _, self.root = next(self.context)  # Get the root element
        return self

    def __next__(self):
        for event, elem in self.context:
            if event == "end":
                tag = elem.tag
                if tag in ["call", "sms", "mms"]:
                    # Clear the element from memory
                    elem_copy = copy.deepcopy(elem)
                    elem.clear()
                    return elem_copy
        # All tags processed, close the streaming body
        self.streaming_body.close()
        raise StopIteration

