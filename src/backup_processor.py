import base64
from hashlib import sha256
from typing import Any, Dict, List

import numpy as np
from lxml import etree
from lxml.etree import Element
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource
from mypy_boto3_s3.client import S3Client
from mypy_boto3_s3.service_resource import Bucket, S3ServiceResource
from smart_open import s3 as smart_open_s3

from schemas import MMS, SMS, Call, CorrespondenceBase
from utils import replace_null_with_none

BUCKET_NAME = "sms-backup-restore"


class BackupRestoreProcessor:
    """Class to handle streaming and processing of backup from S3"""

    def __init__(
        self, s3_client: S3ServiceResource, s3_resource: DynamoDBServiceResource
    ) -> None:
        self._s3_client: S3Client = s3_client
        self._s3_resource: DynamoDBServiceResource = s3_resource

    def tag_object(
        self, bucket_name: str, object_key: str, tags: Dict[str, Any]
    ) -> None:
        """
        Adds key-value pair tags to an object in an S3 bucket.

        Args:
            bucket_name (str): The name of the S3 bucket.
            object_key (str): The key of the object to tag.
            tags (Dict[str, Any]): A dictionary of tags where keys are tag names
                                and values are tag values.

        Returns:
            None
        """
        tag_set = [{"Key": k, "Value": str(v)} for k, v in tags.items()]
        self._s3_client.put_object_tagging(
            Bucket=bucket_name,
            Key=object_key,
            Tagging={"TagSet": tag_set},
        )

    def upload_part_s3(
        self, bucket_name: str, part_data: str, part_content_type: str
    ) -> str:
        """
        Uploads a part to an S3 bucket if it does not already exist.

        Args:
            bucket_name (str): The name of the S3 bucket.
            part_data (str): Base64-encoded string representing the part data.
            part_content_type (str): The content type of the part being uploaded.

        Returns:
            str: The SHA-256 hash of the decoded part data, used as the object key.
        """
        data = base64.b64decode(part_data)
        data_sha256 = sha256(data).hexdigest()
        key = f"parts/{data_sha256}"
        try:
            self._s3_client.head_object(Bucket=bucket_name, Key=key)
        except self._s3_client.exceptions.ClientError:
            self._s3_client.put_object(
                Bucket=bucket_name, Key=key, ContentType=part_content_type
            )
        return data_sha256

    def process_tag(self, bucket: Bucket, elem: Element) -> CorrespondenceBase:
        """Processes XML tag.  Uploading object data for MMS parts."""
        e_data = replace_null_with_none(dict(elem.attrib))

        match elem.tag:
            case "call":
                return Call.model_validate(e_data)
            case "sms":
                return SMS.model_validate(e_data)
            case "mms":
                parts = [
                    replace_null_with_none(dict(part.attrib))
                    for part in elem.findall(".//part")
                ]
                parts1 = []
                for part in parts:
                    if part["ct"] not in ["application/smil", "text/plain"] and bool(
                        part["data"]
                    ):
                        object_hash = self.upload_part_s3(
                            bucket_name=bucket.name,
                            part_data=part["data"],
                            part_content_type=part["ct"],
                        )
                        part["data"] = object_hash
                    parts1.append(part)

                addrs = [
                    replace_null_with_none(dict(addr.attrib))
                    for addr in elem.findall(".//addr")
                ]
                e_data.update({"parts": parts1, "addrs": addrs})

                return MMS.model_validate(e_data)
            case _:
                pass

    def process_backup(self, bucket_name: str, backup_key: str) -> List[Dict[str, Any]]:
        """Streams .xml backup file from S3 and uploads records to S3."""
        fin: smart_open_s3.Reader = smart_open_s3.open(
            bucket_name,
            backup_key,
            mode="rb",
            defer_seek=True,
            client=self._s3_client,
        )
        seekable_reader = fin._raw_reader

        # Creates document parser with the buffered file
        context = etree.iterparse(seekable_reader, recover=True, encoding="utf-8")

        # Skips to the children of interest
        context = iter(context)
        next(context)

        bucket: Bucket = self._s3_resource.Bucket(bucket_name)
        tag_data = {}
        for _, elem in context:
            tag_parsed = self.process_tag(elem=elem, bucket=bucket)
            if isinstance(tag_parsed, CorrespondenceBase):
                elem_processed = {"id": tag_parsed.hash(), **tag_parsed.model_dump()}

                tags = tag_data.get(elem.tag, [])
                tags.append(elem_processed)
                tag_data.update({elem.tag: tags})

        fin.close()
        return list(np.concatenate(list(tag_data.values())))
