from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class FileInfoResponse(BaseModel):
    """
    Standard response format matching requirement specification:
    {
        "id": "abc123",
        "filename": "survey.kml",
        "feature_count": 120,
        "crs": "EPSG:4326",
        "status": "COMPLETED"
    }
    """
    id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original uploaded filename")
    feature_count: int = Field(0, description="Total number of geospatial features extracted")
    crs: str = Field("EPSG:4326", description="Detected or default Coordinate Reference System")
    status: str = Field(..., description="Processing status: PENDING, PROCESSING, COMPLETED, FAILED")
    file_type: Optional[str] = Field(None, description="Type of geospatial file (SHAPEFILE_ZIP or KML)")
    file_size_bytes: Optional[int] = Field(None, description="Size in bytes")
    created_at: Optional[datetime] = Field(None, description="Timestamp of file upload")
    error_message: Optional[str] = Field(None, description="Error detail if processing failed")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings (e.g., missing .prj)")

    model_config = ConfigDict(from_attributes=True)


class FileListResponse(BaseModel):
    total: int = Field(..., description="Total count of uploaded files")
    files: List[FileInfoResponse] = Field(default_factory=list, description="List of file records")
