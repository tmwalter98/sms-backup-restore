from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, root_validator


class CorrespondenceBase(BaseModel):
    timestamp: datetime = Field(validation_alias="date")
    readable_date: str = Field(exclude=True)
    contact_name: Optional[str]

    class Config:
        orm_mode = True

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
        return values


class SMS(CorrespondenceBase):
    protocol: int
    address: Optional[str]
    type: int
    subject: Optional[str]
    body: str
    toa: str = Field(exclude=True)
    sc_toa: str = Field(exclude=True)
    service_center: Optional[str]
    read: int
    status: int
    locked: int
    date_sent: Optional[int]
    sub_id: Optional[int]

    class Config:
        orm_mode = True


class MMS(CorrespondenceBase):
    rr: Optional[str]
    sub: Optional[str]
    ct_t: Optional[str]
    read_status: Optional[str]
    seen: Optional[int]
    msg_box: Optional[int]
    address: Optional[str]
    sub_cs: Optional[str]
    resp_st: Optional[str]
    retr_st: Optional[str]
    d_tm: Optional[str]
    text_only: int
    exp: Optional[str]
    locked: Optional[int]
    m_id: str
    st: Optional[str]
    retr_txt_cs: Optional[str]
    retr_txt: Optional[str]
    creator: Optional[str]
    date_sent: Optional[int]
    read: int
    m_size: Optional[str]
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

    class Config:
        orm_mode = True


class Call(CorrespondenceBase):
    number: Optional[str]
    duration: int
    type: int
    presentation: int
    subscription_id: Optional[str]
    subscription_component_name: Optional[str]
