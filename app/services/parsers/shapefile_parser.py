import os
import datetime
from pathlib import Path
from typing import Dict, Any, List
import shapefile

from app.core.exceptions import CorruptGeospatialFileError
from app.services.crs_service import CRSService
from app.services.parsers.base import BaseGeospatialParser, ParsedFeature, ParsedGeospatialData
from app.utils.file_utils import temporary_extraction_dir, extract_zip_safely


class ShapefileParser(BaseGeospatialParser):
    """
    Parser for ESRI Shapefiles bundled within .zip archives.
    Extracts geometric shapes, coordinate system (.prj), and DBF attribute tables.
    """

    def parse(self, file_path: Path) -> ParsedGeospatialData:
        filename = file_path.name

        with temporary_extraction_dir() as temp_dir:
            if file_path.suffix.lower() == ".zip":
                extracted_files = extract_zip_safely(file_path, temp_dir)
                
                # Search for .shp file
                shp_files = [f for f in extracted_files if f.suffix.lower() == ".shp"]
                if not shp_files:
                    raise CorruptGeospatialFileError(
                        "Zip archive does not contain a valid .shp file component."
                    )
                target_shp = shp_files[0]
            elif file_path.suffix.lower() == ".shp":
                target_shp = file_path
            else:
                raise CorruptGeospatialFileError(f"Unsupported shapefile extension: {file_path.suffix}")

            # Locate corresponding .prj file to detect CRS
            prj_file = target_shp.with_suffix(".prj")
            crs = "EPSG:4326"
            if prj_file.exists():
                try:
                    with open(prj_file, "r", encoding="utf-8", errors="ignore") as f:
                        prj_content = f.read()
                    crs = CRSService.parse_prj_file(prj_content)
                except Exception:
                    crs = "EPSG:4326"

            features: List[ParsedFeature] = []

            try:
                # Open with PyShp
                with shapefile.Reader(str(target_shp), encoding="utf-8", encodingErrors="replace") as sf:
                    field_names = [f[0] for f in sf.fields[1:]]  # skip deletion flag

                    for idx, shape_record in enumerate(sf.shapeRecords()):
                        geom_obj = shape_record.shape
                        rec_values = shape_record.record

                        # Build properties dict
                        properties: Dict[str, Any] = {}
                        for f_name, f_val in zip(field_names, rec_values):
                            if isinstance(f_val, (datetime.date, datetime.datetime)):
                                properties[f_name] = f_val.isoformat()
                            elif isinstance(f_val, bytes):
                                properties[f_name] = f_val.decode("utf-8", errors="replace")
                            else:
                                properties[f_name] = f_val

                        # Extract geometry
                        if not geom_obj or not hasattr(geom_obj, "__geo_interface__"):
                            continue

                        geo_interface = geom_obj.__geo_interface__
                        geom_type = geo_interface.get("type", "Unknown")

                        # Determine identifier
                        identifier = (
                            properties.get("ID")
                            or properties.get("id")
                            or properties.get("NAME")
                            or properties.get("name")
                            or f"feature_{idx}"
                        )

                        features.append(
                            ParsedFeature(
                                feature_index=idx,
                                identifier=str(identifier),
                                geometry_type=geom_type,
                                geometry=geo_interface,
                                crs=crs,
                                properties=properties
                            )
                        )

            except Exception as e:
                raise CorruptGeospatialFileError(f"Failed to read shapefile records: {str(e)}")

            return ParsedGeospatialData(
                filename=filename,
                file_type="SHAPEFILE_ZIP",
                crs=crs,
                features=features
            )
