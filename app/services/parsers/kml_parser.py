import re
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Optional
import defusedxml.ElementTree as ET

from app.core.exceptions import CorruptGeospatialFileError
from app.services.parsers.base import BaseGeospatialParser, ParsedFeature, ParsedGeospatialData


class KMLParser(BaseGeospatialParser):
    """
    Parser for OGC KML (Keyhole Markup Language) and KMZ compressed files.
    Extracts Placemark geometries (Point, LineString, Polygon, MultiGeometry)
    and associated attribute properties.
    """

    def parse(self, file_path: Path) -> ParsedGeospatialData:
        filename = file_path.name
        xml_content: str = ""

        if file_path.suffix.lower() == ".kmz":
            # Extract doc.kml from KMZ archive
            try:
                with zipfile.ZipFile(file_path, "r") as zf:
                    kml_entries = [name for name in zf.namelist() if name.lower().endswith(".kml")]
                    if not kml_entries:
                        raise CorruptGeospatialFileError("KMZ archive contains no .kml document.")
                    with zf.open(kml_entries[0]) as kml_file:
                        xml_content = kml_file.read().decode("utf-8", errors="replace")
            except Exception as e:
                raise CorruptGeospatialFileError(f"Error opening KMZ archive: {str(e)}")
        else:
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    xml_content = f.read()
            except Exception as e:
                raise CorruptGeospatialFileError(f"Error reading KML file: {str(e)}")

        if not xml_content.strip():
            raise CorruptGeospatialFileError("KML file is empty.")

        try:
            root = ET.fromstring(xml_content)
        except Exception as e:
            raise CorruptGeospatialFileError(f"Malformed XML in KML file: {str(e)}")

        features: List[ParsedFeature] = []
        feature_index = 0

        # Recursively inspect for Placemark elements
        for elem in root.iter():
            tag_name = self._strip_namespace(elem.tag)
            if tag_name == "Placemark":
                parsed = self._parse_placemark(elem, feature_index)
                if parsed:
                    features.append(parsed)
                    feature_index += 1

        return ParsedGeospatialData(
            filename=filename,
            file_type="KML",
            crs="EPSG:4326",  # Standard KML specification uses WGS84
            features=features
        )

    def _strip_namespace(self, tag: str) -> str:
        """Strip XML namespace prefix from tag."""
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    def _find_child_by_tag(self, parent: ET.Element, target_tag: str) -> Optional[ET.Element]:
        """Find immediate child by tag name ignoring namespaces."""
        for child in parent:
            if self._strip_namespace(child.tag) == target_tag:
                return child
        return None

    def _find_descendant_by_tag(self, parent: ET.Element, target_tag: str) -> Optional[ET.Element]:
        """Find first descendant by tag name ignoring namespaces."""
        for elem in parent.iter():
            if self._strip_namespace(elem.tag) == target_tag:
                return elem
        return None

    def _parse_coordinates(self, coord_str: str) -> List[List[float]]:
        """
        Parse KML coordinates string (lon,lat,alt tuples separated by whitespace).
        Returns a list of [lon, lat] coordinate pairs.
        """
        coords: List[List[float]] = []
        if not coord_str:
            return coords

        tokens = coord_str.strip().split()
        for token in tokens:
            parts = token.split(",")
            if len(parts) >= 2:
                try:
                    lon = float(parts[0].strip())
                    lat = float(parts[1].strip())
                    coords.append([lon, lat])
                except ValueError:
                    continue
        return coords

    def _parse_placemark(self, elem: ET.Element, index: int) -> Optional[ParsedFeature]:
        """Extract geometry and attributes from a Placemark element."""
        properties: Dict[str, Any] = {}

        # Extract name, description, ExtendedData
        for child in elem:
            child_tag = self._strip_namespace(child.tag)
            if child_tag == "name" and child.text:
                properties["name"] = child.text.strip()
            elif child_tag == "description" and child.text:
                properties["description"] = child.text.strip()
            elif child_tag == "ExtendedData":
                self._extract_extended_data(child, properties)

        # Prioritize name if available, then XML id, then index fallback
        identifier = properties.get("name") or elem.attrib.get("id") or f"placemark_{index}"

        # Extract Geometry
        geom = self._extract_geometry(elem)
        if not geom:
            return None

        geom_type = geom.get("type", "Unknown")

        return ParsedFeature(
            feature_index=index,
            identifier=str(identifier),
            geometry_type=geom_type,
            geometry=geom,
            crs="EPSG:4326",
            properties=properties
        )

    def _extract_extended_data(self, ext_elem: ET.Element, properties: Dict[str, Any]) -> None:
        """Extract key-value pairs from ExtendedData / SchemaData / Data tags."""
        for child in ext_elem.iter():
            tag = self._strip_namespace(child.tag)
            if tag == "Data":
                name = child.attrib.get("name")
                val_elem = self._find_descendant_by_tag(child, "value")
                if name and val_elem is not None and val_elem.text:
                    properties[name] = val_elem.text.strip()
            elif tag == "SimpleData":
                name = child.attrib.get("name")
                if name and child.text:
                    properties[name] = child.text.strip()

    def _extract_geometry(self, elem: ET.Element) -> Optional[Dict[str, Any]]:
        """Look for Point, LineString, Polygon, MultiGeometry within the Placemark."""
        for child in elem:
            tag = self._strip_namespace(child.tag)

            if tag == "Point":
                coords_elem = self._find_descendant_by_tag(child, "coordinates")
                if coords_elem is not None and coords_elem.text:
                    parsed_coords = self._parse_coordinates(coords_elem.text)
                    if parsed_coords:
                        return {"type": "Point", "coordinates": parsed_coords[0]}

            elif tag == "LineString":
                coords_elem = self._find_descendant_by_tag(child, "coordinates")
                if coords_elem is not None and coords_elem.text:
                    coords = self._parse_coordinates(coords_elem.text)
                    if coords:
                        return {"type": "LineString", "coordinates": coords}

            elif tag == "Polygon":
                polygon_coords = self._parse_polygon_element(child)
                if polygon_coords:
                    return {"type": "Polygon", "coordinates": polygon_coords}

            elif tag == "MultiGeometry":
                return self._parse_multi_geometry(child)

        return None

    def _parse_polygon_element(self, poly_elem: ET.Element) -> Optional[List[List[List[float]]]]:
        """Parse outer and inner boundary linear rings for a Polygon."""
        rings: List[List[List[float]]] = []

        # Outer boundary
        for child in poly_elem:
            tag = self._strip_namespace(child.tag)
            if tag == "outerBoundaryIs":
                coords_elem = self._find_descendant_by_tag(child, "coordinates")
                if coords_elem is not None and coords_elem.text:
                    outer = self._parse_coordinates(coords_elem.text)
                    if outer:
                        if outer[0] != outer[-1]:
                            outer.append(outer[0])
                        rings.append(outer)

        if not rings:
            return None

        # Inner boundaries (holes)
        for child in poly_elem:
            tag = self._strip_namespace(child.tag)
            if tag == "innerBoundaryIs":
                coords_elem = self._find_descendant_by_tag(child, "coordinates")
                if coords_elem is not None and coords_elem.text:
                    inner = self._parse_coordinates(coords_elem.text)
                    if inner:
                        if inner[0] != inner[-1]:
                            inner.append(inner[0])
                        rings.append(inner)

        return rings

    def _parse_multi_geometry(self, multi_elem: ET.Element) -> Optional[Dict[str, Any]]:
        """Parse MultiGeometry element into MultiPolygon, MultiLineString, MultiPoint, or GeometryCollection."""
        sub_geometries: List[Dict[str, Any]] = []

        for child in multi_elem:
            tag = self._strip_namespace(child.tag)
            if tag == "Polygon":
                p_coords = self._parse_polygon_element(child)
                if p_coords:
                    sub_geometries.append({"type": "Polygon", "coordinates": p_coords})
            elif tag == "LineString":
                c_elem = self._find_descendant_by_tag(child, "coordinates")
                if c_elem is not None and c_elem.text:
                    l_coords = self._parse_coordinates(c_elem.text)
                    if l_coords:
                        sub_geometries.append({"type": "LineString", "coordinates": l_coords})
            elif tag == "Point":
                c_elem = self._find_descendant_by_tag(child, "coordinates")
                if c_elem is not None and c_elem.text:
                    pt_coords = self._parse_coordinates(c_elem.text)
                    if pt_coords:
                        sub_geometries.append({"type": "Point", "coordinates": pt_coords[0]})

        if not sub_geometries:
            return None

        types = {g["type"] for g in sub_geometries}
        if len(types) == 1:
            geom_type = list(types)[0]
            if geom_type == "Polygon":
                return {
                    "type": "MultiPolygon",
                    "coordinates": [g["coordinates"] for g in sub_geometries]
                }
            elif geom_type == "LineString":
                return {
                    "type": "MultiLineString",
                    "coordinates": [g["coordinates"] for g in sub_geometries]
                }
            elif geom_type == "Point":
                return {
                    "type": "MultiPoint",
                    "coordinates": [g["coordinates"] for g in sub_geometries]
                }

        return {
            "type": "GeometryCollection",
            "geometries": sub_geometries
        }
