import pytest
from pathlib import Path
from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert ".kml" in data["supported_formats"]
    assert ".zip" in data["supported_formats"]


def test_upload_kml_file(client: TestClient, sample_data_dir: Path):
    kml_path = sample_data_dir / "sample_polygons.kml"
    with open(kml_path, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": ("sample_polygons.kml", f, "application/vnd.google-earth.kml+xml")}
        )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["filename"] == "sample_polygons.kml"
    assert data["feature_count"] == 2
    assert data["crs"] == "EPSG:4326"
    assert data["status"] == "COMPLETED"


def test_upload_shapefile_zip(client: TestClient, sample_data_dir: Path):
    zip_path = sample_data_dir / "sample_parcels.zip"
    with open(zip_path, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": ("sample_parcels.zip", f, "application/zip")}
        )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["filename"] == "sample_parcels.zip"
    assert data["feature_count"] == 2
    assert data["crs"] == "EPSG:4326"
    assert data["status"] == "COMPLETED"


def test_get_file_info(client: TestClient, sample_data_dir: Path):
    # First upload
    kml_path = sample_data_dir / "sample_linestrings.kml"
    with open(kml_path, "rb") as f:
        upload_resp = client.post(
            "/api/files/",
            files={"file": ("sample_linestrings.kml", f, "application/vnd.google-earth.kml+xml")}
        )
    file_id = upload_resp.json()["id"]

    # Now get file info
    info_resp = client.get(f"/api/files/{file_id}/")
    assert info_resp.status_code == 200
    info_data = info_resp.json()

    # Verify exact required schema
    assert info_data["id"] == file_id
    assert info_data["filename"] == "sample_linestrings.kml"
    assert info_data["feature_count"] == 2
    assert info_data["crs"] == "EPSG:4326"
    assert info_data["status"] == "COMPLETED"


def test_get_file_measurements(client: TestClient, sample_data_dir: Path):
    # Upload mixed dataset (polygons, lines, points)
    kml_path = sample_data_dir / "sample_mixed.kml"
    with open(kml_path, "rb") as f:
        upload_resp = client.post(
            "/api/files/",
            files={"file": ("sample_mixed.kml", f, "application/vnd.google-earth.kml+xml")}
        )
    file_id = upload_resp.json()["id"]

    # Fetch measurements
    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()

    assert meas_data["id"] == file_id
    assert meas_data["status"] == "COMPLETED"
    assert "summary" in meas_data
    assert meas_data["summary"]["total_features"] == 3
    assert meas_data["summary"]["total_area_sq_meters"] > 0
    assert meas_data["summary"]["total_length_meters"] > 0

    features = meas_data["features"]
    assert len(features) == 3

    # Check Polygon feature has area and metric projected CRS
    poly_feats = [f for f in features if f["geometry_type"] == "Polygon"]
    assert len(poly_feats) == 1
    assert poly_feats[0]["measurements"]["area"]["sq_meters"] > 0
    assert poly_feats[0]["measurements"]["projected_crs_used"] is not None

    # Check LineString feature has length
    line_feats = [f for f in features if f["geometry_type"] == "LineString"]
    assert len(line_feats) == 1
    assert line_feats[0]["measurements"]["length"]["meters"] > 0
    assert line_feats[0]["measurements"]["projected_crs_used"] is not None

    # Check Point feature has NO_MEASUREMENT_REQUIRED
    point_feats = [f for f in features if f["geometry_type"] == "Point"]
    assert len(point_feats) == 1
    assert point_feats[0]["measurements"]["status"] == "NO_MEASUREMENT_REQUIRED"
    assert point_feats[0]["measurements"]["area"] is None
    assert point_feats[0]["measurements"]["length"] is None


def test_list_and_delete_files(client: TestClient, sample_data_dir: Path):
    kml_path = sample_data_dir / "sample_points.kml"
    with open(kml_path, "rb") as f:
        upload_resp = client.post(
            "/api/files/",
            files={"file": ("sample_points.kml", f, "application/vnd.google-earth.kml+xml")}
        )
    file_id = upload_resp.json()["id"]

    # List files
    list_resp = client.get("/api/files/")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # Delete file
    del_resp = client.delete(f"/api/files/{file_id}/")
    assert del_resp.status_code == 204

    # Verify not found after deletion
    get_resp = client.get(f"/api/files/{file_id}/")
    assert get_resp.status_code == 404


def test_unsupported_file_extension(client: TestClient, tmp_path: Path):
    dummy_txt = tmp_path / "test.txt"
    dummy_txt.write_text("Hello world", encoding="utf-8")

    with open(dummy_txt, "rb") as f:
        resp = client.post(
            "/api/files/",
            files={"file": ("test.txt", f, "text/plain")}
        )
    assert resp.status_code == 400
    assert "unsupported format" in resp.json()["detail"].lower()


def test_nonexistent_file_404(client: TestClient):
    resp = client.get("/api/files/nonexistent_id_999/")
    assert resp.status_code == 404
