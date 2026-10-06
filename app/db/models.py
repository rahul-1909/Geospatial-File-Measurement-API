from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base


class FileRecord(Base):
    __tablename__ = "files"

    id = Column(String(36), primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)  # 'SHAPEFILE_ZIP' or 'KML'
    file_path = Column(String(1024), nullable=False)
    file_size_bytes = Column(Integer, default=0)
    crs = Column(String(100), default="EPSG:4326")
    feature_count = Column(Integer, default=0)
    status = Column(String(50), default="PENDING")  # PENDING, PROCESSING, COMPLETED, FAILED
    error_message = Column(Text, nullable=True)
    warnings_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    features = relationship("FeatureRecord", back_populates="file", cascade="all, delete-orphan", lazy="joined")

    @property
    def warnings(self):
        import json
        try:
            return json.loads(self.warnings_json or "[]")
        except Exception:
            return []


class FeatureRecord(Base):
    __tablename__ = "features"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    file_id = Column(String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    feature_index = Column(Integer, nullable=False)
    identifier = Column(String(255), nullable=True)
    geometry_type = Column(String(100), nullable=False)
    geometry_geojson = Column(Text, nullable=False)  # Stored as GeoJSON string
    properties_json = Column(Text, nullable=False, default="{}")  # Stored as JSON string
    
    # Measurements in metric system (derived via projected CRS)
    area_sq_meters = Column(Float, nullable=True)
    length_meters = Column(Float, nullable=True)
    projected_crs = Column(String(100), nullable=True)
    
    measurement_status = Column(String(50), default="SUCCESS")
    # 'SUCCESS', 'NO_MEASUREMENT_REQUIRED', 'UNSUPPORTED_GEOMETRY', 'INVALID_GEOMETRY'
    measurement_notes = Column(Text, nullable=True)

    file = relationship("FileRecord", back_populates="features")
