import re
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Dict, FrozenSet, List, Optional

import phonenumbers
from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    PlainSerializer,
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)
from typing_extensions import Annotated

StringSerializedDatetime = Annotated[
    datetime, PlainSerializer(lambda x: x.isoformat(), return_type=str)
]


def replace_unknown_contact_name_null(v: Optional[str]) -> Optional[str]:
    """Replace contact name `(Unknown)` with `Null`."""

    match = re.match(r"^(?!\(Unknown\)$).+$", v) if isinstance(v, str) else None
    return match.group() if match else None


def phone_number_validator(v: str) -> str:
    """Attempt to validate phone number or format."""
    try:
        phome_numbers = phonenumbers.parse(v, region="US")
        v = phonenumbers.format_number(
            phome_numbers, phonenumbers.PhoneNumberFormat.E164
        )
    except phonenumbers.phonenumberutil.NumberParseException:
        v = v.strip() if isinstance(v, str) else None
    return v


def ensure_phone_number_sorted_list(value: Any) -> List[str]:
    if isinstance(value, str):
        return sorted(
            [phone_number_validator(v) for v in value.split("~") if len(v) > 0]
        )
    elif isinstance(value, list):
        return sorted([phone_number_validator(v) for v in value])
    else:
        return []


class HashableBaseModel(BaseModel):
    """Base model that enforces hashability."""

    def hash(self) -> str:
        """Computes a SHA-256 hash of the model's data."""
        raise NotImplementedError()


class CorrespondenceBase(HashableBaseModel):
    """Base model for correspondence records like SMS, MMS, and Calls."""

    timestamp: StringSerializedDatetime = Field(validation_alias="date")
    address: Annotated[FrozenSet[str], BeforeValidator(ensure_phone_number_sorted_list)]

    @model_validator(mode="before")
    @classmethod
    def set_timestamp(cls, values: Dict[str, Any]):
        """Parses timestamp values from the input data."""
        tz = timezone.utc
        timestamp = datetime(1970, 1, 1, tzinfo=tz)

        try:
            timestamp = datetime.fromtimestamp(float(values["date"]))
        except (OSError, KeyError, ValueError):
            try:
                timestamp = datetime.strptime(
                    values["readable_date"], "%b %d, %Y %I:%M:%S %p"
                ).replace(tzinfo=tz)
            except Exception:
                pass
        finally:
            values["timestamp"] = timestamp

        try:
            values.update(
                {
                    "date_sent": datetime.fromtimestamp(
                        int(values["date_sent"])
                    ).replace(tzinfo=tz)
                }
            )
        except Exception:
            values.update({"date_sent": timestamp})
        finally:
            values["date_sent"] = (
                timestamp
                if values["date_sent"]
                <= datetime(1970, 1, 1).replace(tzinfo=tz)
                < timestamp
                else values["date_sent"]
            )
        return values

    @computed_field
    @property
    def record_type(self) -> str:
        """Defines the record type, must be implemented in subclasses."""
        raise NotImplementedError("Subclass needs to define this.")

    class Config:
        from_attributes = True
        extra = "ignore"
        frozen = True

    @field_serializer("address", when_used="always")
    def serialize_address_frozenset(self, address: FrozenSet[str]) -> List[str]:
        """Returns address FrozenSet as list"""
        return list(address)


class SMS(CorrespondenceBase):
    """Represents an SMS message."""

    protocol: int
    contact_name: Optional[str]
    type: int
    subject: Optional[str]
    body: str
    toa: Optional[str] = Field(exclude=True)
    sc_toa: Optional[str] = Field(exclude=True)
    service_center: Optional[str]
    read: int
    status: int
    locked: int
    date_sent: Optional[StringSerializedDatetime]
    sub_id: Optional[int]

    @computed_field
    @property
    def record_type(self) -> str:
        return "SMS"

    class Config:
        """SMS Validator Config"""

        from_attributes = True

    @field_validator("contact_name", mode="before")
    @classmethod
    def set_unknown_contact_name_null(cls, v: str):
        """Replace contact name `(Unknown)` with `Null`."""
        return replace_unknown_contact_name_null(v)

    def hash(self):
        hash_values = type(self), self.address, self.timestamp, self.type, self.body
        hash_string = "".join([str(v) for v in hash_values])
        return sha256(hash_string.encode("utf-8")).hexdigest()


