from pathlib import Path
from typing import Dict, Type
from app.core.exceptions import InvalidFileFormatError
from app.services.parsers.base import BaseGeospatialParser, ParsedGeospatialData
from app.services.parsers.shapefile_parser import ShapefileParser
from app.services.parsers.kml_parser import KMLParser


class ParserService:
    """Service to select appropriate parser based on file type and extract geospatial data."""

    _parsers: Dict[str, Type[BaseGeospatialParser]] = {
        ".zip": ShapefileParser,
        ".kml": KMLParser,
        ".kmz": KMLParser,
    }

    @classmethod
    def parse_file(cls, file_path: Path) -> ParsedGeospatialData:
        suffix = file_path.suffix.lower()
        parser_cls = cls._parsers.get(suffix)

        if not parser_cls:
            raise InvalidFileFormatError(file_path.name, set(cls._parsers.keys()))

        parser_instance = parser_cls()
        return parser_instance.parse(file_path)
