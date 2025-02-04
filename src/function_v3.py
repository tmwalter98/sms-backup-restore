import base64
import hashlib
import json
import os
import pickle
import sys
import time
import traceback
from typing import Any, Dict, List

import boto3
import sqlalchemy
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities import parameters
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from kafka import KafkaProducer
from lxml import etree
from minio import Minio
from minio.error import S3Error
from smart_open import open as sopen
from smart_open import s3 as smart_open_s3
from smart_open.s3 import Reader
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker

import schemas_v2 as schemas
from schemas_v2 import MMS, SMS, Address, Call, Part
from utils import (S3XMLTagIterator, replace_null_with_none, upload_s3,
                   upload_s3_minio)

logger = Logger()


SOURCE_URL = "s3://sms-backup-restore/sms-20231224050040.xml"
ARCHIVE_BUCKET = "sms-backup-restore"
SMS_MEDIA_BUCKET = "sms-media-backup"

S3_ENDPOINT_URL = "http://192.168.10.76:8080"
AWS_ACCESS_KEY_ID = "X5L771469X3A9G0TRM40"
AWS_SECRET_ACCESS_KEY = "Pc0oPlAWdFpkJKEyrxgFKaB9qqBkVV1D75tLBdhr"

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT_URL,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    verify=False,
)
s3_resource = boto3.resource(
    "s3",
    endpoint_url=S3_ENDPOINT_URL,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    verify=False,
)

archive_bucket = s3_resource.Bucket(ARCHIVE_BUCKET)
media_bucket = s3_resource.Bucket(SMS_MEDIA_BUCKET)

cts: Dict[str, int] = {}


def process_element(elem: etree.ElementBase) -> List:
    e_data = replace_null_with_none(dict(elem.attrib))

    element_data = None
    match elem.tag:
        case "call":
            print(json.dumps(dict(elem.attrib), indent=4, default=str))
            exit()
            element_data = (Call.model_validate(e_data),)
        case "sms":
            element_data = (SMS.model_validate(e_data),)
        case "mms":
            mms = MMS.model_validate(e_data)
            addrs = [
                Address.model_validate(addr.attrib) for addr in elem.findall(".//addr")
            ]

            parts = []
            for part_e in elem.findall(".//part"):
                ct = part_e.attrib["ct"]
                cts.update({ct: cts.get(ct, 0) + 1})

                part_dict = replace_null_with_none(dict(part_e.attrib))
                part_dict.update({"mms_id": mms.m_id})
                part = schemas.Part.model_validate(part_dict)

                if part.data:
                    data_bytes = base64.b64decode(part.data)
                    sha256_hash = hashlib.sha256()
                    sha256_hash.update(data_bytes)
                    hash_value = sha256_hash.hexdigest()

                    obj = media_bucket.Object(hash_value)

                    try:
                        media_bucket.Object(hash_value).content_length
                    except ClientError:
                        pass
                    finally:
                        logger.info(
                            f"Uploading object {obj.key} of {len(data_bytes)} bytes"
                        )
                        obj.put(
                            Body=data_bytes,
                            ContentType=part.ct,
                        )
                        logger.info(
                            f"Done uploading object {obj.key} of {len(data_bytes)} bytes"
                        )

                    part.data_url = f"s3://{SMS_MEDIA_BUCKET}/{obj.key}"
                parts.append(part)

            mms.addr = addrs
            mms.part = parts
            element_data = mms

    return element_data


def handler(event: dict, context: dict):
    bucket_name, object_key = ARCHIVE_BUCKET, "sms-20231126050039.xml"
    logger.info(f"Received event for object: s3://{bucket_name}/{object_key}")

    kafka_producer = KafkaProducer(
        bootstrap_servers="127.0.0.1:19092",
    )
    future = kafka_producer.send("sms_meta", value=b"hey yo")
    future.get(60)

    kafka_producer = KafkaProducer(
        bootstrap_servers="127.0.0.1:19092",
        # value_serializer=lambda v: v.model_dump_json(),
    )

    # Open a connection to the object that is streamable
    fin: smart_open_s3.Reader = smart_open_s3.open(
        bucket_name, object_key, mode="rb", defer_seek=True, client=s3
    )
    seekable_reader = fin._raw_reader

    # Creates document parser with the buffered file
    context = etree.iterparse(seekable_reader, recover=True, encoding="utf-8")

    # Skips to the children of interest
    context = iter(context)
    next(context)

    element_count: Dict[str, int] = {}
    for event, elem in context:
        element_count.update({elem.tag: element_count.get(elem.tag, 0) + 1})

        elem_processed = sum(element_count.values())

        sms_meta_data = []
        if not elem_processed % 1000:
            print(
                f"({seekable_reader._position} / {seekable_reader._content_length}) [{elem_processed}] elements"
            )
            print(seekable_reader._content_length, seekable_reader._position)

        element_results: List[schemas.CorrespondenceBase] = process_element(elem)

        # sms_meta_data.extend(element_results)

        # for element in element_results:
        #    kafka_producer.send(
        #        "sms_meta", value=element.model_dump_json().encode("utf-8")
        #    )
        # future = kafka_producer.send('foobar', b'another_message')
        # result = future.get(timeout=60)

    fin.close()

    """ s3_boto3.put_object_tagging(
        Bucket=bucket_name,
        Key=object_key,
        Tagging={
            "TagSet": [
                {"Key": "processed", "Value": "true"},
            ]
        },
    ) """


if __name__ == "__main__":
    handler(event={}, context={})
