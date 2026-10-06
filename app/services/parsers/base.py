from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional


@dataclass
class ParsedFeature:
    """Represents an extracted geospatial feature."""
    feature_index: int
    geometry_type: str
    geometry: Dict[str, Any]
    crs: str
    properties: Dict[str, Any] = field(default_factory=dict)
    identifier: Optional[str] = None


@dataclass
class ParsedGeospatialData:
    """Represents all features and global metadata extracted from a file."""
    filename: str
    file_type: str
    crs: str
    features: List[ParsedFeature] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class BaseGeospatialParser(ABC):
    """Abstract base class for geospatial file parsers."""

    @abstractmethod
    def parse(self, file_path: Path) -> ParsedGeospatialData:
        """Parse geospatial file and return extracted features and CRS."""
        pass
