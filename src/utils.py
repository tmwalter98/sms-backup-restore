import base64
import copy
import hashlib
import io
import logging
import traceback
from typing import Tuple

from botocore.exceptions import ClientError
from lxml import etree
from minio import Minio
from mypy_boto3_s3.service_resource import Bucket


def upload_s3(bucket: Bucket, data: str, content_type: str) -> str:
    data_bytes = base64.b64decode(data)
    sha256_hash = hashlib.sha256()
    sha256_hash.update(data_bytes)
    hash_value = sha256_hash.hexdigest()

    object_key = f"mms_parts/{hash_value}"
    try:
        bucket.Object(object_key).last_modified
        s3_client.head_object(Bucket=bucket_name, Key=object_key)
        print(f"{object_key} already exists")
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "404":
            res = s3_client.put_object(
                Body=base64.b64decode(data),
                Bucket=bucket_name,
                Key=object_key,
                ContentType=content_type,
            )
            print(res)
    return f"s3://{bucket_name}/mms_parts/{hash_value}"


def upload_s3_minio(
    s3_client: Minio,
    bucket_name: str,
    prefix: str = None,
    data: str = None,
    content_type: str = None,
) -> str:
    data_bytes = base64.b64decode(data)
    sha256_hash = hashlib.sha256()
    sha256_hash.update(data_bytes)
    hash_value = sha256_hash.hexdigest()

    object_key = "/".join([prefix, hash_value]) if prefix else hash_value
    print(object_key)
    try:
        s3_client.stat_object(bucket_name, object_key)
        print(f"{object_key} already exists")
    except Exception as exc:
        logging.error(traceback.format_exception(type(exc), exc, exc.__traceback__))
        data_bytes = base64.b64decode(data)
        res = s3_client.put_object(
            bucket_name,
            object_key,
            io.BytesIO(data_bytes),
            len(data_bytes),
            content_type,
        )
        print(res.etag, res.location, res.last_modified)
        return res.location
    return f"s3://{bucket_name}/mms_parts/{hash_value}"


def replace_null_with_none(data: dict) -> dict:
    if isinstance(data, dict):
        return {k: replace_null_with_none(v) for k, v in data.items()}
    elif isinstance(data, list) and not isinstance(data, str):
        return [replace_null_with_none(item) for item in data]
    elif data == "null":
        return None
    elif data == "":
        return None
    else:
        return data


class S3XMLTagIteratorMinio:
    def __init__(self, s3_client: Minio, bucket_name: str, object_key: str):
        self.bucket_name = bucket_name
        self.object_key = object_key
        self.s3 = s3_client
        self.streaming_body = None
        self.context = None
        self.root = None
        self.progress = 0

    def __iter__(self):
        response = self.s3.get_object(
            self.bucket_name,
            self.object_name,
        )
        self.streaming_body = response["Body"]

        # Create an iterator for the XML streaming body
        self.context = etree.iterparse(
            self.streaming_body,
            events=("start", "end"),
            recover=True,
            encoding="utf-8",
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
