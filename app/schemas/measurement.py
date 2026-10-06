from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field


class AreaMeasurement(BaseModel):
    sq_meters: float = Field(..., description="Area in square meters")
    sq_kilometers: float = Field(..., description="Area in square kilometers")
    hectares: float = Field(..., description="Area in hectares")
    acres: float = Field(..., description="Area in acres")


class LengthMeasurement(BaseModel):
    meters: float = Field(..., description="Length in meters")
    kilometers: float = Field(..., description="Length in kilometers")
    miles: float = Field(..., description="Length in miles")
    feet: float = Field(..., description="Length in feet")


class MeasurementDetails(BaseModel):
    area: Optional[AreaMeasurement] = Field(None, description="Calculated area for 2D polygon surfaces")
    length: Optional[LengthMeasurement] = Field(None, description="Calculated length for linear geometries")
    projected_crs_used: Optional[str] = Field(
        None,
        description="The metric projected coordinate system used to compute distortion-free measurements"
    )
    status: str = Field(
        ...,
        description="Status: SUCCESS, NO_MEASUREMENT_REQUIRED, UNSUPPORTED_GEOMETRY, INVALID_GEOMETRY"
    )
    notes: Optional[str] = Field(None, description="Additional context or topology notices")


class FeatureMeasurement(BaseModel):
    feature_id: Union[int, str] = Field(..., description="Unique identifier or index of the feature")
    feature_index: int = Field(..., description="0-based index of feature within the file")
    identifier: Optional[str] = Field(None, description="Name or identifier extracted from feature properties")
    geometry_type: str = Field(..., description="GeoJSON geometry type (Polygon, LineString, Point, etc.)")
    crs: str = Field(..., description="Coordinate Reference System of the source geometry")
    geometry: Dict[str, Any] = Field(..., description="GeoJSON geometry representation")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Feature attributes and metadata")
    measurements: MeasurementDetails = Field(..., description="Measurement calculations and metric status")


class MeasurementSummary(BaseModel):
    total_features: int = Field(..., description="Total features processed")
    geometry_type_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of features per geometry type"
    )
    total_area_sq_meters: float = Field(0.0, description="Sum of all polygon areas in square meters")
    total_area_sq_km: float = Field(0.0, description="Sum of all polygon areas in square kilometers")
    total_length_meters: float = Field(0.0, description="Sum of all linestring lengths in meters")
    total_length_km: float = Field(0.0, description="Sum of all linestring lengths in kilometers")


class FileMeasurementsResponse(BaseModel):
    id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original filename")
    crs: str = Field(..., description="Primary CRS of the file")
    status: str = Field(..., description="Processing status")
    summary: MeasurementSummary = Field(..., description="Aggregated measurement summary")
    features: List[FeatureMeasurement] = Field(default_factory=list, description="Per-feature measurement details")
