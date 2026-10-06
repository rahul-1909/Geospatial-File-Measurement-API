from pathlib import Path
from typing import List, Set
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Geospatial File Measurement API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = (
        "Production-grade backend service for processing geospatial files "
        "(Shapefile .zip and KML/KMZ), extracting features, transforming CRS, "
        "and computing precise metric measurements."
    )
    API_V1_PREFIX: str = "/api"
    
    # Storage settings
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    TEMP_DIR: Path = BASE_DIR / "temp"
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'geospatial.db'}"
    
    # File upload limits
    MAX_UPLOAD_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MB
    ALLOWED_EXTENSIONS: Set[str] = {".zip", ".kml", ".kmz"}
    
    # Geospatial defaults
    DEFAULT_CRS: str = "EPSG:4326"
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
# Ensure directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
