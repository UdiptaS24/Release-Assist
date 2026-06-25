from pydantic import BaseModel, Field, EmailStr, HttpUrl, field_validator
from datetime import datetime, timezone, time
from typing import Literal, Dict, Any
import uuid
from dateutil import parser as date_parser
from zoneinfo import ZoneInfo

BUSINESS_TIMEZONE = ZoneInfo("Asia/Kolkata")

class ReleaseRequest(BaseModel):
    app_name: str = Field(min_length=2, max_length=100, description="Name of the application")
    version: str = Field(pattern=r'^\d+\.\d+\.\d+$', description="Version number in the format X.Y.Z")
    release_type: Literal["major", "minor", "patch"] = Field(description="Type of release: major, minor or patch")
    contact_email: EmailStr = Field(description="AppDev team contact email")
    repository_url: HttpUrl = Field(description="URL of the application's code repository")
    rollback_plan: str = Field(min_length=15, description="Brief description of the rollback plan to revert this deployment if it fails")

class ScheduleRequest(BaseModel):
    requested_start: datetime = Field(description="Requested deployment start time in ISO fornat")
    requested_end: datetime = Field("Requested deployment end time in ISO format")
    notify_contacts: list[EmailStr] = Field(default_factory=list, description="Contacts to notify about the scheduling decision")

    
    @field_validator("requested_start", "requested_end", mode="before")
    @classmethod
    def parse_flexible_datetime(cls, value: Any) -> datetime:
        if isinstance(value, datetime):
            dt = value
        else:
            try:
                dt = date_parser.parse(str(value), dayfirst=False)
            except Exception as exc:
                raise ValueError(
                    f"Could not parse datetime: '{value}'. Use formats like '2026-06-29 11:00', '29 Jun 2026 11AM', or ISO."
                ) from exc
            
        if dt.time() == time(0, 0):
            dt = dt.replace(hour=10, minute=0, second=0, microsecond=0)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=BUSINESS_TIMEZONE)

        return dt

    @field_validator("requested_end")
    @classmethod
    def validate_requested_end(cls, requested_end, info):
        requested_start = info.data.get("requested_start")
        if requested_start and requested_end <= requested_start:
            raise ValueError("requested_end must be after requested_start")
        return requested_end

class ReleaseRecord(ReleaseRequest):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8], description="Unique identifier of a release record")
    status: Literal["PENDING", "APPROVED", "NEEDS_REVIEW", "BLOCKED"] = Field(default="PENDING", description="Current status of the release automatically set by agent: PENDING, APPROVED, NEEDS_REVIEW, BLOCKED")
    created_at: datetime = Field(default_factory= lambda: datetime.now(timezone.utc), description="Timestamp when the release record was created")
    validation_report: Dict[str, Any] = Field(default_factory=dict, description="Detailed report of the repository analysis and validation results")
    change_snapshot: Dict[str, Any] = Field(default_factory=dict, description="Change snapshot showing difference between incoming version and last released version")
    schedule: Dict[str, Any] = Field(default_factory=dict,  description="Deployment scheduling result for this release")