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


def extract_zip_safely(zip_path: Path, target_dir: Path) -> List[Path]:
    """
    Extract a zip file safely, preventing directory traversal vulnerabilities (Zip Slip).
    Returns list of extracted file paths.
    """
    extracted_files: List[Path] = []
    
    if not zipfile.is_zipfile(zip_path):
        raise CorruptGeospatialFileError("Uploaded file is not a valid zip archive.")

    with zipfile.ZipFile(zip_path, 'r') as zf:
        resolved_target = target_dir.resolve()
        
        for member in zf.infolist():
            # Prevent zip bombs: check uncompressed size sanity if needed
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
