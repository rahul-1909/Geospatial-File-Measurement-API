from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.file import FileInfoResponse, FileListResponse
from app.schemas.measurement import FileMeasurementsResponse
from app.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["Geospatial Files & Measurements"])


@router.post(
    "/",
    response_model=FileInfoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a geospatial file",
    description="Upload a zipped Shapefile (.zip) or KML file (.kml, .kmz). Extracts features and computes measurements."
)
@router.post(
    "",
    response_model=FileInfoResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
async def upload_geospatial_file(
    file: UploadFile = File(..., description="Geospatial file (.zip Shapefile or .kml)"),
    db: Session = Depends(get_db)
):
    """Accepts a geospatial file (.zip or .kml), processes features, and computes measurements."""
    file_record = await FileService.process_uploaded_file(file, db)
    return file_record


@router.get(
    "/{file_id}/",
    response_model=FileInfoResponse,
    summary="Get file processing status and metadata",
    description="Retrieves metadata and processing status for an uploaded file by its ID."
)
@router.get(
    "/{file_id}",
    response_model=FileInfoResponse,
    include_in_schema=False
)
def get_file_info(
    file_id: str,
    db: Session = Depends(get_db)
):
    """Returns metadata for an uploaded file matching the specified format."""
    return FileService.get_file_record(file_id, db)


@router.get(
    "/{file_id}/measurements/",
    response_model=FileMeasurementsResponse,
    summary="Get calculated measurements for features",
    description="Returns calculated metric measurements (Polygon Area, LineString Length) and summary statistics."
)
@router.get(
    "/{file_id}/measurements",
    response_model=FileMeasurementsResponse,
    include_in_schema=False
)
def get_file_measurements(
    file_id: str,
    db: Session = Depends(get_db)
):
    """Returns measurements for the features in the uploaded file."""
    return FileService.get_measurements_response(file_id, db)


@router.get(
    "/",
    response_model=FileListResponse,
    summary="List all uploaded geospatial files",
    description="Returns a paginated list of all uploaded geospatial files and their processing status."
)
@router.get(
    "",
    response_model=FileListResponse,
    include_in_schema=False
)
def list_files(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all uploaded files."""
    records = FileService.list_files(db, skip=skip, limit=limit)
    return FileListResponse(total=len(records), files=records)


@router.delete(
    "/{file_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a geospatial file",
    description="Deletes file records, features, and uploaded data from disk."
)
@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False
)
def delete_file(
    file_id: str,
    db: Session = Depends(get_db)
):
    """Deletes the specified file and its associated features."""
    FileService.delete_file(file_id, db)
    return None
