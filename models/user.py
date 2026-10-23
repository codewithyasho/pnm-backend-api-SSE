from sqlmodel import SQLModel, Field
from pydantic import EmailStr
from typing import Optional
from datetime import datetime, timezone
from enum import Enum


# ENUM for user enquiry status PENDING, COMPLETED
class EnquiryStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class UserTable(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str = Field(index=True)
    corporate_email: EmailStr = Field(index=True)
    phone_number: str = Field(index=True)
    company_name: str = Field(index=True)
    employee_count: Optional[str] = Field(default=None)
    primary_interest: Optional[str] = Field(default=None)
    specific_requirements: Optional[str] = Field(default=None)
    status: EnquiryStatus = Field(default=EnquiryStatus.PENDING)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class UserRequestModel(SQLModel):
    id: Optional[int] = Field(default=None)
    full_name: str = Field(min_length=3)
    corporate_email: EmailStr
    phone_number: str
    company_name: str = Field(min_length=3)
    employee_count: Optional[str] = Field(default=None)
    primary_interest: Optional[str] = Field(default=None)
    specific_requirements: Optional[str] = Field(default=None)
    status: EnquiryStatus = Field(default=EnquiryStatus.PENDING)
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class UserResponseModel(SQLModel):
    status: str = Field(default="success")
    message: str


class ListUsers(SQLModel):
    status: str = Field(default="success")
    count: int
    users: list[UserRequestModel]


class UpdateEnquiryStatus(SQLModel):
    status: EnquiryStatus
