import json
import random
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import phonenumbers
from pydantic import (BaseModel, Field, GetCoreSchemaHandler, field_validator,
                      model_validator, root_validator)
from pydantic_core import CoreSchema, core_schema


class PhoneNumber(str):
    """Phone Number Pydantic type, using google's phonenumbers"""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(cls, handler(str))

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: str):
        # Remove spaces
        v = v.strip().replace(" ", "")

        try:
            pn = phonenumbers.parse(v, region="US")
            v = cls(phonenumbers.format_number(pn, phonenumbers.PhoneNumberFormat.E164))
        except phonenumbers.phonenumberutil.NumberParseException:
            print(v)

        return v


class CorrespondenceBase(BaseModel):
    timestamp: datetime = Field(validation_alias="date")

    class Config:
        from_attributes = True
        extra = "ignore"

    @root_validator(pre=True)
    def set_timestamp(cls, values):
        try:
            values.update({"timestamp": datetime.fromtimestamp(int(values["date"]))})
        except ValueError:
            values.update(
                {
                    "timestamp": datetime.strptime(
                        values["readable_date"], "%b %d, %Y %I:%M:%S %p"
                    )
                }
            )
        finally:
            values["timestamp"] = (
                values["timestamp"]
                if values["timestamp"] >= datetime(1970, 1, 1)
                else datetime(1970, 1, 1)
            )

        try:
            values.update(
                {"date_sent": datetime.fromtimestamp(int(values["date_sent"]))}
            )
        except Exception:
            values.update({"date_sent": values["timestamp"]})
        finally:
            values["date_sent"] = (
                values["timestamp"]
                if values["date_sent"] <= datetime(1970, 1, 1)
                else values["date_sent"]
            )
        return values


class SMS(CorrespondenceBase):
    """Validator for SMS messages"""

    protocol: int
    address: Optional[PhoneNumber]
    contact_name: Optional[str]
    type: int
    subject: Optional[str]
    body: str
    toa: Optional[str] = Field(exclude=True)
    sc_toa: Optional[str] = Field(exclude=True)
    service_center: Optional[PhoneNumber]
    read: int
    status: int
    locked: int
    date_sent: Optional[datetime]
    sub_id: Optional[int]

    class Config:
        """SMS Validator Config"""

        from_attributes = True


class Part(BaseModel):
    """Validator for MMS parts"""

    mms_id: Optional[str]
    name: Optional[str]
    seq: Optional[int]
    ct: Optional[str] = None
    chset: Optional[int]
    cd: Optional[str]
    fn: Optional[str] = Field(exclude=True, default=None)
    cid: Optional[str]
    cl: Optional[str]
    ctt_s: Optional[str]
    ctt_t: Optional[str]
    text: Optional[str]
    data_url: Optional[str] = None
    data: Optional[bytes] = Field(exclude=True, default=None)

    class Config:
        """MMS Parts Validator Config"""

        from_attributes = True


class MMS(CorrespondenceBase):
    """Validator for MMS messages"""

    rr: Optional[int]
    sub: Optional[str]
    ct_t: Optional[str]
    read_status: Optional[bool]
    seen: Optional[int]
    msg_box: Optional[int]
    address: List[PhoneNumber]
    sub_cs: Optional[str]
    resp_st: Optional[int]
    retr_st: Optional[str]
    d_tm: Optional[str]
    text_only: int
    exp: Optional[int]
    locked: Optional[int]
    m_id: str
    st: Optional[str]
    retr_txt_cs: Optional[str]
    retr_txt: Optional[str]
    creator: Optional[str]
    date_sent: Optional[datetime]
    read: int
    m_size: Optional[int]
    rpt_a: Optional[str]
    ct_cls: Optional[str]
    pri: Optional[int]
    sub_id: Optional[int]
    tr_id: Optional[str]
    resp_txt: Optional[str]
    ct_l: Optional[str]
    m_cls: Optional[str]
    d_rpt: Optional[int]
    v: Optional[int]
    m_type: Optional[int]
    parts: List[Part] = Field(default=[], exclude=True)

    @model_validator(mode="before")
    def set_m_id_if_dne(cls, data) -> Dict[str, Any]:
        data["m_id"] = data["tr_id"] if data["m_id"] is None else data["m_id"]
        data["m_id"] = (
            f"assigned/{uuid.uuid4().hex.upper()}"
            if data["m_id"] is None
            else data["m_id"]
        )
        data["address"] = [PhoneNumber(num) for num in data["address"].split("~")]
        return data

    class Config:
        """MMS Validator Config"""

        from_attributes = True


class Address(BaseModel):
    """Validator for Addresses"""

    address: PhoneNumber
    contact_name: Optional[str] = Field(default=None)
    type: Optional[int] = Field(default=None, exclude=True)
    charset: Optional[int] = Field(default=None, exclude=True)

    @field_validator("contact_name", mode="before")
    def set_unknown_contact_name_null(cls, v):
        if isinstance(v, str):
            return None if "(Unknown)" in v else v
        return v

    class Config:
        """Address Validator Config"""

        from_attributes = True
        extra = "ignore"


class Call(CorrespondenceBase):
    """Validator for Phone Calls"""

    number: Optional[PhoneNumber]
    contact_name: Optional[str] = Field(exclude=True)
    duration: int
    type: int
    presentation: int
    subscription_id: Optional[str]
    subscription_component_name: Optional[str]
