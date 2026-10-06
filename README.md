# Geospatial File Measurement API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-24%20Passed-success.svg)](tests/)

A production-grade backend service built with **FastAPI** that accepts geospatial files (**ESRI Shapefile `.zip`** and **OGC KML/KMZ**), extracts geometric features and attributes, transforms geographic coordinate systems to optimal metric projections, and calculates precise real-world measurements (**Polygon Area** and **LineString Length**).

---

## Table of Contents
- [Problem Statement](#problem-statement)
- [Key Features](#key-features)
- [Architecture & System Design](#architecture--system-design)
  - [1. Application Structure](#1-application-structure)
  - [2. File-Processing Flow](#2-file-processing-flow)
  - [3. Measurement Calculation Flow](#3-measurement-calculation-flow)
  - [4. CRS Handling Strategy](#4-crs-handling-strategy)
- [Technical Decisions & Alternatives Considered](#technical-decisions--alternatives-considered)
- [API Reference & Examples](#api-reference--examples)
  - [Upload Geospatial File (`POST /api/files/`)](#1-upload-geospatial-file)
  - [Get File Information (`GET /api/files/{id}/`)](#2-get-file-information)
  - [Get File Measurements (`GET /api/files/{id}/measurements/`)](#3-get-file-measurements)
  - [List Uploaded Files (`GET /api/files/`)](#4-list-uploaded-files)
  - [Delete File (`DELETE /api/files/{id}/`)](#5-delete-file)
  - [Health Check (`GET /api/health/`)](#6-health-check)
- [Local Setup & Execution](#local-setup--execution)
- [Running via Docker](#running-via-docker)
- [Testing](#testing)
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
- **Comprehensive Measurement Output**: Computes surface area (with polygon hole exclusion) and linestring length, reporting results in multiple standard metric and imperial units.
- **Topological Robustness**: Detects non-simple and self-intersecting geometries (e.g. bowtie polygons) and applies automated topology repair (`shapely.make_valid`) without crashing.
- **Security-Hardened File Handling**:
  - **Zip Slip Defense**: Canonical path validation prevents directory traversal attacks during zip unpacking.
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
│   ├── main.py                     # FastAPI application entrypoint, CORS, exception handlers
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
│   │   ├── file.py                 # FileInfoResponse, FileListResponse schemas
│   │   └── measurement.py          # FeatureMeasurement, MeasurementSummary schemas
│   ├── services/
│   │   ├── crs_service.py          # CRS identification, optimal UTM zone selection, reprojection
│   │   ├── measurement_service.py  # Area and length calculation engine
│   │   ├── parser_service.py       # Parser dispatcher
│   │   ├── file_service.py         # File ingestion orchestration and persistence
│   │   └── parsers/
│   │       ├── base.py             # Abstract base parser and data models
│   │       ├── shapefile_parser.py # Shapefile (.zip) parser with .prj parsing
│   │       └── kml_parser.py       # Defused XML KML/KMZ parser
│   └── utils/
│       └── file_utils.py           # Zip Slip defense, sanitized filenames, temp dirs
├── sample_data/                    # Sample Shapefile zip files and KML files
│   ├── create_sample_shapefiles.py # Generator for valid test shapefiles
│   ├── sample_parcels.zip          # Zipped Polygon Shapefile with attributes and .prj
│   ├── sample_roads.zip            # Zipped LineString Shapefile with attributes and .prj
│   ├── sample_polygons.kml         # Polygons (including parcel with inner reservoir hole)
│   ├── sample_linestrings.kml      # Infrastructure LineStrings
│   ├── sample_points.kml           # Geodetic benchmark Points
│   └── sample_mixed.kml            # Combined Polygons, Lines, and Points
├── tests/                          # Automated test suite (24 passing tests)
│   ├── conftest.py                 # Pytest fixtures and in-memory test database
│   ├── test_api.py                 # Integration tests for all endpoints and status codes
│   ├── test_crs.py                 # Tests for UTM zone determination and reprojection
│   ├── test_measurements.py        # Tests for area/length/point calculations
│   └── test_parsers.py             # Tests for KML and Shapefile extraction
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
  ├── .zip  ──► [ShapefileParser]: Safe Unpack ──► Read .prj (CRS) ──► Read Shapes & DBF
  └── .kml  ──► [KMLParser]: DefusedXML ──► Extract Placemarks ──► Rings, Lines, Points
       │
       ▼
[Feature Extraction: GeoJSON Geometry + Attributes + CRS]
       │
       ▼
[Measurement Engine: Reproject to UTM Metric System ──► Compute Area / Length]
       │
       ▼
[Store FileRecord & FeatureRecords in SQLite DB]
       │
       ▼
[Return FileInfoResponse (ID, Filename, Feature Count, CRS, Status: COMPLETED)]
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
  │     ├── Topological Validation (repair invalid bowties if needed)
  │     ├── Determine Optimal Projected CRS (UTM Zone based on centroid lon/lat)
  │     ├── Reproject Geometry (degrees ──► meters)
  │     ├── Calculate Area = projected_geom.area (m²)
  │     └── Convert to km², hectares, acres
  │
  ├── Geometry is LineString / MultiLineString:
  │     ├── Determine Optimal Projected CRS (UTM Zone based on centroid lon/lat)
  │     ├── Reproject Geometry (degrees ──► meters)
  │     ├── Calculate Length = projected_geom.length (m)
  │     └── Convert to km, miles, feet
  │
  └── Unsupported Geometry (e.g. GeometryCollection):
        └── Handled gracefully with Status = UNSUPPORTED_GEOMETRY (no crash)
```

---

### 4. CRS Handling Strategy

Geographic coordinates (such as **EPSG:4326 / WGS 84**) measure locations in angular units (degrees of latitude and longitude). Directly calculating distance or area on degrees produces mathematically invalid results ($1^\circ$ of longitude at the equator is $\approx 111.32\text{ km}$, while at $60^\circ$ latitude it is $\approx 55.80\text{ km}$).

**Our Projection Strategy:**
1. **CRS Detection**:
   - For **Shapefiles**: Parses the `.prj` file WKT definition into an EPSG identifier using `pyproj.CRS.from_wkt()`. Defaults to `EPSG:4326` if `.prj` is missing.
   - For **KML**: The OGC KML standard specifies coordinates in `EPSG:4326` (WGS 84).
2. **Dynamic Metric Projection Selection**:
   - Computes the geometry centroid $(\text{lon}, \text{lat})$.
   - Dynamically calculates the optimal **Universal Transverse Mercator (UTM)** zone:
     $$\text{zone} = \left\lfloor \frac{\text{lon} + 180.0}{6.0} \right\rfloor + 1 \quad (1 \le \text{zone} \le 60)$$
   - Identifies the hemisphere:
     - **Northern Hemisphere** ($\text{lat} \ge 0$): `EPSG:32600 + zone`
     - **Southern Hemisphere** ($\text{lat} < 0$): `EPSG:32700 + zone`
     - **Polar Extremes** ($|\text{lat}| > 84^\circ$): Universal Polar Stereographic (`EPSG:32661` North / `EPSG:32761` South).
   - If the source data is already in a projected metric coordinate system (e.g., State Plane or existing UTM), the service retains that projection.
3. **Reprojection Execution**:
   - Uses `pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)` with `shapely.ops.transform` to project coordinates into meters.
   - Calculates the exact planar metric measurements in this conformal, distance-preserving coordinate frame.

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

## API Reference & Examples

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

**Example Response (`201 Created`):**
```json
{
  "id": "e9b21f37ac01",
  "filename": "sample_polygons.kml",
  "feature_count": 2,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "file_type": "KML",
  "file_size_bytes": 1928,
  "created_at": "2026-10-06T17:34:00Z",
  "error_message": null
}
```

---

### 2. Get File Information
Retrieves metadata and processing status for an uploaded file.

- **URL**: `GET /api/files/{id}/`
- **Response Format**: Matches the exact specification.

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/files/e9b21f37ac01/"
```

**Example Response (`200 OK`):**
```json
{
  "id": "e9b21f37ac01",
  "filename": "sample_polygons.kml",
  "feature_count": 2,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

---

### 3. Get File Measurements
Returns calculated measurements (area, length, projected CRS used) for every feature, along with aggregate summary statistics.

- **URL**: `GET /api/files/{id}/measurements/`

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/files/e9b21f37ac01/measurements/"
```

**Example Response (`200 OK`):**
```json
{
  "id": "e9b21f37ac01",
  "filename": "sample_polygons.kml",
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "summary": {
    "total_features": 2,
    "geometry_type_breakdown": {
      "Polygon": 2
    },
    "total_area_sq_meters": 31254.8921,
    "total_area_sq_km": 0.031255,
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
          "sq_meters": 31254.8921,
          "sq_kilometers": 0.031255,
          "hectares": 3.1255,
          "acres": 7.7233
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

**Example Response (`200 OK`):**
```json
{
  "status": "HEALTHY",
  "service": "Geospatial File Measurement API",
  "version": "1.0.0",
  "supported_formats": [".kml", ".kmz", ".zip"],
  "measurement_engines": {
    "polygon": "Area calculation via dynamic metric UTM projection",
    "linestring": "Length calculation via dynamic metric UTM projection",
    "point": "No measurement required"
  }
}
```

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

## Testing

The project includes an automated test suite covering unit tests for parsers, CRS selection algorithms, topological repairs, and end-to-end API integration tests.

Run all tests:
```bash
pytest -v
```

Test summary:
- `tests/test_api.py`: Upload, retrieval, measurement querying, deletion, and HTTP error handling.
- `tests/test_crs.py`: Geographic CRS detection, Northern/Southern UTM selection, polar handling, and metric reprojection.
- `tests/test_measurements.py`: Polygon area, LineString length, Point no-measurement handling, and invalid geometry auto-repair.
- `tests/test_parsers.py`: Shapefile zip component extraction, KML inner/outer boundary parsing, attributes extraction, and XML error resilience.

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
1. **Coordinate Geometry Nuances**:
   Computing areas and lengths directly on latitude/longitude spherical coordinates is one of the most common pitfalls in geospatial engineering. Automating dynamic UTM projection selection ensures high accuracy without manual projection configuration from API consumers.
2. **Defensive Geospatial Parsing**:
   Real-world GIS files often contain topological anomalies (such as self-intersecting bowtie polygons) or corrupted archive structures. Handling these cases gracefully with automated repairs and explicit error messages prevents service interruptions.
3. **XML & Archive Security**:
   Extracting user-submitted archives requires guarding against path traversal (Zip Slip), while parsing KML documents demands protection against XML entity attacks (`defusedxml`).

### Future Scope
- **Asynchronous Task Workers**: For multi-gigabyte shapefiles containing millions of parcels, integrate Celery or RQ with Redis to process measurements asynchronously and emit webhook notifications upon completion.
- **Elevation & 3D Surface Measurements**: Expand support for 3D coordinates ($Z$ elevation) and digital elevation models (DEM) to calculate true surface area across topography.
- **GeoPackage & Cloud-Optimized Formats**: Add native parsers for OGC GeoPackage (`.gpkg`), FlatGeobuf, and Cloud-Optimized Point Clouds (COPC).
- **Direct GeoJSON Export & Map Visualization**: Add an export endpoint (`GET /api/files/{id}/geojson`) and an embedded interactive Leaflet or MapLibre viewer to inspect feature geometries visually in the browser.

---

## Repository

- **GitHub Repository**: [https://github.com/rahul-1909/Geospatial-File-Measurement-API](https://github.com/rahul-1909/Geospatial-File-Measurement-API)
- **Author**: Rahul Teja Nalla ([rahul-1909](https://github.com/rahul-1909))
