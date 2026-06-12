from pydantic import BaseModel, Field, EmailStr, HttpUrl
from datetime import datetime, timezone
from typing import Literal
import uuid

class ReleaseRequest(BaseModel):
    app_name: str = Field(min_length=2, max_length=100, description="Name of the application")
    version: str = Field(pattern=r'^\d+\.\d+\.\d+$', description="Version number in the format X.Y.Z")
    release_type: Literal["major", "minor", "patch", "hotfix"] = Field(description="Type of release: major, minor or patch")
    contact_email: EmailStr = Field(description="AppDev team contact email")
    repository_url: HttpUrl = Field(description="URL of the application's code repository")
    rollback_plan: str = Field(min_length=15, description="Brief description of the rollback plan to revert this deployment if it fails")

class ReleaseRecord(ReleaseRequest):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8], description="Unique identifier of a release record")
    status: Literal["PENDING", "IN_REVIEW", "APPROVED", "SCHEDULED"] = Field(default="PENDING", description="Current status of the release: PENDING, IN_REVIEW, APPROVED, SCHEDULED")
    created_at: datetime = Field(default_factory= lambda: datetime.now(timezone.utc), description="Timestamp when the release record was created")