class Part(HashableBaseModel):
    """Represents an MMS message Part."""

    # mms_id: Optional[str] = None
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
    data: Optional[str] = Field(default=None)

    class Config:
        """MMS Parts Validator Config"""

        from_attributes = True
        frozen = True

    def hash(self):
        d = self.data if bool(self.data) else self.text
        hash_values = type(self), self.seq, d
        hash_string = "".join([str(v) for v in hash_values])
        return sha256(hash_string.encode("utf-8")).hexdigest()

    def __lt__(self, obj):
        if self.seq == obj.seq:
            hash_self = hash(self.data) if bool(self.data) else hash(self.text)
            hash_obj = hash(self.data) if bool(self.data) else hash(self.text)
            return hash_self < hash_obj
        return (self.seq) < (obj.seq)

    def __gt__(self, obj):
        if self.seq == obj.seq:
            hash_self = hash(self.data) if bool(self.data) else hash(self.text)
            hash_obj = hash(self.data) if bool(self.data) else hash(self.text)
            return hash_self > hash_obj
        return (self.seq) > (obj.seq)

    def __le__(self, obj):
        if self.seq == obj.seq:
            hash_self = hash(self.data) if bool(self.data) else hash(self.text)
            hash_obj = hash(self.data) if bool(self.data) else hash(self.text)
            return hash_self <= hash_obj
        return (self.seq) <= (obj.seq)

    def __ge__(self, obj):
        if self.seq == obj.seq:
            hash_self = hash(self.data) if bool(self.data) else hash(self.text)
            hash_obj = hash(self.data) if bool(self.data) else hash(self.text)
            return hash_self >= hash_obj
        return (self.seq) >= (obj.seq)

    def __eq__(self, obj):
        if self.seq == obj.seq:
            hash_self = hash(self.data) if bool(self.data) else hash(self.text)
            hash_obj = hash(self.data) if bool(self.data) else hash(self.text)
            return hash_self == hash_obj
        return (self.seq) == (obj.seq)


class MMS(CorrespondenceBase):
    """Validator for MMS messages"""

    rr: Optional[int]
    sub: Optional[str]
    ct_t: Optional[str]
    read_status: Optional[bool]
    seen: Optional[int]
    msg_box: Optional[int]
    sub_cs: Optional[str]
    resp_st: Optional[int]
    retr_st: Optional[str]
    d_tm: Optional[str]
    text_only: int
    exp: Optional[int]
    locked: Optional[int]
    m_id: Optional[str]
    st: Optional[str]
    retr_txt_cs: Optional[str]
    retr_txt: Optional[str]
    creator: Optional[str]
    date_sent: Optional[StringSerializedDatetime]
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
    parts: FrozenSet[Part] = Field(default=[])

    @computed_field
    @property
    def record_type(self) -> str:
        return "MMS"

    class Config:
        """MMS Validator Config"""

        from_attributes = True

    @field_validator("parts", mode="after")
    @classmethod
    def sorted_set_parts(cls, parts: List[Part]) -> List[Part]:
        """Ensures `parts` are sorted"""
        return sorted(parts)

    @field_serializer("parts", when_used="always")
    def serialize_parts_frozenset(self, parts: FrozenSet[str]) -> List[str]:
        """Return parts FrozenSet as a list"""
        return list(parts)

    def hash(self):
        hash_values = (
            type(self),
            "~".join(self.address),
            self.timestamp,
            self.msg_box,
            self.m_id,
            self.m_type,
        )
        hash_string = "".join([str(v) for v in hash_values])
        return sha256(hash_string.encode("utf-8")).hexdigest()


class Address(HashableBaseModel):
    """Validator for Addresses"""

    address: str
    contact_name: Optional[str] = Field(default=None)
    type: Optional[int] = Field(default=None, exclude=True)
    charset: Optional[int] = Field(default=None, exclude=True)

    @field_validator("contact_name", mode="before")
    @classmethod
    def set_unknown_contact_name_null(cls, v: str):
        """Replace contact name `(Unknown)` with `Null`."""
        return replace_unknown_contact_name_null(v)

    @field_validator("address", mode="before")
    @classmethod
    def validate_address(cls, v: str) -> List[str]:
        """Replace contact name `(Unknown)` with `Null`."""
        return phone_number_validator(v)

    class Config:
        """Address Validator Config"""

        from_attributes = True
        extra = "ignore"

    def hash(self):
        hash_values = (type(self), self.address, self.type)
        hash_string = "".join([str(v) for v in hash_values])
        return sha256(hash_string.encode("utf-8")).hexdigest()


class Call(CorrespondenceBase):
    """Validator for Phone Calls"""

    contact_name: Optional[str] = Field(exclude=True)
    duration: int
    type: int
    presentation: int
    subscription_id: Optional[str]
    subscription_component_name: Optional[str]

    @computed_field
    @property
    def record_type(self) -> str:
        return "Call"

    class Config:
        """Call Validator Config"""

        extra = "ignore"

    @field_validator("contact_name", mode="before")
    @classmethod
    def set_unknown_contact_name_null(cls, v: str):
        """Replace contact name `(Unknown)` with `Null`."""
        return replace_unknown_contact_name_null(v)

    @model_validator(mode="before")
    @classmethod
    def set_address_from_alias(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Use `number` if key in data, else use `address`."""
        data["address"] = data["number"] if "number" in data else data["address"]
        return data

    def hash(self):
        hash_values = type(self), self.address, self.timestamp, self.duration, self.type
        hash_string = "".join([str(v) for v in hash_values])
        return sha256(hash_string.encode("utf-8")).hexdigest()
