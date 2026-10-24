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


# FOR WEBSOCKET

# --- LIVE CHAT MODELS ---

class SenderRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class ChatSession(SQLModel, table=True):
    """Stores each visitor's chat identity and secret session_token (No password needed!)."""

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )
    corporate_email: EmailStr = Field(
        index=True,
        unique=True
    )
    full_name: str
    session_token: str  # Auto-generated UUID from FE and saved in visitor's localStorage

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_active_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class ChatMessage(SQLModel, table=True):
    """Stores every chat message (1-on-1 and Admin Broadcasts) in SQLite."""

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )
    # Which user thread this message belongs to ("ALL" if it's an Admin global broadcast)
    user_email: str = Field(index=True)
    user_name: str

    sender_role: SenderRole  # "user" or "admin"

    message: str = Field(
        min_length=1,
        max_length=2000
    )

    is_broadcast: bool = Field(default=False)
    is_read_by_admin: bool = Field(default=False)   # like of unread msg

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class IncomingChatPayload(SQLModel):
    """Pydantic validator for incoming WebSocket JSON messages."""

    to_email: Optional[str] = Field(
        default=None)  # Used by Admin (None = Broadcast to ALL)

    message: str = Field(min_length=1, max_length=2000)
