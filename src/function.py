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
from lxml import etree
from minio import Minio
from minio.error import S3Error
from smart_open import open as sopen
from smart_open import s3 as smart_open_s3
from smart_open.s3 import Reader
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker

import schemas
from models import MMS, SMS, Address, Call, Part, metadata, mms_address_association
from utils import S3XMLTagIterator, replace_null_with_none, upload_s3, upload_s3_minio

logger = Logger()


POSTGRES_URL = "postgresql://postgres:tcZ1NVYW#SAY>Uo.Hkg+5#c6!y63@database-1.c13nswndmmkb.us-east-1.rds.amazonaws.com/postgres"
SOURCE_URL = "s3://sms-backup-restore/sms-20231203050040.xml"
IMAGE_BUCKET = "sms-backup-restore"
IMAGE_BUCKET = "ceph-bkt-33693fba-8470-4240-804d-cba2fe53efda"

S3_ENDPOINT_URL = "http://192.168.10.32:80"
AWS_ACCESS_KEY_ID = "42NI2HEA18LK97U5TIDC"  # "ZiNqL46UkMhpT8lN8DVg"
AWS_SECRET_ACCESS_KEY = "SZWfNJrklGKj7jryUNUnquy1U0mKlhpDYIpu5Jn2"  # "j22I8zT2mMsOgnktBq5rTEi86YlUCTD3lKQLkpwt"

s3_boto3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT_URL,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    verify=False,
)

s3 = boto3.resource(
    "s3",
    endpoint_url=S3_ENDPOINT_URL,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    verify=False,
)
image_bucket = s3.Bucket(IMAGE_BUCKET)


s3_client = Minio(
    "192.168.10.32:80",
    access_key=AWS_ACCESS_KEY_ID,
    secret_key=AWS_SECRET_ACCESS_KEY,
    cert_check=False,
)


# Prepare Postgres
engine = sqlalchemy.create_engine(
    POSTGRES_URL,
    echo=False,
    connect_args={"application_name": "sms-backup-restore"},
)
metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

cts: Dict[str, int] = {}


def process_element(elem: etree.ElementBase) -> None:
    e_data = replace_null_with_none(dict(elem.attrib))

    match elem.tag:
        case "call":
            call = schemas.Call.model_validate(e_data).model_dump()
            stmt = insert(Call).values(**call).on_conflict_do_nothing()

            try:
                session.execute(stmt)
            except IntegrityError:
                session.rollback()
                address = schemas.Address.model_validate(e_data).model_dump()
                session.execute(
                    insert(Address).values(**address).on_conflict_do_nothing()
                )
                session.execute(stmt)

        case "sms":
            sms = schemas.SMS.model_validate(e_data).model_dump()
            stmt = insert(SMS).values(**sms).on_conflict_do_nothing()

            try:
                session.execute(stmt)
            except IntegrityError:
                session.rollback()
                address = schemas.Address.model_validate(e_data).model_dump()
                session.execute(
                    insert(Address).values(**address).on_conflict_do_nothing()
                )
                session.execute(stmt)

        case "mms":
            addresses: List[schemas.Address] = [
                schemas.Address.model_validate(elem.attrib)
                for elem in elem.findall(".//addr")
            ]
            for address in addresses:
                address_stmt = insert(Address).values(**address.model_dump())
                session.execute(
                    address_stmt.on_conflict_do_update(
                        index_elements=[Address.address],
                        set_={"contact_name": address.contact_name},
                        where=(Address.contact_name.is_(None)),
                    ),
                )

            mms_data = schemas.MMS.model_validate(e_data)
            session.execute(
                insert(MMS).values(**mms_data.model_dump()).on_conflict_do_nothing()
            )
            for address in addresses:
                insert_stmt = insert(mms_address_association).values(
                    mms_id=mms_data.m_id,
                    address=address.address,
                )
                session.execute(insert_stmt.on_conflict_do_nothing())

            for part_e in elem.findall(".//part"):
                ct = part_e.attrib["ct"]
                cts.update({ct: cts.get(ct, 0) + 1})

                part_dict = replace_null_with_none(dict(part_e.attrib))
                part_dict.update({"mms_id": mms_data.m_id})
                part = schemas.Part.model_validate(part_dict)

                if part.data:
                    data_bytes = base64.b64decode(part.data)
                    sha256_hash = hashlib.sha256()
                    sha256_hash.update(data_bytes)
                    hash_value = sha256_hash.hexdigest()

                    obj = image_bucket.Object(hash_value)

                    try:
                        image_bucket.Object(hash_value).content_length
                    except ClientError as exc:
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

                    part.data_url = f"s3://{image_bucket.name}/{obj.key}"
                session.execute(
                    insert(Part).values(**part.model_dump()).on_conflict_do_nothing()
                )


def handler(event: dict, context: dict):
    s3_event = event["Records"][0]["s3"]
    logger.info(event["Records"][0]["eventName"])
    bucket_name = s3_event["bucket"]["name"]
    object_key = s3_event["object"]["key"]

    logger.info(f"Received event for object: s3://{bucket_name}/{object_key}")

    # Open a connection to the object that is streamable
    fin: smart_open_s3.Reader = smart_open_s3.open(
        bucket_name, object_key, mode="rb", defer_seek=True, client=s3_boto3
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

        if not elem_processed % 1000:
            print(
                f"{ 100*seekable_reader._position / seekable_reader._content_length}% ({seekable_reader._position} / {seekable_reader._content_length}) [{elem_processed}] elements"
            )

        # if elem.tag in ["sms"]:
        #    continue

        try:
            process_element(elem)
        except SQLAlchemyError as exc:
            session.rollback()
            logger.error(traceback.format_exception(type(exc), exc, exc.__traceback__))
            break
        except (TypeError, Exception) as exc:
            logger.error(traceback.format_exception(type(exc), exc, exc.__traceback__))
        finally:
            session.commit()

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


with open("./src/example_payload copy.json", "r") as fp:
    event = json.load(fp)
handler(event, {})
