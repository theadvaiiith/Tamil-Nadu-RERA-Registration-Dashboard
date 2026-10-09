from pathlib import Path

import pandas as pd

from data_prep import (
    prepare_coordinates,
    prepare_districts,
    prepare_dates,
)

# Locate the Excel file relative to this script.
PROJECT_DIR = Path(__file__).resolve().parent
EXCEL_PATH = PROJECT_DIR / "data" / "Cleaned RERA Data.xlsx"

# Read the first worksheet into a DataFrame.
df = pd.read_excel(EXCEL_PATH, sheet_name=0)

# Remove surrounding whitespace from column headers.
df.columns = df.columns.str.strip()

print("\n--- DATASET SIZE ---")
print(f"Rows: {df.shape[0]:,}")
print(f"Columns: {df.shape[1]}")

print("\n--- COLUMN NAMES ---")
print(df.columns.tolist())

print("\n--- FIRST FIVE RECORDS ---")
print(
    df[
        ["RERA ID", "Project Name", "Project District", "Project Plots"]
    ].head().to_string(index=False)
)

print("\n--- MISSING VALUES PER COLUMN ---")
print(df.isna().sum().to_string())

print("\n--- REGISTRATION ID CHECK ---")
print(f"Unique RERA IDs: {df['RERA ID'].nunique():,}")
print(f"Duplicate RERA IDs: {df['RERA ID'].duplicated().sum():,}")

print("\n--- TOTAL RECORDED PLOTS ---")
print(f"{df['Project Plots'].sum():,}")

print("\n--- COORDINATE VALIDATION ---")

# Convert coordinates to numbers; unreadable values become NaN.
latitude = pd.to_numeric(df["Latitude"], errors="coerce")
longitude = pd.to_numeric(df["Longitude"], errors="coerce")

# Decimal latitude and longitude must fall within these limits.
valid_coordinates = (
    latitude.between(-90, 90)
    & longitude.between(-180, 180)
)

print(f"Within coordinate limits: {valid_coordinates.sum():,}")
print(f"Need review: {(~valid_coordinates).sum():,}")

print("\n--- COORDINATES NEEDING REVIEW: FIRST 10 ---")
print(
    df.loc[
        ~valid_coordinates,
        ["RERA ID", "Project District", "Latitude", "Longitude"]
    ].head(10).to_string(index=False)
)

prepared_df = prepare_coordinates(df)

print("\n--- PREPARED DATA ---")
print(f"Registrations retained: {len(prepared_df):,}")
print(
    "Within coordinate limits: "
    f"{prepared_df['coordinate_range_valid'].sum():,}"
)

print("\n--- SAMPLE RECORD NEEDING COORDINATE REVIEW ---")
print(
    prepared_df.loc[
        ~prepared_df["coordinate_range_valid"],
        ["RERA ID", "Latitude", "Longitude",
         "map_latitude", "map_longitude"]
    ].head(1).to_string(index=False)
)

prepared_df = prepare_districts(prepared_df)

print("\n--- DISTRICT STANDARDIZATION ---")
print(f"Registrations retained: {len(prepared_df):,}")
print(
    "Recognized districts: "
    f"{prepared_df['district_clean'].nunique()}"
)
print(
    "Records needing district review: "
    f"{prepared_df['district_review_needed'].sum():,}"
)

print("\n--- ORIGINAL LABELS AND STANDARDIZED NAMES ---")
print(
    prepared_df[
        ["Project District", "district_clean"]
    ].drop_duplicates().sort_values(
        "Project District"
    ).to_string(index=False)
)

print("\n--- UNRECOGNIZED DISTRICT LABELS ---")
print(
    prepared_df.loc[
        prepared_df["district_review_needed"],
        "Project District"
    ].value_counts(dropna=False).to_string()
)

prepared_df = prepare_dates(prepared_df)

print("\n--- DATE VALIDATION ---")
print(
    "Records with missing/unreadable dates: "
    f"{prepared_df['date_review_needed'].sum():,}"
)
print(
    "Approval after registration: "
    f"{prepared_df['approval_sequence_issue'].sum():,}"
)
print(
    "Registration coverage:",
    prepared_df["registration_date"].min(),
    "to",
    prepared_df["registration_date"].max(),
)

print("\n--- DATE CALCULATIONS: FIRST FIVE ---")
print(
    prepared_df[
        [
            "RERA ID",
            "registration_date",
            "approval_date",
            "approval_to_registration_days",
            "Days after Approval",
        ]
    ].head().to_string(index=False)
)

print("\n--- APPROVAL DATES NEEDING REVIEW: FIRST TEN ---")
print(
    prepared_df.loc[
        prepared_df["approval_sequence_issue"],
        ["RERA ID", "Registration Date", "Approval Date"]
    ].head(10).to_string(index=False)
)