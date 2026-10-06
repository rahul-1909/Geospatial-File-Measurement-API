import pytest
from shapely.geometry import Point, Polygon, LineString
from app.services.crs_service import CRSService


def test_is_geographic():
    assert CRSService.is_geographic("EPSG:4326") is True
    assert CRSService.is_geographic("WGS84") is True
    assert CRSService.is_geographic("EPSG:3857") is False  # Web Mercator is projected
    assert CRSService.is_geographic("EPSG:32618") is False  # UTM Zone 18N is projected


def test_utm_zone_selection_new_york():
    # New York City: lon ~ -74.0, lat ~ 40.7 -> UTM Zone 18N -> EPSG:32618
    ny_poly = Polygon([
        (-74.01, 40.71),
        (-74.00, 40.71),
        (-74.00, 40.72),
        (-74.01, 40.72),
        (-74.01, 40.71)
    ])
    utm_crs = CRSService.determine_optimal_projected_crs(ny_poly, "EPSG:4326")
    assert utm_crs == "EPSG:32618"


def test_utm_zone_selection_southern_hemisphere():
    # Sydney, Australia: lon ~ 151.2, lat ~ -33.8 -> UTM Zone 56S -> EPSG:32756
    sydney_poly = Polygon([
        (151.20, -33.86),
        (151.21, -33.86),
        (151.21, -33.85),
        (151.20, -33.85),
        (151.20, -33.86)
    ])
    utm_crs = CRSService.determine_optimal_projected_crs(sydney_poly, "EPSG:4326")
    assert utm_crs == "EPSG:32756"


def test_utm_zone_selection_london():
    # London: lon ~ -0.12, lat ~ 51.5 -> UTM Zone 30N or 31N -> EPSG:32630
    london_line = LineString([(-0.12, 51.50), (-0.10, 51.52)])
    utm_crs = CRSService.determine_optimal_projected_crs(london_line, "EPSG:4326")
    assert utm_crs in ("EPSG:32630", "EPSG:32631")


def test_reproject_geometry_metric_units():
    # 0.01 degree square in NYC
    ny_poly = Polygon([
        (-74.01, 40.71),
        (-74.00, 40.71),
        (-74.00, 40.72),
        (-74.01, 40.72),
        (-74.01, 40.71)
    ])
    # In geographic degrees, area is 0.0001 square degrees (invalid for metric measurements)
    deg_area = ny_poly.area
    assert abs(deg_area - 0.0001) < 1e-6

    # Reproject to UTM Zone 18N (EPSG:32618)
    proj_geom = CRSService.reproject_geometry(ny_poly, "EPSG:4326", "EPSG:32618")
    metric_area = proj_geom.area

    # In UTM meters, a 0.01 deg x 0.01 deg box at 40.7° lat is roughly ~840m x ~1110m ~ 930,000 m²
    assert 800_000 < metric_area < 1_100_000


def test_projected_input_in_feet_converted_to_metric():
    # NYC in State Plane NY Long Island (US Survey Feet, EPSG:2263)
    # Centroid ~ (985000 ft, 210000 ft) which corresponds to NYC lat 40.74, lon -74.00
    ny_poly_feet = Polygon([
        (984000, 209000),
        (986000, 209000),
        (986000, 211000),
        (984000, 211000),
        (984000, 209000)
    ])
    utm_crs = CRSService.determine_optimal_projected_crs(ny_poly_feet, "EPSG:2263")
    # Must correctly recognize that it's in feet, reproject centroid to WGS84, and pick UTM Zone 18N
    assert utm_crs == "EPSG:32618"


def test_geodesic_cross_check_accuracy():
    """
    Cross-checks UTM projected area calculation against the WGS84 ellipsoidal geodesic benchmark (Karney algorithm).
    Verifies that UTM scale distortion is minimal (within expected ~0.1% tolerance).
    """
    import pyproj

    poly = Polygon([
        (-74.0060, 40.7128),
        (-74.0040, 40.7128),
        (-74.0040, 40.7145),
        (-74.0060, 40.7145),
        (-74.0060, 40.7128)
    ])

    # 1. UTM projected calculation
    proj_geom = CRSService.reproject_geometry(poly, "EPSG:4326", "EPSG:32618")
    area_utm = proj_geom.area

    # 2. Ellipsoidal geodesic benchmark
    geod = pyproj.Geod(ellps="WGS84")
    area_geodesic, _ = geod.geometry_area_perimeter(poly)
    area_geodesic = abs(area_geodesic)

    # Relative error should be well under 0.15% (here ~0.063%)
    rel_error = abs(area_utm - area_geodesic) / area_geodesic
    assert rel_error < 0.0015
    assert 31800 < area_utm < 32000
