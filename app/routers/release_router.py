from fastapi import APIRouter, HTTPException, status
from typing import Literal
import textwrap
from app.models.release_model import ReleaseRequest, ScheduleRequest
from app.controllers import release_controller

router = APIRouter(prefix="/releases", tags=["releases"])

def generate_summary(record: dict) -> str:
    """Generate a concise summary of the release request for quick review."""
    return textwrap.dedent(
        f"""
        # Release Request Summary
        * **App Name**: {record['app_name']}
        * **Version**: {record['version']}
        * **Release Type**: {record['release_type']}
        * **Contact Email**: {record['contact_email']}
        * **Repository URL**: {record['repository_url']}
        * **Rollback Plan**: {record['rollback_plan']}
        * **Requested schedule start time**: {record['requested_start']}
        * **Requested schedule end time**: {record['requested_end']}
        * **Contacts to notify**: {",".join(record['notify_contacts'])}
        * **Status**: {record['status']}
        """
    ).strip()

@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_release(payload: ReleaseRequest):
    try:
        saved_record = release_controller.store_release_record(payload)
        summary = generate_summary(saved_record)
        return {"message": "Release request captured successfully", "data" : saved_record, "summary": summary}
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid input: {str(ve)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the release request: {str(e)}"
        )
    
@router.get("", response_model=list[dict], status_code=status.HTTP_200_OK)
async def list_releases():
    try:
        return release_controller.get_all_releases()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching release records: {str(e)}"
        )

@router.get("/{release_id}", response_model=dict, status_code=status.HTTP_200_OK)
async def get_release(release_id: str):
    try:
        record = release_controller.get_release_by_id(release_id)
        if record:
            summary = generate_summary(record)
            return {"data": record, "summary": summary}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Release record with ID {release_id} not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching the release record: {str(e)}"
        )

@router.post("/{release_id}/schedule", response_model=dict, status_code=status.HTTP_200_OK)
async def schedule_release(release_id: str, payload: ScheduleRequest):
    try:
        updated_record = release_controller.schedule_release(
            release_id=release_id,
            requested_start=payload.requested_start,
            requested_end=payload.requested_end,
            notify_contacts=[str(email) for email in payload.notify_contacts]
        )

        if not updated_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Release record with id {release_id} not found")
        return{
            "message": "Deployement scheduling evaluated successfully",
            "data": updated_record,
            "schedule": updated_record.get("schedule", {})
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occured while scheduling deployment: {str(e)}"
        )
    
@router.post("/{release_id}/run", response_model=dict, status_code=status.HTTP_200_OK)
async def run_release_pipeline(release_id: str):
    try:
        record = release_controller.run_pipeline(release_id)

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Release record with ID {release_id} not found",
            )

        return {
            "message": "Release pipeline executed",
            "data": record,
            "pipeline_status": record.get("pipeline_status"),
            "pipeline_log": record.get("pipeline_log", []),
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while running the pipeline: {str(e)}",
        )