import logging
from typing import Dict, Any, Optional, Tuple
from shapely.geometry import shape, mapping
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity
import shapely

from app.services.crs_service import CRSService
from app.schemas.measurement import (
    AreaMeasurement,
    LengthMeasurement,
    MeasurementDetails
)

logger = logging.getLogger(__name__)


class MeasurementService:
    """
    Computes precise metric measurements for geospatial geometries.
    
    Transforms geographic coordinates (EPSG:4326) to a local metric
    projected CRS (UTM) to ensure measurements represent true metric surface area
    and distance instead of invalid planar calculations on degree angles.
    """

    @classmethod
    def process_feature_measurement(
        cls,
        geom_dict: Dict[str, Any],
        source_crs: str
    ) -> Tuple[MeasurementDetails, Optional[float], Optional[float], Optional[str]]:
        """
        Process geometry measurement.
        Returns:
            Tuple of (MeasurementDetails, area_sq_meters, length_meters, projected_crs)
        """
        try:
            geom = shape(geom_dict)
        except Exception as e:
            return (
                MeasurementDetails(
                    status="INVALID_GEOMETRY",
                    notes=f"Failed to parse geometry structure: {str(e)}"
                ),
                None,
                None,
                None
            )

        if geom.is_empty:
            return (
                MeasurementDetails(
                    status="UNSUPPORTED_GEOMETRY",
                    notes="Geometry is empty."
                ),
                None,
                None,
                None
            )

        geom_type = geom.geom_type

        # Check topological validity
        validity_note = None
        if not geom.is_valid:
            reason = explain_validity(geom)
            validity_note = f"Geometry had topological anomalies ({reason}). Auto-repaired for calculation."
            try:
                geom = shapely.make_valid(geom)
            except Exception:
                geom = geom.buffer(0)

        # 1. Point / MultiPoint -> No measurement required
        if geom_type in ("Point", "MultiPoint"):
            return (
                MeasurementDetails(
                    status="NO_MEASUREMENT_REQUIRED",
                    notes="Point features have zero dimensional length and area; no measurement required."
                ),
                None,
                None,
                None
            )

        # 2. Polygon / MultiPolygon -> Calculate Area
        elif geom_type in ("Polygon", "MultiPolygon"):
            try:
                projected_crs = CRSService.determine_optimal_projected_crs(geom, source_crs)
                projected_geom = CRSService.reproject_geometry(geom, source_crs, projected_crs)
                
                area_m2 = float(projected_geom.area)
                area_km2 = area_m2 / 1_000_000.0
                hectares = area_m2 / 10_000.0
                acres = area_m2 * 0.000247105381

                area_obj = AreaMeasurement(
                    sq_meters=round(area_m2, 4),
                    sq_kilometers=round(area_km2, 6),
                    hectares=round(hectares, 4),
                    acres=round(acres, 4)
                )

                note = f"Area calculated in metric projected CRS ({projected_crs})."
                if validity_note:
                    note = f"{note} {validity_note}"

                return (
                    MeasurementDetails(
                        area=area_obj,
                        length=None,
                        projected_crs_used=projected_crs,
                        status="SUCCESS",
                        notes=note
                    ),
                    area_m2,
                    None,
                    projected_crs
                )
            except Exception as e:
                logger.error(f"Error calculating polygon area: {e}")
                return (
                    MeasurementDetails(
                        status="CALCULATION_ERROR",
                        notes=f"Error computing area: {str(e)}"
                    ),
                    None,
                    None,
                    None
                )

        # 3. LineString / MultiLineString -> Calculate Length
        elif geom_type in ("LineString", "MultiLineString", "LinearRing"):
            try:
                projected_crs = CRSService.determine_optimal_projected_crs(geom, source_crs)
                projected_geom = CRSService.reproject_geometry(geom, source_crs, projected_crs)

                length_m = float(projected_geom.length)
                length_km = length_m / 1000.0
                miles = length_m / 1609.344
                feet = length_m * 3.280839895

                length_obj = LengthMeasurement(
                    meters=round(length_m, 4),
                    kilometers=round(length_km, 6),
                    miles=round(miles, 4),
                    feet=round(feet, 4)
                )

                note = f"Length calculated in metric projected CRS ({projected_crs})."
                if validity_note:
                    note = f"{note} {validity_note}"

                return (
                    MeasurementDetails(
                        area=None,
                        length=length_obj,
                        projected_crs_used=projected_crs,
                        status="SUCCESS",
                        notes=note
                    ),
                    None,
                    length_m,
                    projected_crs
                )
            except Exception as e:
                logger.error(f"Error calculating line length: {e}")
                return (
                    MeasurementDetails(
                        status="CALCULATION_ERROR",
                        notes=f"Error computing length: {str(e)}"
                    ),
                    None,
                    None,
                    None
                )

        # 4. Graceful handling for other geometry types (GeometryCollection, etc.)
        else:
            return (
                MeasurementDetails(
                    status="UNSUPPORTED_GEOMETRY",
                    notes=f"Geometry type '{geom_type}' is not currently supported for automated measurement."
                ),
                None,
                None,
                None
            )
