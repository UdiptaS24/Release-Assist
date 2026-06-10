from fastapi import APIRouter, HTTPException, status
from app.models.release_model import ReleaseRequest
from app.controllers import release_controller

router = APIRouter(prefix="/releases", tags=["releases"])

@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_release(payload: ReleaseRequest):
    try:
        saved_record = release_controller.store_release_record(payload)
        return {"message": "Release request captured successfully", "data" : saved_record}
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
            return record
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Release record with ID {release_id} not found"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching the release record: {str(e)}"
        )

@router.patch("/{release_id}/status", response_model=dict, status_code=status.HTTP_200_OK)
async def update_release_status(release_id: str, status: str):
    try:
        updated_record = release_controller.update_release_status(release_id, status)
        if updated_record:
            return updated_record
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Release record with ID {release_id} not found"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating the release status: {str(e)}"
        )