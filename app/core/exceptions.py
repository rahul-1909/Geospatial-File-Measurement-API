from fastapi import HTTPException, status


class GeospatialAPIException(HTTPException):
    """Base exception for Geospatial File Measurement API."""
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


class FileNotFoundInDBError(GeospatialAPIException):
    def __init__(self, file_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Geospatial file with ID '{file_id}' was not found."
        )


class InvalidFileFormatError(GeospatialAPIException):
    def __init__(self, filename: str, allowed: set):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File '{filename}' has an unsupported format. "
                f"Supported formats are: {', '.join(sorted(allowed))}."
            )
        )


class FileTooLargeError(GeospatialAPIException):
    def __init__(self, max_bytes: int):
        max_mb = max_bytes / (1024 * 1024)
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds maximum allowed size of {max_mb:.1f} MB."
        )


class CorruptGeospatialFileError(GeospatialAPIException):
    def __init__(self, message: str):
        super().__init__(
            status_code=422,
            detail=f"Unable to parse geospatial file: {message}"
        )


class CRSTransformationError(GeospatialAPIException):
    def __init__(self, message: str):
        super().__init__(
            status_code=422,
            detail=f"Coordinate Reference System transformation failed: {message}"
        )
