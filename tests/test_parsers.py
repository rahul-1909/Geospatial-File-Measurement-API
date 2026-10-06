import pytest
from pathlib import Path
from app.services.parsers.kml_parser import KMLParser
from app.services.parsers.shapefile_parser import ShapefileParser
from app.core.exceptions import CorruptGeospatialFileError


def test_kml_parser_polygons(sample_data_dir: Path):
    parser = KMLParser()
    kml_file = sample_data_dir / "sample_polygons.kml"
    data = parser.parse(kml_file)

    assert data.file_type == "KML"
    assert data.crs == "EPSG:4326"
    assert len(data.features) == 2

    feat1 = data.features[0]
    assert feat1.geometry_type == "Polygon"
    assert feat1.identifier == "Parcel Alpha"
    assert feat1.properties.get("zoning") == "Agricultural"
    assert feat1.properties.get("owner") == "Apex Agri Corp"

    feat2 = data.features[1]
    assert feat2.geometry_type == "Polygon"
    # feat2 has an inner hole
    coords = feat2.geometry["coordinates"]
    assert len(coords) == 2  # outer boundary + inner boundary


def test_kml_parser_linestrings(sample_data_dir: Path):
    parser = KMLParser()
    kml_file = sample_data_dir / "sample_linestrings.kml"
    data = parser.parse(kml_file)

    assert len(data.features) == 2
    for feat in data.features:
        assert feat.geometry_type == "LineString"
        assert len(feat.geometry["coordinates"]) >= 2


def test_kml_parser_points(sample_data_dir: Path):
    parser = KMLParser()
    kml_file = sample_data_dir / "sample_points.kml"
    data = parser.parse(kml_file)

    assert len(data.features) == 2
    for feat in data.features:
        assert feat.geometry_type == "Point"
        assert len(feat.geometry["coordinates"]) == 2


def test_shapefile_parser_parcels_zip(sample_data_dir: Path):
    parser = ShapefileParser()
    zip_file = sample_data_dir / "sample_parcels.zip"
    data = parser.parse(zip_file)

    assert data.file_type == "SHAPEFILE_ZIP"
    assert data.crs == "EPSG:4326"
    assert len(data.features) == 2
    for feat in data.features:
        assert feat.geometry_type == "Polygon"
        assert "ID" in feat.properties
        assert "ZONING" in feat.properties


def test_shapefile_parser_roads_zip(sample_data_dir: Path):
    parser = ShapefileParser()
    zip_file = sample_data_dir / "sample_roads.zip"
    data = parser.parse(zip_file)

    assert len(data.features) == 2
    for feat in data.features:
        assert feat.geometry_type in ("LineString", "MultiLineString")
        assert "ROAD_ID" in feat.properties


def test_kml_parser_invalid_xml(tmp_path: Path):
    bad_kml = tmp_path / "corrupt.kml"
    bad_kml.write_text("<Document><unclosed_tag>", encoding="utf-8")
    parser = KMLParser()

    with pytest.raises(CorruptGeospatialFileError):
        parser.parse(bad_kml)
