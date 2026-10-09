from pathlib import Path
import sqlite3

import pandas as pd

from data_prep import (
    prepare_coordinates,
    prepare_districts,
    prepare_dates,
)


PROJECT_DIR = Path(__file__).resolve().parent
EXCEL_PATH = PROJECT_DIR / "data" / "Cleaned RERA Data.xlsx"
DATABASE_PATH = PROJECT_DIR / "data" / "rera.db"

# Read and prepare the workbook.
df = pd.read_excel(EXCEL_PATH, sheet_name=0)
df.columns = df.columns.str.strip()

df = prepare_coordinates(df)
df = prepare_districts(df)
df = prepare_dates(df)

# Validate the identifier before storing records.
rera_ids = df["RERA ID"].astype("string").str.strip()

if rera_ids.isna().any() or rera_ids.eq("").any():
    raise ValueError("Some records have missing or empty RERA IDs.")

if rera_ids.duplicated().any():
    raise ValueError("Duplicate RERA IDs found. Review them before importing.")

df["RERA ID"] = rera_ids

# Open the database; SQLite creates the file if needed.
connection = sqlite3.connect(DATABASE_PATH)

try:
    # First import: create the projects table.
    df.to_sql(
        "projects",
        connection,
        if_exists="fail",
        index=False,
    )

    # Prevent repeated registration IDs in this table.
    connection.execute(
        'CREATE UNIQUE INDEX projects_rera_id_unique '
        'ON projects ("RERA ID")'
    )
    connection.commit()

    # Retrieve a district summary from SQL into Pandas.
    district_summary = pd.read_sql_query(
        """
        SELECT
            COALESCE(district_clean, 'Needs review') AS district,
            COUNT(*) AS registrations,
            SUM("Project Plots") AS total_plots
        FROM projects
        GROUP BY COALESCE(district_clean, 'Needs review')
        ORDER BY registrations DESC
        LIMIT 10
        """,
        connection,
    )

    stored_count = connection.execute(
        "SELECT COUNT(*) FROM projects"
    ).fetchone()[0]

    print(f"\nRegistrations stored: {stored_count:,}")
    print(f"Database: {DATABASE_PATH}")

    print("\n--- TOP DISTRICTS IN THE IMPORTED DATA ---")
    print(district_summary.to_string(index=False))

finally:
    connection.close()