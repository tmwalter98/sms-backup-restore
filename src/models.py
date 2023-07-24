import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (UUID, Boolean, Column, DateTime, Enum, ForeignKey,
                        Integer, String, Table, event)
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy_utils import URLType
from sqlalchemy_utils.types.phone_number import PhoneNumberType

# Define the SQLAlchemy model
Base = declarative_base()
metadata = Base.metadata


class Common(Base):
    __abstract__ = True

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True)


class ReadStatus(enum.IntEnum):
    UNREAD = 0
    READ = 1


class MessageType(enum.IntEnum):
    RECEIVED = 1
    SENT = 2
    DRAFT = 3
    OUTBOX = 4
    FAILED = 5
    QUEUED = 6


class StatusEnum(enum.IntEnum):
    NONE = -1
    COMPLETE = 0
    PENDING = 32
    FAILED = 64
    UNKNOWN = 131072


class SMS(Common):
    __tablename__ = "sms"

    timestamp = Column("timestamp", DateTime(timezone=True), primary_key=True)
    address: PhoneNumberType = Column(
        PhoneNumberType(),
        ForeignKey("address.address", ondelete="CASCADE"),
        primary_key=True,
    )
    type = Column(Enum(MessageType, native_enum=False), primary_key=True)
    subject = Column(String)
    body = Column(String)
    protocol = Column(Integer)
    contact_name = Column(String)
    status = Column(Enum(StatusEnum, native_enum=False))
    service_center = Column(String)
    read = Column(Enum(ReadStatus, native_enum=False))
    locked = Column(Boolean)
    date_sent = Column(DateTime(timezone=True))
    sub_id = Column(Integer)


class MessageBox(enum.IntEnum):
    Received = 1
    Sent = 2
    Draft = 3
    Outbox = 4


class AddressTypeEnum(enum.IntEnum):
    BCC = 129
    CC = 130
    TO = 151
    FROM = 137


mms_address_association = Table(
    "mms_address_association",
    Base.metadata,
    Column(
        "mms_id", String, ForeignKey("mms.m_id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "address",
        PhoneNumberType,
        ForeignKey("address.address", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("type", Enum(AddressTypeEnum, native_enum=False)),
    Column("charset", Integer),
)


class Address(Common):
    __tablename__ = "address"

    address: Mapped[str] = mapped_column(PhoneNumberType(), primary_key=True)
    contact_name: Optional[str] = Column(String)


class MMS(Common):
    __tablename__ = "mms"

    m_id: Mapped[str] = mapped_column(String, primary_key=True)
    timestamp = Column("timestamp", DateTime(timezone=True))
    address: Column[List[PhoneNumberType]] = Column(postgresql.ARRAY(PhoneNumberType))
    creator = Column(String)
    ct_cls = Column(String)
    ct_l = Column(String)
    ct_t = Column(String)
    d_rpt = Column(Integer)
    d_tm = Column(String)
    date_sent = Column(DateTime(timezone=True))
    exp = Column(Integer)
    from_address = Column(String)
    locked = Column(Boolean)
    m_cls = Column(String)
    m_size = Column(Integer)
    m_type = Column(Integer)
    message_classifier = Column(String)
    msg_box = Column(Integer)
    pri = Column(Integer)
    read = Column(Integer)
    read_status = Column(Boolean, default=False)
    resp_st = Column(Integer)
    resp_txt = Column(String)
    retr_st = Column(String)
    retr_txt = Column(String)
    retr_txt_cs = Column(String)
    rpt_a = Column(String)
    rr = Column(Integer)
    seen = Column(Integer)
    st = Column(String)
    sub = Column(String)
    sub_cs = Column(String)
    sub_id = Column(Integer)
    text_only = Column(Boolean)
    tr_id = Column(String)
    v = Column(Integer)

    parts = relationship("Part", back_populates="mms", passive_deletes=True)
    addresses = relationship(
        "Address",
        secondary=mms_address_association,
        backref="mms_messages",
        passive_deletes=True,
    )


class Part(Common):
    __tablename__ = "part"

    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True)
    mms_id = Column(String, ForeignKey("mms.m_id", ondelete="CASCADE"))
    seq = Column(Integer)
    ct = Column(String)
    chset = Column(Integer)
    cd = Column(String)
    cid = Column(String)
    cl = Column(String)
    ctt_s = Column(String)
    ctt_t = Column(String)
    text = Column(String)
    name = Column(String)
    data_url = Column(URLType)

    mms = relationship("MMS", back_populates="parts")


class Call(Common):
    __tablename__ = "calls"

    timestamp = Column("timestamp", DateTime(timezone=True), primary_key=True)
    address: PhoneNumberType = Column(
        PhoneNumberType(),
        ForeignKey("address.address", ondelete="CASCADE"),
        primary_key=True,
    )
    duration = Column(Integer)
    type = Column(Integer)
    presentation = Column(Integer)
    subscription_id = Column(String)
    post_dial_digits = Column(String)
    subscription_component_name = Column(String)
