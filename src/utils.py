import base64
import copy
import hashlib
from typing import Tuple

import boto3
from botocore.exceptions import ClientError
from lxml import etree

secrets_manager_client = boto3.client("secretsmanager")
s3_client = boto3.client("s3")


def upload_s3(bucket_name: str, data: str, content_type: str) -> str:
    data_bytes = base64.b64decode(data)
    sha256_hash = hashlib.sha256()
    sha256_hash.update(data_bytes)
    hash_value = sha256_hash.hexdigest()

    object_key = f"mms_parts/{hash_value}"
    try:
        s3_client.head_object(Bucket=bucket_name, Key=object_key)
        print(f"{object_key} already exists")
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "404":
            s3_client.put_object(
                Body=base64.b64decode(data),
                Bucket=bucket_name,
                Key=object_key,
                ContentType=content_type,
            )
    return f"s3://{bucket_name}/mms_parts/{hash_value}"


def replace_null_with_none(data: dict) -> dict:
    if isinstance(data, dict):
        return {k: replace_null_with_none(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_null_with_none(item) for item in data]
    elif data == "null":
        return None
    else:
        return data


class S3XMLTagIterator:
    def __init__(self, s3_client, bucket_name: str, object_key: str):
        self.bucket_name = bucket_name
        self.object_key = object_key
        self.s3 = s3_client
        self.streaming_body = None
        self.context = None
        self.root = None
        self.progress = 0

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
                    self.progress += 1
                    return elem_copy
        # All tags processed, close the streaming body
        self.streaming_body.close()
        raise StopIteration

    def get_progress(self) -> Tuple[int, int]:
        total = 0 if self.root is None else int(self.root.attrib["count"])
        return (self.progress, total)

    def resume_to(self, progress_pos: int) -> None:
        while progress_pos < self.progress:
            if self.progress % 1000 == 0:
                print("skipping... at ", self.progress)
            if progress_pos * 100 / self.progress == 0:
                print("skipping... at ", self.progress)
            self.__next__()
