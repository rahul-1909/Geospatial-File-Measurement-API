# Geospatial File Measurement API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-28%20Passed-success.svg)](tests/)

A production-grade backend service built with **FastAPI** that accepts geospatial files (**ESRI Shapefile `.zip`** and **OGC KML/KMZ**), extracts geometric features and attributes, transforms geographic coordinate systems to optimal metric projections, and calculates precise real-world measurements (**Polygon Area** and **LineString Length**).

---

## Table of Contents
- [Problem Statement](#problem-statement)
- [Key Features](#key-features)
- [Architecture & System Design](#architecture--system-design)
  - [1. Application Structure](#1-application-structure)
  - [2. File-Processing Flow](#2-file-processing-flow)
  - [3. Measurement Calculation Flow](#3-measurement-calculation-flow)
  - [4. CRS Handling Strategy & UTM Analysis](#4-crs-handling-strategy--utm-analysis)
- [Why UTM vs. Equal-Area vs. Geodesic Calculations?](#why-utm-vs-equal-area-vs-geodesic-calculations)
- [Technical Decisions & Alternatives Considered](#technical-decisions--alternatives-considered)
- [API Reference & Verified Examples](#api-reference--verified-examples)
  - [Upload Geospatial File (`POST /api/files/`)](#1-upload-geospatial-file)
  - [Get File Information (`GET /api/files/{id}/`)](#2-get-file-information)
  - [Get File Measurements (`GET /api/files/{id}/measurements/`)](#3-get-file-measurements)
  - [List Uploaded Files (`GET /api/files/`)](#4-list-uploaded-files)
  - [Delete File (`DELETE /api/files/{id}/`)](#5-delete-file)
  - [Health Check (`GET /api/health/`)](#6-health-check)
- [Limitations & Edge Cases](#limitations--edge-cases)
- [Local Setup & Execution](#local-setup--execution)
- [Running via Docker](#running-via-docker)
- [Testing & Geodesic Cross-Check](#testing--geodesic-cross-check)
- [Sample Data Fixtures](#sample-data-fixtures)
- [Learnings & Future Scope](#learnings--future-scope)
- [Repository](#repository)

---

## Problem Statement

Build a backend service using FastAPI that accepts a geospatial file (`.zip` containing a Shapefile, or `.kml`), processes the features within it, and returns measurement information:
- **Polygon**: Calculate Area ($m^2$, $km^2$, hectares, acres).
- **LineString**: Calculate Length ($m$, $km$, miles, feet).
- **Point**: No measurement required (graceful status).
- **CRS Handling**: Transform geographic coordinates (e.g. `EPSG:4326` in degrees) to an appropriate projected coordinate system in meters before calculating measurements.

---

## Key Features

- **Multi-Format Ingestion**: Supports `.zip` Shapefile archives (`.shp`, `.shx`, `.dbf`, `.prj`) and `.kml` / `.kmz` files.
- **Strict CRS & Metric Integrity**: Never performs planar math on spherical degree units (`EPSG:4326`). Dynamically determines and reprojects features to the optimal local **Universal Transverse Mercator (UTM)** zone or metric projection.
- **Missing `.prj` & Imperial Units Resilience**: Detects missing Shapefile `.prj` components and returns explicit non-fatal warnings rather than silently assuming projections. Converts projected CRSs in US Survey Feet to metric UTM seamlessly.
- **Comprehensive Measurement Output**: Computes surface area (with polygon hole exclusion) and linestring length, reporting results in multiple standard metric and imperial units.
- **Topological Robustness**: Detects non-simple and self-intersecting geometries (e.g. bowtie polygons) and applies automated topology repair (`shapely.make_valid`) without crashing.
- **Security-Hardened File Handling**:
  - **Zip Slip Defense**: Canonical path validation prevents directory traversal attacks during zip unpacking.
  - **Zip Bomb Guard**: Uncompressed size thresholds (250 MB) and compression ratio checks (>100:1) eliminate decompression denial-of-service vulnerabilities.
  - **XML Bomb Protection**: Uses `defusedxml` to parse KML documents safely against entity expansion attacks (Billion Laughs).
  - **Stream Size Throttling**: Restricts upload sizes via streaming buffers to mitigate memory exhaustion.
- **Clean Persistence & Metadata**: Backed by SQLite via SQLAlchemy for fast, zero-dependency persistence across sessions.

---

## Architecture & System Design

### 1. Application Structure

The project follows a clean, modular, layered architecture separating domain logic, persistence, and REST interfaces:

```
Geospatial-File-Measurement-API/
├── app/
│   ├── main.py                     # FastAPI application entrypoint, CORS, lifespan & exceptions
│   ├── api/
│   │   └── v1/
│   │       ├── router.py           # V1 route aggregator
│   │       └── endpoints/
│   │           ├── files.py        # File upload, status, measurement endpoints
│   │           └── health.py       # Health check endpoint
│   ├── core/
│   │   ├── config.py               # Application settings (Pydantic Settings)
│   │   └── exceptions.py           # Custom exception definitions and HTTP status codes
│   ├── db/
│   │   ├── session.py              # SQLite database session and engine setup
│   │   └── models.py               # FileRecord and FeatureRecord ORM models
│   ├── schemas/
│   │   ├── file.py                 # FileInfoResponse, FileListResponse schemas (with warnings)
│   │   └── measurement.py          # FeatureMeasurement, MeasurementSummary schemas
│   ├── services/
│   │   ├── crs_service.py          # CRS identification, optimal UTM zone selection, reprojection
│   │   ├── measurement_service.py  # Area and length calculation engine
│   │   ├── parser_service.py       # Parser dispatcher
│   │   ├── file_service.py         # File ingestion orchestration and persistence
│   │   └── parsers/
│   │       ├── base.py             # Abstract base parser and data models
│   │       ├── shapefile_parser.py # Shapefile (.zip) parser with .prj parsing & warnings
│   │       └── kml_parser.py       # Defused XML KML/KMZ parser (recursive tree traversal)
│   └── utils/
│       └── file_utils.py           # Zip Slip & Zip Bomb defense, temp dir context managers
├── sample_data/                    # Sample Shapefile zip files and KML files
│   ├── create_sample_shapefiles.py # Generator for valid test shapefiles
│   ├── sample_parcels.zip          # Zipped Polygon Shapefile with attributes and .prj
│   ├── sample_roads.zip            # Zipped LineString Shapefile with attributes and .prj
│   ├── sample_polygons.kml         # Polygons (including parcel with inner reservoir hole)
│   ├── sample_linestrings.kml      # Infrastructure LineStrings
│   ├── sample_points.kml           # Geodetic benchmark Points
│   └── sample_mixed.kml            # Combined Polygons, Lines, and Points
├── tests/                          # Automated test suite (28 passing tests)
│   ├── conftest.py                 # Pytest fixtures and isolated in-memory test database
│   ├── test_api.py                 # Integration tests for all endpoints and status codes
│   ├── test_crs.py                 # Tests for UTM zone selection, projected feet, and geodesic cross-check
│   ├── test_measurements.py        # Tests for area/length/point calculations and auto-repair
│   └── test_parsers.py             # Tests for KML, Shapefiles, missing .prj warning, and zip bomb guard
├── Dockerfile                      # Production container image
├── docker-compose.yml              # Multi-container orchestration
├── requirements.txt                # Production dependencies
└── README.md                       # Comprehensive documentation
```

---

### 2. File-Processing Flow

```
[Client Upload]
       │
       ▼
[FastAPI Endpoint: POST /api/files/]
       │
       ▼
[Sanitize Filename & Validate Extension (.zip, .kml, .kmz)]
       │
       ▼
[Stream to Disk with 100MB Size Limit Check]
       │
       ▼
[Parser Dispatcher]
  ├── .zip  ──► [ShapefileParser]: Safe Unpack (Zip Slip & Bomb checks)
  │                                Read .prj (or flag warning if missing) ──► Read Shapes & DBF
  └── .kml  ──► [KMLParser]: DefusedXML ──► Recursive Placemark extraction (Rings, Lines, Points)
       │
       ▼
[Feature Extraction: GeoJSON Geometry + Attributes + CRS + Warnings]
       │
       ▼
[CRS Service: Determine Optimal Metric Projection]
  ├── If Geographic (EPSG:4326): Compute Centroid (lon/lat) ──► Select UTM Zone
  ├── If Projected in Meters: Retain source projected CRS
  └── If Projected in Feet (e.g. State Plane): Convert centroid to WGS84 ──► Select UTM Zone
       │
       ▼
[Measurement Engine: Reproject to Metric CRS ──► Compute Area (m²) / Length (m)]
       │
       ▼
[Store FileRecord & FeatureRecords in SQLite DB]
       │
       ▼
[Return FileInfoResponse (ID, Filename, Feature Count, CRS, Status: COMPLETED, Warnings)]
```

---

### 3. Measurement Calculation Flow

```
For each extracted feature:
  │
  ├── Geometry is Point / MultiPoint:
  │     └── Status = NO_MEASUREMENT_REQUIRED (area=None, length=None)
  │
  ├── Geometry is Polygon / MultiPolygon:
  │     ├── Topological Validation (auto-repair invalid bowties via shapely.make_valid)
  │     ├── Determine Optimal Metric Projected CRS (UTM Zone or retain source metric CRS)
  │     ├── Reproject Geometry to metric coordinates
  │     ├── Calculate Area = projected_geom.area (m²) [automatically subtracts inner holes]
  │     └── Convert to km², hectares, acres
  │
  ├── Geometry is LineString / MultiLineString:
  │     ├── Determine Optimal Metric Projected CRS (UTM Zone or retain source metric CRS)
  │     ├── Reproject Geometry to metric coordinates
  │     ├── Calculate Length = projected_geom.length (m)
  │     └── Convert to km, miles, feet
  │
  └── Unsupported Geometry (e.g. GeometryCollection):
        └── Handled gracefully with Status = UNSUPPORTED_GEOMETRY (no crash)
```

---

### 4. CRS Handling Strategy & UTM Analysis

Geographic coordinates (such as **EPSG:4326 / WGS 84**) measure positions in angular units (degrees of latitude and longitude). Directly computing areas or distances on degrees using planar Euclidean formulas produces invalid results because degrees do not represent uniform physical distances.

#### Dynamic Projection Algorithm
1. **Source CRS Resolution**:
   - For **Shapefiles**: Parses the `.prj` file WKT definition using `pyproj.CRS.from_wkt()`. If the `.prj` file is missing, the service flags an explicit warning in the response (`warnings: [...]`) and marks `crs = "EPSG:4326 (assumed, missing .prj)"`.
   - For **KML**: The OGC KML standard specifies coordinates in `EPSG:4326` (WGS 84).
2. **Projected CRS Selection**:
   - If the source data is **already projected in meters** (e.g., existing UTM or metric national grids), the service retains the source CRS.
   - If the source data is **projected in non-metric units** (e.g., US Survey Feet in State Plane EPSG:2263), the service converts the feature centroid to WGS84 degrees first to reliably locate the optimal UTM zone.
   - If the source data is **geographic (degrees)**, the centroid $(\text{lon}, \text{lat})$ is computed directly.
3. **Universal Transverse Mercator (UTM) Zone Computation**:
   $$\text{zone} = \left\lfloor \frac{\text{lon} + 180.0}{6.0} \right\rfloor + 1 \quad (1 \le \text{zone} \le 60)$$
   - **Northern Hemisphere** ($\text{lat} \ge 0$): `EPSG:32600 + zone`
   - **Southern Hemisphere** ($\text{lat} < 0$): `EPSG:32700 + zone`
   - **Polar Latitudes** ($|\text{lat}| > 84^\circ$): Universal Polar Stereographic (`EPSG:32661` North / `EPSG:32761` South).
4. **Reprojection**:
   - Transforms geometries using `pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)` with `shapely.ops.transform`.

---

## Why UTM vs. Equal-Area vs. Geodesic Calculations?

*A critical architectural consideration in geospatial engineering:*

| Projection / Method | Mathematical Property | Strengths | Tradeoffs | Why / Why Not Selected |
| :--- | :--- | :--- | :--- | :--- |
| **Universal Transverse Mercator (UTM)** *(Chosen)* | **Conformal** (Preserves local angles and shapes) | Standardized worldwide 6° zones, globally recognized EPSG codes, minimal scale distortion ($\approx 0.05\% - 0.1\%$). | Not strictly equal-area; slight scale factor variation ($k_0 = 0.9996$ at central meridian to $\approx 1.0004$ at boundaries). | **Selected**: Meets the requirement to transform geometry to a projected coordinate system before calculation, using a standard worldwide grid. |
| **Equal-Area Projections** (e.g., Albers Equal Area, Lambert Azimuthal) | **Equivalent** (Preserves true area exactly) | Area calculations on 2D planes have zero projection distortion. | Distorts local angles and distances; requires customizing standard parallels for every local jurisdiction. | **Alternative considered**: Better for continental polygon statistical summaries, but requires dynamic non-standard parallel configuration per feature. |
| **Direct Geodesic Math** (e.g., Karney's algorithm via `pyproj.Geod`) | **Ellipsoidal** (Calculates along WGS84 ellipsoid surface) | Perfect true-surface geodesic distance and area with zero projection error. | Operates directly on the 3D ellipsoid without producing a 2D projected coordinate system. | **Benchmark used**: Used in our test suite (`test_geodesic_cross_check_accuracy`) to verify that UTM projection error remains $< 0.1\%$. |

> **Summary**: UTM is **conformal**, not equal-area or strictly distance-preserving. However, across a single 6° UTM zone, area distortion is negligible for parcel/infrastructure measurement ($\approx 0.06\%$ in our New York benchmark: $31,883.57\text{ m}^2$ UTM vs $31,903.54\text{ m}^2$ geodesic).

---

## Technical Decisions & Alternatives Considered

| Decision | Chosen Solution | Alternatives Considered | Rationale |
| :--- | :--- | :--- | :--- |
| **Framework** | **FastAPI** | Django + DRF | FastAPI provides native async request handling, high throughput, lightweight footprint, automatic OpenAPI/Swagger documentation, and Pydantic v2 data validation. |
| **Shapefile Parser** | **`pyshp` (PyShp)** | GDAL / Fiona | `pyshp` is 100% pure Python, avoiding fragile external C-library compilation dependencies (`gdal-bin`, `libgdal`) across diverse OS platforms while providing complete shape & DBF access. |
| **Geometry Math** | **`shapely` 2.x** | GEOS C API / GeoDjango | Shapely 2.0+ is built on vectorized C GEOS internals with Pythonic bindings, topology validation (`make_valid`, `explain_validity`), and coordinate reprojection. |
| **CRS & Projections** | **`pyproj` (PROJ 9)** | Geodesic Haversine / Manual math | `pyproj` is the industry standard for coordinate transformations and supports all EPSG authorities, WKT parsing, and ellipsoid models. |
| **XML Security** | **`defusedxml`** | Standard `xml.etree` / `lxml` | Standard XML parsers are vulnerable to XML entity expansion and Billion Laughs denial-of-service attacks. `defusedxml` neutralizes these risks. |
| **Persistence** | **SQLite + SQLAlchemy** | In-memory dict / PostgreSQL | SQLite requires zero infrastructure setup, stores file and measurement state permanently across server restarts, and provides a clean repository pattern. |

---

## API Reference & Verified Examples

Interactive API documentation is automatically accessible at:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

### 1. Upload Geospatial File
Uploads and processes a `.zip` Shapefile or `.kml` file.

- **URL**: `POST /api/files/`
- **Content-Type**: `multipart/form-data`
- **Request Body**: `file` (Binary file data)

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/files/" \
  -H "accept: application/json" \
  -F "file=@sample_data/sample_polygons.kml"
```

**Real Verified Output (`201 Created`):**
```json
{
  "id": "95c9668ee912",
  "filename": "sample_polygons.kml",
  "feature_count": 2,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "file_type": "KML",
  "file_size_bytes": 1928,
  "created_at": "2026-10-06T18:15:06.453439",
  "error_message": null,
  "warnings": []
}
```

---

### 2. Get File Information
Retrieves metadata and processing status for an uploaded file.

- **URL**: `GET /api/files/{id}/`
- **Response Format**: Matches the exact specification.

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/files/95c9668ee912/"
```

**Real Verified Output (`200 OK`):**
```json
{
  "id": "95c9668ee912",
  "filename": "sample_polygons.kml",
  "feature_count": 2,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "file_type": "KML",
  "file_size_bytes": 1928,
  "created_at": "2026-10-06T18:15:06.453439",
  "error_message": null,
  "warnings": []
}
```

---

### 3. Get File Measurements
Returns calculated measurements (area, length, projected CRS used) for every feature, along with aggregate summary statistics.

- **URL**: `GET /api/files/{id}/measurements/`

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/files/95c9668ee912/measurements/"
```

**Real Verified Output (`200 OK`):**
```json
{
  "id": "95c9668ee912",
  "filename": "sample_polygons.kml",
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "summary": {
    "total_features": 2,
    "geometry_type_breakdown": {
      "Polygon": 2
    },
    "total_area_sq_meters": 256947.6703,
    "total_area_sq_km": 0.256948,
    "total_length_meters": 0.0,
    "total_length_km": 0.0
  },
  "features": [
    {
      "feature_id": 1,
      "feature_index": 0,
      "identifier": "Parcel Alpha",
      "geometry_type": "Polygon",
      "crs": "EPSG:4326",
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [-74.006, 40.7128],
            [-74.004, 40.7128],
            [-74.004, 40.7145],
            [-74.006, 40.7145],
            [-74.006, 40.7128]
          ]
        ]
      },
      "properties": {
        "name": "Parcel Alpha",
        "description": "Commercial agricultural field",
        "zoning": "Agricultural",
        "owner": "Apex Agri Corp"
      },
      "measurements": {
        "area": {
          "sq_meters": 31883.5668,
          "sq_kilometers": 0.031884,
          "hectares": 3.1884,
          "acres": 7.8786
        },
        "length": null,
        "projected_crs_used": "EPSG:32618",
        "status": "SUCCESS",
        "notes": "Area calculated in metric projected CRS (EPSG:32618)."
      }
    },
    {
      "feature_id": 2,
      "feature_index": 1,
      "identifier": "Parcel Beta (With Inner Reservoir Hole)",
      "geometry_type": "Polygon",
      "crs": "EPSG:4326",
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [-74.01, 40.71],
            [-74.005, 40.71],
            [-74.005, 40.715],
            [-74.01, 40.715],
            [-74.01, 40.71]
          ],
          [
            [-74.008, 40.712],
            [-74.007, 40.712],
            [-74.007, 40.713],
            [-74.008, 40.713],
            [-74.008, 40.712]
          ]
        ]
      },
      "properties": {
        "name": "Parcel Beta (With Inner Reservoir Hole)",
        "description": "Residential tract with protected lake hole",
        "zoning": "Residential-R2"
      },
      "measurements": {
        "area": {
          "sq_meters": 225064.1035,
          "sq_kilometers": 0.225064,
          "hectares": 22.5064,
          "acres": 55.6146
        },
        "length": null,
        "projected_crs_used": "EPSG:32618",
        "status": "SUCCESS",
        "notes": "Area calculated in metric projected CRS (EPSG:32618)."
      }
    }
  ]
}
```

---

### 4. List Uploaded Files
Lists all uploaded files with pagination.

- **URL**: `GET /api/files/?skip=0&limit=50`

---

### 5. Delete File
Deletes a file record, its associated features, and cleans up uploaded data from disk.

- **URL**: `DELETE /api/files/{id}/`
- **Response**: `204 No Content`

---

### 6. Health Check
System diagnostic endpoint.

- **URL**: `GET /api/health/`

---

## Limitations & Edge Cases

An honest overview of system behavior on complex boundary cases:

1. **Synchronous Request Processing**:
   File parsing and measurement calculation are executed synchronously within the HTTP request lifecycle. The database records intermediate states (`PENDING` and `PROCESSING`) to support future asynchronous worker architectures (e.g., Celery/RQ + Redis), but in the current release, responses complete synchronously.
2. **Missing `.prj` Handling**:
   Shapefiles without a `.prj` coordinate file default to `EPSG:4326 (assumed, missing .prj)` and populate a clear non-fatal message in the `warnings` list. If the coordinates were already in a projected system (e.g. State Plane), planar measurements will be distorted.
3. **Multi-Zone & Antimeridian Features**:
   Features spanning across multiple 6° UTM zones or crossing the 180° antimeridian are projected using the UTM zone of their centroid. At zone boundaries, scale distortion increases ($>0.4\%$). For global or continental datasets, a global equal-area projection or geodesic splitting is recommended.
4. **Z-Coordinate (Elevation) Handling**:
   3D coordinates $(x, y, z)$ present in KML or Shapefiles preserve their $Z$-values in the output GeoJSON, but area and length calculations represent the 2D planimetric horizontal footprint. True 3D surface area across sloped terrain requires a digital elevation model (DEM).
5. **Multiple Shapefiles per Zip**:
   If an uploaded `.zip` contains multiple `.shp` datasets, the primary shapefile is processed and a notification is added to `warnings`.

---

## Local Setup & Execution

### Prerequisites
- Python 3.11, 3.12, or 3.14
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/rahul-1909/Geospatial-File-Measurement-API.git
cd Geospatial-File-Measurement-API
```

### 2. Create and Activate a Virtual Environment
```bash
# On Linux / macOS:
python3 -m venv venv
source venv/bin/activate

# On Windows (PowerShell):
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Application
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The API is now running at `http://localhost:8000`. You can visit `http://localhost:8000/docs` to test endpoints interactively.

---

## Running via Docker

### Using Docker Compose
```bash
docker-compose up --build
```

### Using Plain Docker
```bash
docker build -t geospatial-api .
docker run -p 8000:8000 geospatial-api
```

---

## Testing & Geodesic Cross-Check

The test suite contains 28 automated tests covering:
- Unit tests for KML & Shapefile parsers (including inner ring holes and attributes).
- Missing `.prj` warning detection and multi-layer notification.
- Zip bomb guard tests (compression ratio and size explosion).
- Projected input CRS in feet (State Plane EPSG:2263) converted to metric UTM.
- **Geodesic Cross-Check Test**: Verifies that UTM projected area is within $0.15\%$ of the Karney ellipsoidal geodesic benchmark (`pyproj.Geod(ellps="WGS84")`).
- Integration tests for all endpoints and HTTP status codes (200, 201, 204, 400, 404, 422).

Run all tests:
```bash
pytest -v
```

---

## Sample Data Fixtures

The repository includes ready-to-test sample datasets in `sample_data/`:
- `sample_parcels.zip`: Zipped Shapefile containing multi-lot polygons with zoning attributes and `.prj` file.
- `sample_roads.zip`: Zipped Shapefile containing roadway linestrings with speed limit and lane attributes.
- `sample_polygons.kml`: KML containing parcels, including a polygon with an interior hole (reservoir).
- `sample_linestrings.kml`: KML containing utility transmission pipeline and fiber optic lines.
- `sample_points.kml`: KML containing geodetic survey benchmarks.
- `sample_mixed.kml`: KML combining park polygons, trail routes, and gateway landmarks.
- `create_sample_shapefiles.py`: Standalone script to generate sample shapefile archives.

---

## Learnings & Future Scope

### Key Learnings
1. **Coordinate Geometry Nuances & UTM Scale Factors**:
   UTM is conformal, meaning it preserves infinitesimal angles and shapes, but scale factors vary from $k_0 = 0.9996$ at the central meridian to $\approx 1.0004$ at boundaries. Understanding when to use UTM vs equal-area projections vs geodesic calculations is essential for geospatial software engineering.
2. **Defensive Geospatial Parsing**:
   Real-world GIS files often omit `.prj` files, contain self-intersecting geometries, or use non-metric linear units (such as US Survey Feet). Detecting and handling these cases gracefully prevents silent calculation errors.
3. **Archive & XML Security**:
   Extracting user-submitted archives requires guarding against path traversal (Zip Slip) and decompression bombs, while parsing KML documents demands protection against XML entity attacks (`defusedxml`).

### Future Scope
- **Asynchronous Task Workers**: Decouple file ingestion from processing using Celery/RQ + Redis for multi-gigabyte datasets with webhook notifications.
- **Elevation & 3D Surface Measurements**: Expand support for 3D coordinates ($Z$ elevation) and digital elevation models (DEM) to calculate true surface area across topography.
- **GeoPackage & Cloud-Optimized Formats**: Add native parsers for OGC GeoPackage (`.gpkg`), FlatGeobuf, and Cloud-Optimized Point Clouds (COPC).
- **Direct GeoJSON Export & Map Visualization**: Add an export endpoint (`GET /api/files/{id}/geojson`) and an embedded interactive Leaflet or MapLibre viewer to inspect feature geometries visually in the browser.

---

## Repository

- **GitHub Repository**: [https://github.com/rahul-1909/Geospatial-File-Measurement-API](https://github.com/rahul-1909/Geospatial-File-Measurement-API)
- **Author**: Rahul Teja Nalla ([rahul-1909](https://github.com/rahul-1909))
