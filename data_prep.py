import pandas as pd



def prepare_coordinates(df):
    # Work on a copy so the original DataFrame stays unchanged.
    cleaned = df.copy()

    latitude = pd.to_numeric(cleaned["Latitude"], errors="coerce")
    longitude = pd.to_numeric(cleaned["Longitude"], errors="coerce")

    valid = (
        latitude.between(-90, 90)
        & longitude.between(-180, 180)
    )

    # Preserve original coordinates and add separate map columns.
    cleaned["coordinate_range_valid"] = valid
    cleaned["map_latitude"] = latitude.where(valid)
    cleaned["map_longitude"] = longitude.where(valid)

    return cleaned


DISTRICTS = [
    "Ariyalur", "Chengalpattu", "Chennai", "Coimbatore",
    "Cuddalore", "Dharmapuri", "Dindigul", "Erode",
    "Kallakurichi", "Kancheepuram", "Kanyakumari", "Karur",
    "Krishnagiri", "Madurai", "Mayiladuthurai", "Nagapattinam",
    "Namakkal", "Perambalur", "Pudukkottai", "Ramanathapuram",
    "Ranipet", "Salem", "Sivaganga", "Tenkasi",
    "Thanjavur", "Theni", "Thoothukudi", "Tiruchirappalli",
    "Tirunelveli", "Tirupathur", "Tiruppur", "Tiruvallur",
    "Tiruvannamalai", "Tiruvarur", "The Nilgiris", "Vellore",
    "Viluppuram", "Virudhunagar",
]

DISTRICT_ALIASES = {
    "chengalpet": "Chengalpattu",
    "chenglepet": "Chengalpattu",
    "kanchipuram": "Kancheepuram",
    "kanniyakumari": "Kanyakumari",
    "pudukottai": "Pudukkottai",
    "sivagangai": "Sivaganga",
    "sivangai": "Sivaganga",
    "thiruppur": "Tiruppur",
    "thiruvallur": "Tiruvallur",
    "thiruvarur": "Tiruvarur",
    "tiruchirapalli": "Tiruchirappalli",
    "tiruchirapallai": "Tiruchirappalli",
    "thiruchirappalli": "Tiruchirappalli",
    "tirupattur": "Tirupathur",
    "villupuram": "Viluppuram",
    "nilgiris": "The Nilgiris",
}


def prepare_districts(df):
    cleaned = df.copy()

    # Standardize whitespace, including non-breaking spaces.
    district_text = (
        cleaned["Project District"]
        .astype("string")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    # Recognize standard names regardless of capitalization.
    lookup = {name.casefold(): name for name in DISTRICTS}
    lookup.update(DISTRICT_ALIASES)

    cleaned["district_clean"] = district_text.str.casefold().map(lookup)
    cleaned["district_review_needed"] = cleaned["district_clean"].isna()

    return cleaned

def prepare_dates(df):
    cleaned = df.copy()

    # Parse day-first dates and Excel datetime values.
    cleaned["registration_date"] = pd.to_datetime(
        cleaned["Registration Date"],
        format="mixed",
        dayfirst=True,
        errors="coerce",
    )

    cleaned["approval_date"] = pd.to_datetime(
        cleaned["Approval Date"],
        format="mixed",
        dayfirst=True,
        errors="coerce",
    )

    # Identify missing or unreadable dates.
    cleaned["date_review_needed"] = (
        cleaned["registration_date"].isna()
        | cleaned["approval_date"].isna()
    )

    # Derive the year from the parsed registration date.
    cleaned["registration_year"] = (
        cleaned["registration_date"].dt.year.astype("Int64")
    )

    # Calculate approval-to-registration elapsed days.
    elapsed_days = (
        cleaned["registration_date"] - cleaned["approval_date"]
    ).dt.days

    # Flag approval dates that occur after registration.
    cleaned["approval_sequence_issue"] = elapsed_days.lt(0)

    # Keep only non-negative intervals for duration analysis.
    cleaned["approval_to_registration_days"] = elapsed_days.where(
        elapsed_days.ge(0)
    )

    return cleaned

def prepare_promoters(df):
    cleaned = df.copy()

    promoter_text = (
        cleaned["Promoter name"]
        .astype("string")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .replace("", pd.NA)
    )

    cleaned["promoter_clean"] = promoter_text
    cleaned["promoter_key"] = promoter_text.str.casefold()

    return cleaned