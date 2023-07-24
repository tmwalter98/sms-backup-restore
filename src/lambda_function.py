import json
import os
import traceback
from typing import Any, Dict, List

import boto3
import sqlalchemy
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities import parameters
from aws_lambda_powertools.utilities.typing import LambdaContext
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker

import schemas
from models import (MMS, SMS, Address, Call, Part, metadata,
                    mms_address_association)
from utils import S3XMLTagIterator, replace_null_with_none, upload_s3

logger = Logger()

s3_client = boto3.client("s3")


@logger.inject_lambda_context
def handler(event: dict, context: LambdaContext):
    s3_event = event["Records"][0]["s3"]
    logger.info(event["Records"][0]["eventName"])
    bucket_name = s3_event["bucket"]["name"]
    object_key = s3_event["object"]["key"]

    # Perform your desired operations with the S3 object
    logger.info(f"Received event for object: s3://{bucket_name}/{object_key}")

    # Example: Get the content of the S3 object
    tag_iterator = S3XMLTagIterator(s3_client, bucket_name, object_key)

    secret_value: Dict[Any, Any] = parameters.get_secret(
        os.getenv("SECRET_NAME", "prod/sms-backup-restore/config"), transform="json"
    )

    engine = sqlalchemy.create_engine(
        secret_value["postgres_url"],
        echo=False,
        connect_args={"application_name": "sms-backup-restore"},
    )
    # metadata.drop_all(engine)
    metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    element_count: Dict[str, int] = {}
    skip = 0
    for elem in tag_iterator:
        if isinstance(skip, int) and tag_iterator.progress < skip:
            element_count.update({elem.tag: element_count.get(elem.tag, 0) + 1})
            progress, __ = tag_iterator.get_progress()
            if progress % 1000 == 0:
                print(progress, json.dumps(element_count))
            continue
        try:
            e_data = replace_null_with_none(dict(elem.attrib))
            element_count.update({elem.tag: element_count.get(elem.tag, 0) + 1})

            addresses: List[schemas.Address] = [
                schemas.Address.model_validate(elem.attrib)
                for elem in elem.findall(".//addr")
            ]
            if len(addresses) < 1:
                addresses.append(schemas.Address.model_validate(e_data))

            for address in addresses:
                address_stmt = insert(Address).values(**address.model_dump())
                session.execute(
                    address_stmt.on_conflict_do_update(
                        index_elements=[Address.address],
                        set_={"contact_name": address.contact_name},
                        where=(Address.contact_name.is_(None)),
                    ),
                )

            match elem.tag:
                case "call":
                    call = schemas.Call.model_validate(e_data).model_dump()
                    session.execute(
                        insert(Call).values(**call).on_conflict_do_nothing()
                    )
                case "sms":
                    sms = schemas.SMS.model_validate(e_data).model_dump()
                    session.execute(insert(SMS).values(**sms).on_conflict_do_nothing())
                case "mms":
                    mms_data = schemas.MMS.model_validate(e_data)
                    session.execute(
                        insert(MMS)
                        .values(**mms_data.model_dump())
                        .on_conflict_do_nothing()
                    )
                    for part in elem.findall(".//part"):
                        part_dict = replace_null_with_none(dict(part.attrib))
                        part_dict.update({"mms_id": mms_data.m_id})
                        part = schemas.Part.model_validate(part_dict)
                        if part.data:
                            url = upload_s3(
                                bucket_name=bucket_name,
                                data=part.data,
                                content_type=part.ct,
                            )
                            part.data_url = url
                        session.execute(
                            insert(Part)
                            .values(**part.model_dump())
                            .on_conflict_do_nothing()
                        )

                    for address in addresses:
                        insert_stmt = insert(mms_address_association).values(
                            mms_id=mms_data.m_id,
                            address=address.address,
                        )
                        session.execute(insert_stmt.on_conflict_do_nothing())
        except TypeError as exc:
            traceback.print_exception(type(exc), exc, exc.__traceback__)
            session.rollback()
            print(e_data, elem.tag)
        except Exception as exc:
            traceback.print_exception(type(exc), exc, exc.__traceback__)
            session.rollback()
            raise exc
        finally:
            progress, __ = tag_iterator.get_progress()
            if progress % 1000 == 0:
                print(progress, json.dumps(element_count))
                session.commit()
    session.commit()
