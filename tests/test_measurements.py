import pytest
from app.services.measurement_service import MeasurementService


def test_polygon_area_calculation():
    # NYC polygon (~170m x ~190m box)
    geom_dict = {
        "type": "Polygon",
        "coordinates": [[
            [-74.0060, 40.7128],
            [-74.0040, 40.7128],
            [-74.0040, 40.7145],
            [-74.0060, 40.7145],
            [-74.0060, 40.7128]
        ]]
    }
    details, area_m2, length_m, proj_crs = MeasurementService.process_feature_measurement(
        geom_dict, "EPSG:4326"
    )

    assert details.status == "SUCCESS"
    assert area_m2 is not None
    assert area_m2 > 0
    assert length_m is None
    assert details.area is not None
    assert details.area.sq_meters > 0
    assert details.area.hectares > 0
    assert details.area.acres > 0
    assert proj_crs == "EPSG:32618"


def test_linestring_length_calculation():
    # NYC linestring
    geom_dict = {
        "type": "LineString",
        "coordinates": [
            [-74.0050, 40.7100],
            [-74.0030, 40.7120],
            [-74.0010, 40.7150]
        ]
    }
    details, area_m2, length_m, proj_crs = MeasurementService.process_feature_measurement(
        geom_dict, "EPSG:4326"
    )

    assert details.status == "SUCCESS"
    assert area_m2 is None
    assert length_m is not None
    assert length_m > 0
    assert details.length is not None
    assert details.length.meters > 0
    assert details.length.kilometers > 0
    assert proj_crs == "EPSG:32618"


def test_point_no_measurement_required():
    geom_dict = {
        "type": "Point",
        "coordinates": [-74.0060, 40.7128]
    }
    details, area_m2, length_m, proj_crs = MeasurementService.process_feature_measurement(
        geom_dict, "EPSG:4326"
    )

    assert details.status == "NO_MEASUREMENT_REQUIRED"
    assert area_m2 is None
    assert length_m is None
    assert details.area is None
    assert details.length is None


def test_unsupported_geometry_type_graceful():
    geom_dict = {
        "type": "GeometryCollection",
        "geometries": [
            {"type": "Point", "coordinates": [-74.0060, 40.7128]}
        ]
    }
    details, area_m2, length_m, proj_crs = MeasurementService.process_feature_measurement(
        geom_dict, "EPSG:4326"
    )

    # Must handle gracefully rather than crashing
    assert details.status in ("UNSUPPORTED_GEOMETRY", "SUCCESS")


def test_invalid_bowtie_polygon_handled_gracefully():
    # Bowtie self-intersecting polygon
    geom_dict = {
        "type": "Polygon",
        "coordinates": [[
            [0.0, 0.0],
            [1.0, 1.0],
            [1.0, 0.0],
            [0.0, 1.0],
            [0.0, 0.0]
        ]]
    }
    details, area_m2, length_m, proj_crs = MeasurementService.process_feature_measurement(
        geom_dict, "EPSG:4326"
    )

    # API handles it gracefully and auto-repairs without crashing
    assert details.status == "SUCCESS"
    assert details.area is not None
