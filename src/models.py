from typing import Optional
import uuid
from sqlalchemy import (
    UUID,
    ForeignKey,
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    Enum,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy_utils.types.phone_number import PhoneNumberType
from sqlalchemy_utils import URLType
from sqlalchemy import event


# Define the SQLAlchemy model
Base = declarative_base()
metadata = Base.metadata


class Common(Base):
    __abstract__ = True

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True)
    contact_name = Column(String)


class SMS(Common):
    __tablename__ = "sms"

    protocol = Column(Integer)
    timestamp = Column("timestamp", DateTime(timezone=True), primary_key=True)
    address = Column(String, primary_key=True)
    type = Column(Integer)
    subject = Column(String)
    body = Column(String)
    status = Column(Integer)
    service_center = Column(String)
    read = Column(Boolean)
    locked = Column(Boolean)
    date_sent = Column(String)
    readable_date = Column(String)
    sub_id = Column(Integer)


class ReadStatus(Enum):
    Read = 1
    Unread = 0


class MessageBox(Enum):
    Received = 1
    Sent = 2
    Draft = 3
    Outbox = 4


class MMS(Common):
    __tablename__ = "mms"

    timestamp = Column("timestamp", DateTime(timezone=True))
    address = Column(String)
    creator = Column(String)
    ct_cls: Optional[str] = Column(String)
    ct_l: Optional[str] = Column(String)
    ct_t = Column(String)
    d_rpt = Column(Integer)
    d_tm: Optional[str] = Column(String)
    date_sent = Column(Integer)
    date_sent = Column(String)
    exp = Column(Integer)
    from_address = Column(String)
    locked = Column(Boolean)
    m_cls = Column(String)
    m_id = Column(String, primary_key=True)
    m_size = Column(Integer)
    m_type = Column(Integer)
    message_classifier = Column(String)
    msg_box = Column(Integer)
    pri = Column(Integer)
    read = Column(Integer)
    read_status = Column(Boolean, default=False)
    readable_date = Column(String)
    resp_st = Column(Integer)
    resp_txt: Optional[str] = Column(String)
    retr_st: Optional[str] = Column(String)
    retr_txt: Optional[str] = Column(String)
    retr_txt_cs: Optional[str] = Column(String)
    rpt_a: Optional[str] = Column(String)
    rr = Column(Integer)
    seen = Column(Boolean)
    st: Optional[str] = Column(String)
    sub: Optional[str] = Column(String)
    sub_cs: Optional[str] = Column(String)
    sub_id = Column(Integer)
    text_only = Column(Boolean)
    tr_id = Column(String)
    v = Column(Integer)

    parts = relationship("Part", back_populates="mms")
    addresses = relationship("Address", back_populates="mms")


class Part(Common):
    __tablename__ = "part"

    mms_id = Column(String, ForeignKey("mms.m_id"))
    name = Column(String)
    seq: Optional[int] = Column(Integer)
    ct: Optional[int] = Column(String)
    name: Optional[str] = Column(String)
    chset: Optional[int] = Column(Integer)
    cd: Optional[str] = Column(String)
    fn: Optional[str] = Column(String)
    cid: Optional[str] = Column(String)
    cl: Optional[str] = Column(String)
    ctt_s: Optional[str] = Column(String)
    ctt_t: Optional[str] = Column(String)
    text: Optional[str] = Column(String)
    file_name: Optional[str] = Column(String)
    data_url: Optional[str] = Column(URLType, primary_key=True)

    mms = relationship("MMS", back_populates="parts")


class AddressType(Enum):
    BCC = 129
    CC = 130
    TO = 151
    FROM = 137


class Address(Common):
    __tablename__ = "address"

    mms_id = Column(String, ForeignKey("mms.m_id"))
    address: str = Column(PhoneNumberType(), primary_key=True)
    type = Column(Integer)
    charset: Optional[int] = Column(String)
    mms = relationship("MMS", back_populates="addresses")


class Call(Common):
    __tablename__ = "calls"

    timestamp = Column("timestamp", DateTime(timezone=True), primary_key=True)
    number = Column(PhoneNumberType(), primary_key=True)
    duration = Column(Integer)
    type = Column(Integer)
    presentation = Column(Integer)
    subscription_id = Column(String)
    post_dial_digits = Column(String)
    subscription_component_name = Column(String)
    readable_date = Column(String)
