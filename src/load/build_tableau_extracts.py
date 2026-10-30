"""Build the Tableau extracts (.hyper files) that the generated workbook reads.

Tableau Public only opens workbooks whose data sources are extracts. Each data
source gets one .hyper file with one table per data object, named
"<file>_<object id>" in the "Extract" schema, which is how Tableau lays out
extracts for its object model.

Run from the project root (after src.load.export_tableau):
    python -m src.load.build_tableau_extracts
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.polygon import orient
from tableauhyperapi import (
    Connection, CreateMode, HyperProcess, Inserter, SqlType, TableDefinition, TableName, Telemetry,
    escape_name,
)

from src.config import ROOT

DATA = ROOT / "tableau" / "data"
EXTRACTS = ROOT / "tableau" / "extracts"

# Object ids: the map's two come from the workbook Tableau built; the others are fixed here.
OBJECTS = {
    "ct_regions": "ct_regions.csv_3A5C7E9B1D3F5A7C9E1B3D5F7A9C1E31",
    "ct_prospects": "ct_prospects.csv_8B0D2F4A6C8E0B2D4F6A8C0E2B4D6F81",
    "counties": "counties.geojson_44F0576E2B404900983994B8D103D788",
    "county_month": "county_month.csv_AF07728901FA4E3CA9F2997ED2222331",
    "seasonal_pulse": "seasonal_pulse.csv_5B1E0C7A9D2F4E6B8C3A1D0E9F7B6A51",
    "county_scores": "county_scores.csv_7E9A1C3B5D7F9B1D3F5A7C9E1B3D5F75",
}
HYPER_FILES = {"map": "map.hyper", "pulse": "seasonal_pulse.hyper", "scores": "county_scores.hyper",
               "ct_regions": "ct_regions.hyper", "ct_prospects": "ct_prospects.hyper"}

SQL_TYPES = {
    "string": SqlType.text(),
    "integer": SqlType.big_int(),
    "real": SqlType.double(),
    "date": SqlType.date(),
}


def ccw(geom):
    """Hyper reads polygon rings counter-clockwise (interior on the left)."""
    if isinstance(geom, Polygon):
        return orient(geom, sign=1.0)
    if isinstance(geom, MultiPolygon):
        return MultiPolygon([orient(p, sign=1.0) for p in geom.geoms])
    return geom


def csv_types(df: pd.DataFrame, dates: list[str]) -> dict[str, str]:
    types = {}
    for col, dtype in df.dtypes.items():
        if col in dates:
            types[col] = "date"
        elif pd.api.types.is_integer_dtype(dtype):
            types[col] = "integer"
        elif pd.api.types.is_float_dtype(dtype):
            types[col] = "real"
        else:
            types[col] = "string"
    return types


def write_table(conn: Connection, object_id: str, df: pd.DataFrame, types: dict[str, str]) -> None:
    table = TableDefinition(TableName("Extract", object_id),
                            [TableDefinition.Column(c, SQL_TYPES[types[c]]) for c in df.columns])
    conn.catalog.create_table(table)
    rows = df.astype(object).where(df.notna(), None)
    for c, t in types.items():
        if t == "date":
            rows[c] = pd.to_datetime(df[c]).dt.date
    with Inserter(conn, table) as ins:
        ins.add_rows(rows.itertuples(index=False, name=None))
        ins.execute()


def write_counties(conn: Connection) -> None:
    gdf = gpd.read_file(DATA / "counties.geojson")
    table = TableDefinition(TableName("Extract", OBJECTS["counties"]), [
        TableDefinition.Column("county_key", SqlType.text()),
        TableDefinition.Column("county_name", SqlType.text()),
        TableDefinition.Column("state_abbr", SqlType.text()),
        TableDefinition.Column("Geometry", SqlType.geography()),
    ])
    conn.catalog.create_table(table)
    staging = [
        TableDefinition.Column("county_key", SqlType.text()),
        TableDefinition.Column("county_name", SqlType.text()),
        TableDefinition.Column("state_abbr", SqlType.text()),
        TableDefinition.Column("wkt", SqlType.text()),
    ]
    mapping = [
        Inserter.ColumnMapping("county_key"),
        Inserter.ColumnMapping("county_name"),
        Inserter.ColumnMapping("state_abbr"),
        Inserter.ColumnMapping("Geometry", f"CAST({escape_name('wkt')} AS TABLEAU.TABGEOGRAPHY)"),
    ]
    with Inserter(conn, table, mapping, inserter_definition=staging) as ins:
        for r in gdf.itertuples():
            ins.add_row([r.county_key, r.county_name, r.state_abbr, ccw(r.geometry).wkt])
        ins.execute()


def build(name: str, tables: list[tuple[str, pd.DataFrame, dict]], with_counties: bool = False) -> None:
    path = EXTRACTS / HYPER_FILES[name]
    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
        with Connection(hyper.endpoint, str(path), CreateMode.CREATE_AND_REPLACE) as conn:
            conn.catalog.create_schema("Extract")
            if with_counties:
                write_counties(conn)
            for object_key, df, types in tables:
                write_table(conn, OBJECTS[object_key], df, types)
    print(f"  wrote extracts/{path.name}")


def load(name: str, dates: list[str]) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(DATA / f"{name}.csv")
    return df, csv_types(df, dates)


def main() -> None:
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    cm, cm_types = load("county_month", ["month_date"])
    build("map", [("county_month", cm, cm_types)], with_counties=True)
    for name, key, dates in [("pulse", "seasonal_pulse", ["month_date"]), ("scores", "county_scores", []),
                             ("ct_regions", "ct_regions", []), ("ct_prospects", "ct_prospects", [])]:
        df, types = load(key, dates)
        build(name, [(key, df, types)])


if __name__ == "__main__":
    main()
