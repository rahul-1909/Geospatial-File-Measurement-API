import os
import zipfile
from pathlib import Path
import shapefile

WGS84_PRJ = (
    'GEOGCS["GCS_WGS_1984",'
    'DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],'
    'UNIT["Degree",0.0174532925199433]]'
)


def create_parcels_shapefile(output_dir: Path):
    """Creates a polygon shapefile and packages it into sample_parcels.zip"""
    temp_shp = output_dir / "temp_parcels"
    temp_shp.mkdir(parents=True, exist_ok=True)
    base_name = temp_shp / "parcels"

    w = shapefile.Writer(str(base_name), shapeType=shapefile.POLYGON)
    w.field("ID", "C", size=50)
    w.field("NAME", "C", size=100)
    w.field("ZONING", "C", size=50)
    w.field("LOT_NUM", "N", decimal=0)

    # Polygon 1: Downtown Commercial Parcel
    w.poly([
        [
            [-73.9851, 40.7484],
            [-73.9820, 40.7484],
            [-73.9820, 40.7505],
            [-73.9851, 40.7505],
            [-73.9851, 40.7484]
        ]
    ])
    w.record("P001", "Empire Plaza Lot", "Commercial", 101)

    # Polygon 2: Riverside Green Area
    w.poly([
        [
            [-73.9900, 40.7400],
            [-73.9870, 40.7400],
            [-73.9860, 40.7430],
            [-73.9910, 40.7430],
            [-73.9900, 40.7400]
        ]
    ])
    w.record("P002", "Riverside Green", "Park", 102)

    w.close()

    # Write PRJ file
    prj_file = temp_shp / "parcels.prj"
    with open(prj_file, "w") as f:
        f.write(WGS84_PRJ)

    # Zip all components
    zip_path = output_dir / "sample_parcels.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for ext in [".shp", ".shx", ".dbf", ".prj"]:
            file_to_add = temp_shp / f"parcels{ext}"
            zf.write(file_to_add, arcname=f"parcels{ext}")

    print(f"Created {zip_path}")


def create_roads_shapefile(output_dir: Path):
    """Creates a linestring shapefile and packages it into sample_roads.zip"""
    temp_shp = output_dir / "temp_roads"
    temp_shp.mkdir(parents=True, exist_ok=True)
    base_name = temp_shp / "roads"

    w = shapefile.Writer(str(base_name), shapeType=shapefile.POLYLINE)
    w.field("ROAD_ID", "C", size=50)
    w.field("NAME", "C", size=100)
    w.field("LANES", "N", decimal=0)
    w.field("SPEED_MPH", "N", decimal=0)

    # Line 1: Broadway Ave
    w.line([
        [
            [-73.9880, 40.7450],
            [-73.9860, 40.7470],
            [-73.9840, 40.7500],
            [-73.9820, 40.7530]
        ]
    ])
    w.record("R101", "Broadway Ave", 4, 30)

    # Line 2: 5th Avenue Express
    w.line([
        [
            [-73.9800, 40.7400],
            [-73.9780, 40.7450],
            [-73.9760, 40.7500]
        ]
    ])
    w.record("R102", "5th Ave Express", 6, 35)

    w.close()

    # Write PRJ file
    prj_file = temp_shp / "roads.prj"
    with open(prj_file, "w") as f:
        f.write(WGS84_PRJ)

    # Zip all components
    zip_path = output_dir / "sample_roads.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for ext in [".shp", ".shx", ".dbf", ".prj"]:
            file_to_add = temp_shp / f"roads{ext}"
            zf.write(file_to_add, arcname=f"roads{ext}")

    print(f"Created {zip_path}")


if __name__ == "__main__":
    out = Path(__file__).resolve().parent
    create_parcels_shapefile(out)
    create_roads_shapefile(out)
