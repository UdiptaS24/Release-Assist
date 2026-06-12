from fastapi import APIRouter, HTTPException, status
from typing import Literal
import textwrap
from app.models.release_model import ReleaseRequest
from app.controllers import release_controller

router = APIRouter(prefix="/releases", tags=["releases"])

def generate_summary(record: dict) -> str:
    """Generate a concise summary of the release request for quick review."""
    return textwrap.dedent(
        f"""
        # Release Request Summary
        ---
        * **App Name**: {record['app_name']}
        * **Version**: {record['version']}
        * **Release Type**: {record['release_type']}
        * **Contact Email**: {record['contact_email']}
        * **Repository URL**: {record['repository_url']}
        * **Rollback Plan**: {record['rollback_plan']}
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

@router.patch("/{release_id}/status", response_model=dict, status_code=status.HTTP_200_OK)
async def update_release_status(release_id: str, new_status: Literal["PENDING", "IN_REVIEW", "APPROVED", "SCHEDULED"]):
    try:
        updated_record = release_controller.update_release_status(release_id, new_status)
        if updated_record:
            summary = generate_summary(updated_record)
            return {"data": updated_record, "summary": summary}
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
            detail=f"An error occurred while updating the release status: {str(e)}"
        )