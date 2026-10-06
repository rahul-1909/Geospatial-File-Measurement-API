import json
import uuid
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    InvalidFileFormatError,
    FileTooLargeError,
    FileNotFoundInDBError,
    CorruptGeospatialFileError
)
from app.db.models import FileRecord, FeatureRecord
from app.services.parser_service import ParserService
from app.services.measurement_service import MeasurementService
from app.utils.file_utils import sanitize_filename
from app.schemas.measurement import (
    FileMeasurementsResponse,
    FeatureMeasurement,
    MeasurementDetails,
    AreaMeasurement,
    LengthMeasurement,
    MeasurementSummary
)


class FileService:
    """Orchestrates file upload, storage, parsing, measurement calculation, and persistence."""

    @classmethod
    async def process_uploaded_file(cls, upload_file: UploadFile, db: Session) -> FileRecord:
        raw_filename = upload_file.filename or "unknown"
        safe_filename = sanitize_filename(raw_filename)
        extension = Path(safe_filename).suffix.lower()

        if extension not in settings.ALLOWED_EXTENSIONS:
            raise InvalidFileFormatError(safe_filename, settings.ALLOWED_EXTENSIONS)

        # Generate unique file ID
        file_id = uuid.uuid4().hex[:12]
        stored_filename = f"{file_id}_{safe_filename}"
        destination_path = settings.UPLOAD_DIR / stored_filename

        # Stream write to disk while monitoring file size
        total_size = 0
        chunk_size = 1024 * 1024  # 1 MB chunk

        try:
            with open(destination_path, "wb") as buffer:
                while True:
                    chunk = await upload_file.read(chunk_size)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > settings.MAX_UPLOAD_SIZE_BYTES:
                        raise FileTooLargeError(settings.MAX_UPLOAD_SIZE_BYTES)
                    buffer.write(chunk)
        except Exception:
            if destination_path.exists():
                destination_path.unlink()
            raise

        file_type = "SHAPEFILE_ZIP" if extension == ".zip" else "KML"

        # Create initial pending record
        file_record = FileRecord(
            id=file_id,
            filename=safe_filename,
            file_type=file_type,
            file_path=str(destination_path),
            file_size_bytes=total_size,
            crs=settings.DEFAULT_CRS,
            feature_count=0,
            status="PROCESSING"
        )
        db.add(file_record)
        db.commit()
        db.refresh(file_record)

        try:
            # Parse geospatial features
            parsed_data = ParserService.parse_file(destination_path)
            file_record.crs = parsed_data.crs
            file_record.feature_count = len(parsed_data.features)
            file_record.warnings_json = json.dumps(parsed_data.warnings)

            # Process features and calculate measurements
            for feat in parsed_data.features:
                measurement_details, area_m2, length_m, proj_crs = (
                    MeasurementService.process_feature_measurement(
                        geom_dict=feat.geometry,
                        source_crs=parsed_data.crs
                    )
                )

                feature_record = FeatureRecord(
                    file_id=file_record.id,
                    feature_index=feat.feature_index,
                    identifier=feat.identifier,
                    geometry_type=feat.geometry_type,
                    geometry_geojson=json.dumps(feat.geometry),
                    properties_json=json.dumps(feat.properties, default=str),
                    area_sq_meters=area_m2,
                    length_meters=length_m,
                    projected_crs=proj_crs,
                    measurement_status=measurement_details.status,
                    measurement_notes=measurement_details.notes
                )
                db.add(feature_record)

            file_record.status = "COMPLETED"
            db.commit()
            db.refresh(file_record)
            return file_record

        except Exception as e:
            db.rollback()
            file_record.status = "FAILED"
            file_record.error_message = str(e)
            db.add(file_record)
            db.commit()
            if isinstance(e, (InvalidFileFormatError, CorruptGeospatialFileError)):
                raise e
            raise CorruptGeospatialFileError(f"Failed to process file: {str(e)}")

    @classmethod
    def get_file_record(cls, file_id: str, db: Session) -> FileRecord:
        record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
        if not record:
            raise FileNotFoundInDBError(file_id)
        return record

    @classmethod
    def list_files(cls, db: Session, skip: int = 0, limit: int = 100) -> List[FileRecord]:
        return db.query(FileRecord).offset(skip).limit(limit).all()

    @classmethod
    def get_measurements_response(cls, file_id: str, db: Session) -> FileMeasurementsResponse:
        file_record = cls.get_file_record(file_id, db)
        feature_records: List[FeatureRecord] = (
            db.query(FeatureRecord)
            .filter(FeatureRecord.file_id == file_id)
            .order_by(FeatureRecord.feature_index)
            .all()
        )

        features: List[FeatureMeasurement] = []
        breakdown: Dict[str, int] = {}
        total_area_m2 = 0.0
        total_length_m = 0.0

        for fr in feature_records:
            breakdown[fr.geometry_type] = breakdown.get(fr.geometry_type, 0) + 1

            area_obj = None
            if fr.area_sq_meters is not None:
                total_area_m2 += fr.area_sq_meters
                area_obj = AreaMeasurement(
                    sq_meters=round(fr.area_sq_meters, 4),
                    sq_kilometers=round(fr.area_sq_meters / 1_000_000.0, 6),
                    hectares=round(fr.area_sq_meters / 10_000.0, 4),
                    acres=round(fr.area_sq_meters * 0.000247105381, 4)
                )

            length_obj = None
            if fr.length_meters is not None:
                total_length_m += fr.length_meters
                length_obj = LengthMeasurement(
                    meters=round(fr.length_meters, 4),
                    kilometers=round(fr.length_meters / 1000.0, 6),
                    miles=round(fr.length_meters / 1609.344, 4),
                    feet=round(fr.length_meters * 3.280839895, 4)
                )

            details = MeasurementDetails(
                area=area_obj,
                length=length_obj,
                projected_crs_used=fr.projected_crs,
                status=fr.measurement_status,
                notes=fr.measurement_notes
            )

            geom_dict = json.loads(fr.geometry_geojson)
            props_dict = json.loads(fr.properties_json)

            features.append(
                FeatureMeasurement(
                    feature_id=fr.id,
                    feature_index=fr.feature_index,
                    identifier=fr.identifier,
                    geometry_type=fr.geometry_type,
                    crs=file_record.crs,
                    geometry=geom_dict,
                    properties=props_dict,
                    measurements=details
                )
            )

        summary = MeasurementSummary(
            total_features=len(features),
            geometry_type_breakdown=breakdown,
            total_area_sq_meters=round(total_area_m2, 4),
            total_area_sq_km=round(total_area_m2 / 1_000_000.0, 6),
            total_length_meters=round(total_length_m, 4),
            total_length_km=round(total_length_m / 1000.0, 6)
        )

        return FileMeasurementsResponse(
            id=file_record.id,
            filename=file_record.filename,
            crs=file_record.crs,
            status=file_record.status,
            summary=summary,
            features=features
        )

    @classmethod
    def delete_file(cls, file_id: str, db: Session) -> None:
        record = cls.get_file_record(file_id, db)
        file_path = Path(record.file_path)
        if file_path.exists():
            file_path.unlink()
        db.delete(record)
        db.commit()
