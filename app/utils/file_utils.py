import os
import shutil
import zipfile
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, List
from app.core.exceptions import CorruptGeospatialFileError


def sanitize_filename(filename: str) -> str:
    """Strip dangerous characters and directory traversal prefixes."""
    base = os.path.basename(filename)
    clean = "".join(c for c in base if c.isalnum() or c in "._- ")
    return clean or "geospatial_file"


@contextmanager
def temporary_extraction_dir() -> Generator[Path, None, None]:
    """Context manager for creating and securely cleaning up temporary extraction directories."""
    temp_dir = tempfile.mkdtemp(prefix="geo_extract_")
    try:
        yield Path(temp_dir)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


MAX_UNCOMPRESSED_ZIP_BYTES = 250 * 1024 * 1024  # 250 MB safety threshold
MAX_COMPRESSION_RATIO = 100  # Threshold for decompression bomb


def extract_zip_safely(zip_path: Path, target_dir: Path) -> List[Path]:
    """
    Extract a zip file safely:
    1. Prevents directory traversal vulnerabilities (Zip Slip).
    2. Enforces uncompressed size thresholds and compression ratio checks (Zip Bomb defense).
    Returns list of extracted file paths.
    """
    extracted_files: List[Path] = []
    
    if not zipfile.is_zipfile(zip_path):
        raise CorruptGeospatialFileError("Uploaded file is not a valid zip archive.")

    total_uncompressed_bytes = 0

    with zipfile.ZipFile(zip_path, 'r') as zf:
        resolved_target = target_dir.resolve()
        
        for member in zf.infolist():
            # Zip Bomb protection: cumulative size
            total_uncompressed_bytes += member.file_size
            if total_uncompressed_bytes > MAX_UNCOMPRESSED_ZIP_BYTES:
                raise CorruptGeospatialFileError(
                    f"Zip archive exceeds maximum uncompressed size limit of {MAX_UNCOMPRESSED_ZIP_BYTES // (1024 * 1024)} MB (potential zip bomb)."
                )

            # Zip Bomb protection: abnormal compression ratio on files > 1MB
            if member.file_size > 1024 * 1024:
                comp_size = max(member.compress_size, 1)
                if (member.file_size / comp_size) > MAX_COMPRESSION_RATIO:
                    raise CorruptGeospatialFileError(
                        f"Abnormal compression ratio detected for {member.filename} (potential zip bomb)."
                    )

            member_path = (target_dir / member.filename).resolve()
            
            # Zip Slip check: ensure destination path is within resolved_target
            if not str(member_path).startswith(str(resolved_target)):
                raise CorruptGeospatialFileError(
                    f"Malicious zip archive entry detected (path traversal attempt): {member.filename}"
                )
            
            if member.is_dir():
                member_path.mkdir(parents=True, exist_ok=True)
            else:
                member_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as source, open(member_path, "wb") as dest:
                    shutil.copyfileobj(source, dest)
                extracted_files.append(member_path)

    return extracted_files
