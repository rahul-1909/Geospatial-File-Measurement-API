import math
import logging
from typing import Tuple, Optional
import pyproj
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform
from app.core.exceptions import CRSTransformationError

logger = logging.getLogger(__name__)


class CRSService:
    """
    Production service for identifying Coordinate Reference Systems (CRS),
    detecting geographic vs projected coordinate systems, handling metric vs imperial units,
    and selecting the optimal metric projected CRS (such as UTM) for accurate planar measurements.
    """

    @staticmethod
    def clean_crs_string(crs_input: Optional[str]) -> str:
        """Strip annotations such as '(assumed, missing .prj)' to obtain a valid CRS string."""
        if not crs_input:
            return "EPSG:4326"
        clean = crs_input.split("(")[0].strip()
        return clean or "EPSG:4326"

    @classmethod
    def normalize_crs(cls, crs_input: Optional[str]) -> str:
        """
        Normalize and validate a CRS string (e.g. 'EPSG:4326', 'WGS84', WKT).
        Returns standardized 'EPSG:XXXX' or proj string.
        """
        if not crs_input or crs_input.strip() == "":
            return "EPSG:4326"

        clean_input = cls.clean_crs_string(crs_input)
        try:
            crs_obj = pyproj.CRS.from_user_input(clean_input)
            auth_code = crs_obj.to_authority()
            if auth_code:
                return f"{auth_code[0]}:{auth_code[1]}"
            return crs_obj.to_string()
        except Exception as e:
            logger.warning(f"Could not parse CRS '{crs_input}': {e}. Defaulting to EPSG:4326.")
            return "EPSG:4326"

    @staticmethod
    def parse_prj_file(prj_content: str) -> str:
        """Parse WKT content from a shapefile .prj file to EPSG."""
        if not prj_content or not prj_content.strip():
            return "EPSG:4326"
        try:
            crs_obj = pyproj.CRS.from_wkt(prj_content.strip())
            auth = crs_obj.to_authority()
            if auth:
                return f"{auth[0]}:{auth[1]}"
            epsg = crs_obj.to_epsg()
            if epsg:
                return f"EPSG:{epsg}"
            return "EPSG:4326"
        except Exception as e:
            logger.warning(f"Failed to parse .prj WKT content: {e}. Defaulting to EPSG:4326")
            return "EPSG:4326"

    @classmethod
    def is_geographic(cls, crs_str: str) -> bool:
        """Returns True if the CRS uses angular units (degrees/lat-lon)."""
        clean = cls.clean_crs_string(crs_str)
        try:
            crs_obj = pyproj.CRS.from_user_input(clean)
            return crs_obj.is_geographic
        except Exception:
            # Default assumption for unrecognized is geographic WGS84
            return True

    @classmethod
    def determine_optimal_projected_crs(cls, geometry: BaseGeometry, source_crs: str = "EPSG:4326") -> str:
        """
        Determines the optimal metric projected CRS for a given geometry.
        
        Strategy:
        1. If source CRS is already projected in meters, retain source CRS.
        2. If source CRS is projected in non-metric units (e.g., US Survey Feet),
           convert centroid coordinates to WGS84 (EPSG:4326) degrees first.
        3. If source CRS is geographic (degrees), use the geometry's centroid (lon, lat).
        4. Dynamically compute the corresponding UTM Zone from (lon, lat):
           - zone = floor((lon + 180) / 6) + 1 (clamped to 1-60)
           - Northern hemisphere (lat >= 0): EPSG:32600 + zone
           - Southern hemisphere (lat < 0): EPSG:32700 + zone
           - Extreme polar latitudes (|lat| > 84): Universal Polar Stereographic (UPS)
        """
        clean_source = cls.clean_crs_string(source_crs)
        crs_obj = None
        try:
            crs_obj = pyproj.CRS.from_user_input(clean_source)
            if crs_obj.is_projected:
                # If already projected, check if linear unit is meter
                axis_info = crs_obj.axis_info
                if axis_info and getattr(axis_info[0], 'unit_name', '').lower() in ('metre', 'meter', 'm'):
                    auth = crs_obj.to_authority()
                    if auth:
                        return f"{auth[0]}:{auth[1]}"
                    return clean_source
        except Exception:
            pass

        if geometry.is_empty:
            return "EPSG:3857"

        centroid = geometry.centroid

        # Obtain centroid in WGS84 degrees (lon, lat)
        lon, lat = centroid.x, centroid.y
        if crs_obj and crs_obj.is_projected:
            # Source CRS was projected (e.g. in feet), so centroid.x/y are linear coordinates.
            # Reproject centroid to WGS84 degrees to calculate optimal UTM zone.
            try:
                to_wgs84 = pyproj.Transformer.from_crs(clean_source, "EPSG:4326", always_xy=True)
                lon, lat = to_wgs84.transform(centroid.x, centroid.y)
            except Exception as e:
                logger.warning(f"Could not convert projected centroid to WGS84: {e}")

        # Clamp lon to -180 .. 180
        if lon > 180.0:
            lon = 180.0
        elif lon < -180.0:
            lon = -180.0

        # Handle extreme polar regions with Universal Polar Stereographic (UPS)
        if lat > 84.0:
            return "EPSG:32661"  # WGS 84 / UPS North
        elif lat < -80.0:
            return "EPSG:32761"  # WGS 84 / UPS South

        # Calculate UTM zone
        utm_zone = int(math.floor((lon + 180.0) / 6.0)) + 1
        if utm_zone > 60:
            utm_zone = 60
        elif utm_zone < 1:
            utm_zone = 1

        if lat >= 0:
            return f"EPSG:{32600 + utm_zone}"
        else:
            return f"EPSG:{32700 + utm_zone}"

    @classmethod
    def reproject_geometry(
        cls,
        geometry: BaseGeometry,
        source_crs: str,
        target_crs: str
    ) -> BaseGeometry:
        """
        Transforms a Shapely geometry from source_crs to target_crs.
        Uses always_xy=True to guarantee (x, y) = (lon, lat) order regardless of PROJ versions.
        """
        if geometry.is_empty:
            return geometry

        clean_source = cls.clean_crs_string(source_crs)
        clean_target = cls.clean_crs_string(target_crs)

        if clean_source == clean_target:
            return geometry

        try:
            transformer = pyproj.Transformer.from_crs(
                clean_source,
                clean_target,
                always_xy=True
            )
            projected_geom = transform(transformer.transform, geometry)
            return projected_geom
        except Exception as e:
            raise CRSTransformationError(
                f"Failed to reproject geometry from {source_crs} to {target_crs}: {str(e)}"
            )
