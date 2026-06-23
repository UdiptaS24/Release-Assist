from pydantic import BaseModel, Field, EmailStr, HttpUrl
from datetime import datetime, timezone
from typing import Literal, Dict, Any
import uuid

class ReleaseRequest(BaseModel):
    app_name: str = Field(min_length=2, max_length=100, description="Name of the application")
    version: str = Field(pattern=r'^\d+\.\d+\.\d+$', description="Version number in the format X.Y.Z")
    release_type: Literal["major", "minor", "patch"] = Field(description="Type of release: major, minor or patch")
    contact_email: EmailStr = Field(description="AppDev team contact email")
    repository_url: HttpUrl = Field(description="URL of the application's code repository")
    rollback_plan: str = Field(min_length=15, description="Brief description of the rollback plan to revert this deployment if it fails")

class ReleaseRecord(ReleaseRequest):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8], description="Unique identifier of a release record")
    status: Literal["PENDING", "APPROVED", "NEEDS_REVIEW", "BLOCKED"] = Field(default="PENDING", description="Current status of the release automatically set by agent: PENDING, APPROVED, NEEDS_REVIEW, BLOCKED")
    created_at: datetime = Field(default_factory= lambda: datetime.now(timezone.utc), description="Timestamp when the release record was created")
    validation_report: Dict[str, Any] = Field(default_factory=dict, description="Detailed report of the repository analysis and validation results")
    change_snapshot: Dict[str, Any] = Field(default_factory=dict, description="Change snapshot showing difference between incoming version and last released version")