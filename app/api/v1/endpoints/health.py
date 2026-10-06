from fastapi import APIRouter
from app.core.config import settings

router = APIRouter(tags=["System Health"])


@router.get("/health", summary="Health check endpoint")
@router.get("/health/", include_in_schema=False)
def health_check():
    """Returns application status, version, and supported geospatial formats."""
    return {
        "status": "HEALTHY",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "supported_formats": sorted(list(settings.ALLOWED_EXTENSIONS)),
        "measurement_engines": {
            "polygon": "Area calculation via dynamic metric UTM projection",
            "linestring": "Length calculation via dynamic metric UTM projection",
            "point": "No measurement required"
        }
    }
