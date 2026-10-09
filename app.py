from contextlib import closing
from pathlib import Path
import sqlite3

from numbers import Number

from uuid import uuid4

import pandas as pd
import streamlit as st
import plotly.express as px

import pydeck as pdk

from data_prep import (
    prepare_coordinates,
    prepare_districts,
    prepare_dates,
    prepare_promoters,
)

st.set_page_config(
    page_title="TN RERA Intelligence",
    page_icon="🏘️",
    layout="wide",
)

PROJECT_DIR = Path(__file__).resolve().parent
DATABASE_PATH = PROJECT_DIR / "data" / "rera.db"

def replace_projects(dataframe, database_path, source_filename):
    if dataframe.empty:
        raise ValueError("Cannot import an empty dataset.")

    database_path.parent.mkdir(parents=True, exist_ok=True)
    staging_table = f"projects_stage_{uuid4().hex}"

    with closing(sqlite3.connect(database_path, timeout=30)) as connection:
        try:
            # Write the upload separately from the current projects table.
            dataframe.to_sql(
                staging_table,
                connection,
                if_exists="fail",
                index=False,
            )

            # Swap the table and its metadata as one transaction.
            connection.execute("BEGIN IMMEDIATE")
            connection.execute('DROP TABLE IF EXISTS "projects"')
            connection.execute(
                f'ALTER TABLE "{staging_table}" RENAME TO "projects"'
            )
            connection.execute(
                'CREATE UNIQUE INDEX projects_rera_id_unique '
                'ON projects ("RERA ID")'
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS import_metadata (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    source_filename TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    imported_at TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                INSERT OR REPLACE INTO import_metadata
                    (id, source_filename, row_count, imported_at)
                VALUES (1, ?, ?, CURRENT_TIMESTAMP)
                """,
                (source_filename, len(dataframe)),
            )

            connection.commit()

        except Exception:
            connection.rollback()
            connection.execute(
                f'DROP TABLE IF EXISTS "{staging_table}"'
            )
            connection.commit()
            raise

    return len(dataframe)

st.title("Tamil Nadu RERA Analysis")


st.sidebar.header("Dataset upload")

uploaded_file = st.sidebar.file_uploader(
    "Choose a RERA Excel workbook",
    type=["xlsx"],
    help="Use the same 18 source headers as your original workbook.",
)

prepared_upload = None

if uploaded_file is not None:
    try:
        uploaded_df = pd.read_excel(
            uploaded_file,
            sheet_name=0,
            engine="openpyxl",
        )

        uploaded_df.columns = (
            uploaded_df.columns.astype(str).str.strip()
        )

        required_columns = {
            "S. No", "RERA ID", "Registration Date",
            "Promoter name", "Project Name", "Latitude",
            "Longitude", "Approval Board", "Project Plots",
            "Project District", "Project Taluk", "Project Village",
            "Approval Date", "Current Status of the Project",
            "Days after Approval", "Approval Period",
            "Plot Range", "Year",
        }

        missing_columns = required_columns - set(uploaded_df.columns)
        extra_columns = set(uploaded_df.columns) - required_columns

        if uploaded_df.columns.duplicated().any():
            raise ValueError("Duplicate column headers found.")

        if missing_columns:
            raise ValueError(
                f"Missing headers: {', '.join(sorted(missing_columns))}"
            )

        if extra_columns:
            raise ValueError(
                f"Unexpected headers: {', '.join(sorted(extra_columns))}"
            )

        if uploaded_df.empty:
            raise ValueError("The first worksheet contains no records.")

        # Registration IDs must be present and unique.
        rera_ids = uploaded_df["RERA ID"].astype("string").str.strip()

        if rera_ids.isna().any() or rera_ids.eq("").any():
            raise ValueError("Some records have missing RERA IDs.")

        if rera_ids.duplicated().any():
            raise ValueError("Duplicate RERA IDs found.")

        uploaded_df["RERA ID"] = rera_ids

        # Plot counts must be positive whole numbers.
        plots = pd.to_numeric(
            uploaded_df["Project Plots"],
            errors="coerce",
        )

        valid_plots = plots.gt(0) & plots.mod(1).eq(0)

        if not valid_plots.all():
            raise ValueError(
                f"{(~valid_plots).sum():,} records have invalid plot counts."
            )

        uploaded_df["Project Plots"] = plots.astype("int64")

        # Avoid treating raw numeric date cells as Unix timestamps.
        for column in ["Registration Date", "Approval Date"]:
            if uploaded_df[column].map(
                lambda value: isinstance(value, Number)
            ).any():
                raise ValueError(
                    f"{column} contains numeric cells. "
                    "Format them as Excel dates or day/month/year text."
                )

        # Reuse our existing preparation pipeline.
        uploaded_df = prepare_coordinates(uploaded_df)
        uploaded_df = prepare_districts(uploaded_df)
        uploaded_df = prepare_dates(uploaded_df)
        uploaded_df = prepare_promoters(uploaded_df)

        if uploaded_df["registration_date"].isna().any():
            raise ValueError(
                "Some registration dates are missing or unreadable."
            )

        # Assign only after validation succeeds.
        prepared_upload = uploaded_df

        st.sidebar.success("Workbook validated for import.")

        with st.sidebar.expander("Upload review", expanded=True):
            st.write({
                "Registrations": len(prepared_upload),
                "Recorded plots": int(
                    prepared_upload["Project Plots"].sum()
                ),
                "Coordinate pairs needing review": int(
                    (~prepared_upload["coordinate_range_valid"]).sum()
                ),
                "District labels needing review": int(
                    prepared_upload["district_review_needed"].sum()
                ),
                "Records with date issues": int(
                    prepared_upload["date_review_needed"].sum()
                ),
                "Approval after registration": int(
                    prepared_upload["approval_sequence_issue"].sum()
                ),
            })

        st.sidebar.caption("Import this workbook as the complete replacement dataset.")

    except Exception as error:
        st.sidebar.error(f"Upload validation failed: {error}")

if prepared_upload is not None:
    import_clicked = st.sidebar.button(
        "Replace dataset",
        type="primary",
        help="Replaces all current registrations with this validated workbook.",
    )

    if import_clicked:
        try:
            imported_count = replace_projects(
                prepared_upload,
                DATABASE_PATH,
                uploaded_file.name,
            )

        except Exception as error:
            st.sidebar.error(f"Database import failed: {error}")

        else:
            st.session_state["import_success"] = (
                f"Imported {imported_count:,} registrations successfully."
            )
            st.rerun()

if "import_success" in st.session_state:
    st.sidebar.success(
        st.session_state.pop("import_success")
    )


# Check that the database has been created.
if not DATABASE_PATH.exists():
    st.error("Database not found. Run python load_data.py first.")
    st.stop()

# Retrieve the SQL table into a Pandas DataFrame.
import_info = None

with closing(sqlite3.connect(DATABASE_PATH)) as connection:
    df = pd.read_sql_query("SELECT * FROM projects", connection)

    metadata_exists = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'import_metadata'
        """
    ).fetchone()

    if metadata_exists:
        import_info = connection.execute(
            """
            SELECT source_filename, row_count, imported_at
            FROM import_metadata
            WHERE id = 1
            """
        ).fetchone()

if import_info:
    st.sidebar.text(f"Source: {import_info[0]}")
    st.sidebar.caption(
        f"{import_info[1]:,} imported registrations · "
        f"{import_info[2]} UTC"
    )

# SQLite returns stored dates as text.
df["registration_date"] = pd.to_datetime(
    df["registration_date"],
    errors="coerce",
)

df = prepare_promoters(df)

# Use explicit, non-overlapping size bands instead of the supplied Plot Range.
SIZE_LABELS = [
    "1–30 plots", "31–60 plots", "61–100 plots",
    "101–200 plots", "More than 200 plots",
]
plot_counts = pd.to_numeric(df["Project Plots"], errors="coerce")
df["plot_count"] = plot_counts.where(
    plot_counts.gt(0) & plot_counts.mod(1).eq(0)
)
df["project_size"] = (
    pd.cut(
        df["plot_count"],
        bins=[0, 30, 60, 100, 200, float("inf")],
        labels=SIZE_LABELS,
        right=True,
    )
    .cat.add_categories(["Needs review"])
    .fillna("Needs review")
)

# Keep unresolved districts visible in the filter and table.
df["district_display"] = df["district_clean"].fillna("Needs review")

# Sidebar controls.
st.sidebar.header("Filters")

district_options = sorted(df["district_display"].unique().tolist())

selected_districts = st.sidebar.multiselect(
    "Districts",
    options=district_options,
    help="Leave empty to include all districts.",
)

# Define the reporting period using valid registration dates.
valid_dates = df["registration_date"].dropna()

if valid_dates.empty:
    st.error("The database contains no valid registration dates.")
    st.stop()

earliest_date = valid_dates.min().date()
latest_date = valid_dates.max().date()

selected_period = st.sidebar.date_input(
    "Registration period",
    value=(earliest_date, latest_date),
    min_value=earliest_date,
    max_value=latest_date,
    format="DD/MM/YYYY",
)

if len(selected_period) != 2:
    st.sidebar.info("Select both a start date and an end date.")
    st.stop()

start_date, end_date = selected_period

# Normalize removes the time component so the end date is fully included.
filtered_df = df.loc[
    df["registration_date"].dt.normalize().between(
        pd.Timestamp(start_date),
        pd.Timestamp(end_date),
    )
].copy()

if selected_districts:
    filtered_df = filtered_df.loc[
        filtered_df["district_display"].isin(selected_districts)
    ]

# Both trend charts will use this same calendar-month range.
reporting_months = pd.date_range(
    start=pd.Timestamp(start_date).to_period("M").to_timestamp(),
    end=pd.Timestamp(end_date).to_period("M").to_timestamp(),
    freq="MS",
)

st.sidebar.caption(
    f"Showing {len(filtered_df):,} of {len(df):,} registrations"
)

st.caption(
    f"Reporting period: {start_date:%d %b %Y} – {end_date:%d %b %Y}. "
    "Monthly charts include only records within these dates; "
    "boundary months may be partial."
)

# Summary cards.
card1, card2, card3, card4 = st.columns(4)

card1.metric(
    "Registrations",
    f"{len(filtered_df):,}",
    border=True,
)

card2.metric(
    "Recorded plots",
    f"{filtered_df['Project Plots'].sum():,}",
    border=True,
)

card3.metric(
    "Recognized districts",
    f"{filtered_df['district_clean'].nunique():,}",
    border=True,
)

card4.metric(
    "Promoter name groups",
    f"{filtered_df['promoter_key'].nunique():,}",
    border=True,
    help=(
        "Groups names after whitespace and capitalization cleanup. "
        "These are not verified unique company identities."
    ),
)

st.subheader("Insights for this selection")

st.caption(
    "Ranked by registration count using the district and date filters. "
    "Percentages use all registrations in the current selection."
)

if filtered_df.empty:
    st.info("Select a district and date range containing registrations.")
else:
    district_counts = filtered_df["district_clean"].dropna().value_counts()

    promoter_counts = filtered_df["promoter_key"].dropna().value_counts()
    promoter_names = (
        filtered_df.dropna(subset=["promoter_key"])
        .drop_duplicates("promoter_key")
        .set_index("promoter_key")["promoter_clean"]
    )
    promoter_counts.index = promoter_counts.index.map(promoter_names)

    size_counts = filtered_df.loc[
        filtered_df["project_size"].isin(SIZE_LABELS),
        "project_size",
    ].value_counts()

    insights = [
        ("Leading district", district_counts),
        ("Most active promoter name group", promoter_counts),
        ("Most common project size", size_counts),
    ]

    insight_columns = st.columns(3)
    selection_total = len(filtered_df)

    for column, (title, counts) in zip(insight_columns, insights):
        with column:
            with st.container(border=True):
                st.markdown(f"#### {title}")

                if counts.empty:
                    st.info("No usable values in this selection.")
                    continue

                highest_count = int(counts.max())
                leaders = counts[counts == highest_count].index.tolist()

                st.write(str(leaders[0]))
                st.metric("Registrations", f"{highest_count:,}")

                share = highest_count / selection_total * 100
                st.caption(f"{share:.1f}% of selected registrations")

                if len(leaders) > 1:
                    st.caption(
                        f"{len(leaders)} entries share first place. "
                        "One is displayed."
                    )



st.subheader("Registered development activity")

chart_measure = st.radio(
    "Chart measure",
    ["Registrations", "Recorded plots"],
    horizontal=True,
)

measure_column = {
    "Registrations": "registrations",
    "Recorded plots": "total_plots",
}[chart_measure]

trend_column, district_column = st.columns([1.4, 1])

# ----- MONTHLY TREND -----
with trend_column:
    st.markdown("#### Monthly activity")

    trend_data = filtered_df.dropna(
        subset=["registration_date"]
    ).copy()

    if trend_data.empty:
        st.info("No valid registration dates in this selection.")
    else:
        # Represent every registration month by its first day.
        trend_data["month"] = (
            trend_data["registration_date"]
            .dt.to_period("M")
            .dt.to_timestamp()
        )

        monthly_summary = trend_data.groupby("month").agg(
            registrations=("RERA ID", "size"),
            total_plots=("Project Plots", "sum"),
        )

        # # Use the selected reporting period.
        month_range = reporting_months

        # Include months with no records in the selected districts.
        monthly_summary = (
            monthly_summary
            .reindex(month_range, fill_value=0)
            .rename_axis("month")
            .reset_index()
        )

        trend_figure = px.line(
            monthly_summary,
            x="month",
            y=measure_column,
            markers=True,
            labels={
                "month": "Registration month",
                measure_column: chart_measure,
            },
            color_discrete_sequence=["#83C9FF"],
        )

        trend_figure.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0E1117",
            plot_bgcolor="#0E1117",
            height=400,
            margin=dict(l=10, r=10, t=20, b=10),
        )

        trend_figure.update_xaxes(
            tickformat="%b %Y",
            hoverformat="%b %Y",
        )
        trend_figure.update_yaxes(
            tickformat=",d",
            rangemode="tozero",
        )

        st.plotly_chart(
            trend_figure,
            width="stretch",
            theme=None,
        )

        excluded_dates = filtered_df["registration_date"].isna().sum()

        st.caption(
            f"{excluded_dates:,} records excluded for missing/unreadable "
            "registration dates. Zero means no records in this uploaded "
            "dataset; boundary months may have partial coverage."
        )

# ----- DISTRICT RANKING -----
with district_column:
    st.markdown("#### Top districts")

    district_summary = (
        filtered_df.dropna(subset=["district_clean"])
        .groupby("district_clean", as_index=False)
        .agg(
            registrations=("RERA ID", "size"),
            total_plots=("Project Plots", "sum"),
        )
        .sort_values(measure_column, ascending=False)
        .head(10)
    )

    if district_summary.empty:
        st.info("No recognized districts in this selection.")
    else:
        district_figure = px.bar(
            district_summary.sort_values(measure_column),
            x=measure_column,
            y="district_clean",
            orientation="h",
            labels={
                "district_clean": "District",
                measure_column: chart_measure,
            },
            color_discrete_sequence=["#FF4B4B"],
        )

        district_figure.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0E1117",
            plot_bgcolor="#0E1117",
            height=400,
            margin=dict(l=10, r=10, t=20, b=10),
        )
        district_figure.update_xaxes(
            tickformat=",d",
            rangemode="tozero",
        )

        st.plotly_chart(
            district_figure,
            width="stretch",
            theme=None,
        )

        leader = district_summary.iloc[0]

        st.caption(
            f"{leader['district_clean']} leads this selection with "
            f"{leader[measure_column]:,} {chart_measure.lower()}. "
            "Unresolved district labels are excluded from this ranking."
        )

st.subheader("District comparison")

comparison_data = filtered_df.dropna(
    subset=["registration_date", "district_clean"]
).copy()

if comparison_data.empty:
    st.info("No records with recognized districts and valid dates.")
else:
    comparison_data["month"] = (
        comparison_data["registration_date"]
        .dt.to_period("M")
        .dt.to_timestamp()
    )

    # Calculate monthly activity for every recognized district.
    monthly_comparison = comparison_data.groupby(
        ["month", "district_clean"]
    ).agg(
        registrations=("RERA ID", "size"),
        total_plots=("Project Plots", "sum"),
    )

    available_districts = sorted(
        comparison_data["district_clean"].unique().tolist()
    )

    comparison_months = reporting_months

    # Include each district in each month, even when its count is zero.
    complete_index = pd.MultiIndex.from_product(
        [comparison_months, available_districts],
        names=["month", "district_clean"],
    )

    monthly_comparison = (
        monthly_comparison
        .reindex(complete_index, fill_value=0)
        .reset_index()
    )

    # Default to the three largest districts for the current measure.
    default_districts = (
        monthly_comparison.groupby("district_clean")[measure_column]
        .sum()
        .nlargest(3)
        .index.tolist()
    )

    comparison_districts = st.multiselect(
        "Districts to compare",
        options=available_districts,
        default=default_districts,
        max_selections=5,
        help=(
            "Select up to five districts. This controls the comparison "
            "lines; the sidebar still defines the overall reporting scope."
        ),
    )

    comparison_view = st.radio(
        "Comparison view",
        ["Activity totals", "Percentage share"],
        horizontal=True,
    )

    # Calculate the denominator BEFORE selecting comparison lines.
    monthly_totals = monthly_comparison.groupby("month")[
        measure_column
    ].transform("sum")

    monthly_comparison["share_pct"] = (
        monthly_comparison[measure_column]
        .div(monthly_totals.where(monthly_totals.gt(0)))
        .mul(100)
    )

    selected_comparison = monthly_comparison.loc[
        monthly_comparison["district_clean"].isin(comparison_districts)
    ]

    if not comparison_districts:
        st.info("Choose at least one district to compare.")
    else:
        y_column = (
            measure_column
            if comparison_view == "Activity totals"
            else "share_pct"
        )

        y_label = (
            chart_measure
            if comparison_view == "Activity totals"
            else "Share within sidebar scope (%)"
        )

        comparison_figure = px.line(
            selected_comparison,
            x="month",
            y=y_column,
            color="district_clean",
            markers=True,
            labels={
                "month": "Registration month",
                "district_clean": "District",
                y_column: y_label,
            },
            hover_data={
                "registrations": ":,.0f",
                "total_plots": ":,.0f",
            },
            color_discrete_sequence=[
                "#83C9FF",
                "#FF4B4B",
                "#29B09D",
                "#FFD166",
                "#B692F6",
            ],
        )

        comparison_figure.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0E1117",
            plot_bgcolor="#0E1117",
            height=420,
            margin=dict(l=10, r=10, t=20, b=10),
            legend_title_text="District",
        )
        comparison_figure.update_xaxes(
            tickformat="%b %Y",
            hoverformat="%b %Y",
        )
        comparison_figure.update_yaxes(rangemode="tozero")

        st.plotly_chart(
            comparison_figure,
            width="stretch",
            theme=None,
        )

        st.caption(
            "Share uses all recognized districts with valid registration "
            "dates within the sidebar selection, including districts whose "
            "lines are hidden. Months with no activity have undefined shares. "
            "Coverage reflects the uploaded dataset."
        )


st.subheader("Project locations")

map_latitude = pd.to_numeric(
    filtered_df["map_latitude"],
    errors="coerce",
)
map_longitude = pd.to_numeric(
    filtered_df["map_longitude"],
    errors="coerce",
)

numerical_coordinates = (
    map_latitude.between(-90, 90)
    & map_longitude.between(-180, 180)
)

# Broad regional screen; this is not a Tamil Nadu boundary check.
regional_coordinates = (
    map_latitude.between(8, 14)
    & map_longitude.between(76, 81)
)

map_eligible = numerical_coordinates & regional_coordinates
map_data = filtered_df.loc[map_eligible].copy()

if map_data.empty:
    st.info("No coordinates pass the map checks in this selection.")
else:
    map_points = map_data[
        [
            "map_latitude",
            "map_longitude",
            "district_display",
            "Project Taluk",
            "RERA ID",
            "promoter_clean",
        ]
    ].rename(
        columns={
            "map_latitude": "latitude",
            "map_longitude": "longitude",
            "district_display": "district",
            "Project Taluk": "taluk",
            "RERA ID": "rera_id",
            "promoter_clean": "promoter",
        }
    )

    tooltip_columns = ["district", "taluk", "rera_id", "promoter"]
    map_points[tooltip_columns] = (
        map_points[tooltip_columns].fillna("Unknown").astype(str)
    )

    positions = map_points[["longitude", "latitude"]].drop_duplicates()

    if len(positions) == 1:
        view_state = pdk.ViewState(
            longitude=float(positions.iloc[0]["longitude"]),
            latitude=float(positions.iloc[0]["latitude"]),
            zoom=12,
        )
    else:
        view_state = pdk.data_utils.compute_view(positions)
        view_state.zoom = min(view_state.zoom, 14)

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_points,
        get_position="[longitude, latitude]",
        get_fill_color=[131, 201, 255, 200],
        get_radius=120,
        radius_min_pixels=4,
        radius_max_pixels=12,
        pickable=True,
        auto_highlight=True,
    )

    project_map = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_provider="carto",
        map_style="dark",
        tooltip={
            "text": (
                "District: {district}\n"
                "Taluk: {taluk}\n"
                "RERA ID: {rera_id}\n"
                "Promoter: {promoter}"
            ),
            "style": {
                "backgroundColor": "#262730",
                "color": "white",
                "fontSize": "13px",
            },
        },
    )

    st.pydeck_chart(project_map, width="stretch", height=450)


st.caption(
    f"{len(map_data):,} of {len(filtered_df):,} registrations shown. "
    "Map screening checks numerical ranges and a broad regional window; "
    "project positions and district assignments still require source verification."
)

with st.expander("Coordinates needing review"):
    coordinate_review = filtered_df.loc[
        ~map_eligible,
        [
            "RERA ID",
            "Project Name",
            "district_display",
            "Latitude",
            "Longitude",
        ],
    ].rename(columns={"district_display": "District"})

    st.dataframe(
        coordinate_review,
        hide_index=True,
        width="stretch",
    )


# Project-size analysis follows the same sidebar scope and chart measure.
st.subheader("Project-size analysis")
st.caption(
    "Size is measured by recorded plot count. These are analysis bands, "
    "not residential/commercial classifications."
)

size_data = filtered_df.loc[
    filtered_df["project_size"].ne("Needs review")
].copy()

if size_data.empty:
    st.info("No positive whole-number plot counts in this selection.")
else:
    size_summary = (
        size_data.groupby("project_size", observed=True)
        .agg(
            registrations=("RERA ID", "size"),
            total_plots=("plot_count", "sum"),
        )
        .reindex(SIZE_LABELS, fill_value=0)
        .rename_axis("project_size")
        .reset_index()
    )

    size_column, mix_column = st.columns(2)

    with size_column:
        st.markdown("#### Activity by project size")
        size_figure = px.bar(
            size_summary,
            x="project_size",
            y=measure_column,
            labels={"project_size": "Project size", measure_column: chart_measure},
            hover_data={"registrations": ":,.0f", "total_plots": ":,.0f"},
            color_discrete_sequence=["#83C9FF"],
            category_orders={"project_size": SIZE_LABELS},
        )
        size_figure.update_layout(
            template="plotly_dark", paper_bgcolor="#0E1117",
            plot_bgcolor="#0E1117", height=420,
            margin=dict(l=10, r=10, t=20, b=10),
        )
        size_figure.update_yaxes(tickformat=",d", rangemode="tozero")
        st.plotly_chart(size_figure, width="stretch", theme=None)

    with mix_column:
        st.markdown("#### Size mix in top districts")
        district_mix = (
            size_data.dropna(subset=["district_clean"])
            .groupby(["district_clean", "project_size"], observed=True, as_index=False)
            .agg(
                registrations=("RERA ID", "size"),
                total_plots=("plot_count", "sum"),
            )
        )
        top_size_districts = (
            district_mix.groupby("district_clean")[measure_column]
            .sum().nlargest(10).index.tolist()
        )
        district_mix = district_mix.loc[
            district_mix["district_clean"].isin(top_size_districts)
        ]

        if district_mix.empty:
            st.info("No recognized districts with usable plot counts.")
        else:
            mix_figure = px.bar(
                district_mix, x=measure_column, y="district_clean",
                color="project_size", orientation="h", barmode="stack",
                labels={
                    "district_clean": "District", "project_size": "Project size",
                    measure_column: chart_measure,
                },
                category_orders={"project_size": SIZE_LABELS},
                color_discrete_sequence=[
                    "#83C9FF", "#FF4B4B", "#29B09D", "#FFD166", "#B692F6",
                ],
            )
            mix_figure.update_layout(
                template="plotly_dark", paper_bgcolor="#0E1117",
                plot_bgcolor="#0E1117", height=420,
                margin=dict(l=10, r=10, t=20, b=10),
            )
            mix_figure.update_yaxes(categoryorder="total ascending")
            mix_figure.update_xaxes(tickformat=",d", rangemode="tozero")
            st.plotly_chart(mix_figure, width="stretch", theme=None)

st.caption(
    f"{filtered_df['project_size'].eq('Needs review').sum():,} records excluded "
    "from size analysis for missing or invalid plot counts. "
    "Unresolved district labels are excluded from the district size-mix chart."
)

# Promoter rankings and project drill-down.
st.subheader("Promoter activity")

promoter_summary = (
    filtered_df.groupby("promoter_key", as_index=False)
    .agg(
        promoter=("promoter_clean", "first"),
        registrations=("RERA ID", "size"),
        total_plots=("Project Plots", "sum"),
        recognized_districts=("district_clean", "nunique"),
    )
    .sort_values(
        [measure_column, "promoter"],
        ascending=[False, True],
    )
)

if promoter_summary.empty:
    st.info("No usable promoter names in this selection.")
else:
    st.caption(
        f"Ranked by {chart_measure.lower()} within the sidebar scope. "
        "Activity means records in this dataset, not current construction status."
    )

    ranking_column, summary_column = st.columns(2)

    with ranking_column:
        st.markdown("#### Top 10 promoter name groups")

        top_promoters = (
            promoter_summary.head(10)
            .sort_values(measure_column)
        )

        promoter_figure = px.bar(
            top_promoters,
            x=measure_column,
            y="promoter",
            orientation="h",
            labels={
                "promoter": "Promoter",
                measure_column: chart_measure,
            },
            hover_data={
                "registrations": ":,.0f",
                "total_plots": ":,.0f",
                "recognized_districts": True,
            },
            color_discrete_sequence=["#83C9FF"],
        )

        promoter_figure.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0E1117",
            plot_bgcolor="#0E1117",
            height=450,
            margin=dict(l=10, r=10, t=20, b=10),
        )
        promoter_figure.update_xaxes(
            tickformat=",d",
            rangemode="tozero",
        )

        st.plotly_chart(
            promoter_figure,
            width="stretch",
            theme=None,
        )

    with summary_column:
        st.markdown("#### Promoter summary")

        st.dataframe(
            promoter_summary[
                [
                    "promoter",
                    "registrations",
                    "total_plots",
                    "recognized_districts",
                ]
            ].rename(
                columns={
                    "promoter": "Promoter",
                    "registrations": "Registrations",
                    "total_plots": "Recorded plots",
                    "recognized_districts": "Recognized districts",
                }
            ),
            hide_index=True,
            width="stretch",
            height=450,
        )

    # This selector affects only the promoter detail section.
    promoter_labels = promoter_summary.set_index(
        "promoter_key"
    )["promoter"].to_dict()

    selected_promoter = st.selectbox(
        "Inspect a promoter",
        options=[""] + promoter_summary["promoter_key"].tolist(),
        format_func=lambda key: (
            "Choose a promoter"
            if key == ""
            else promoter_labels[key]
        ),
    )

    if selected_promoter:
        promoter_projects = filtered_df.loc[
            filtered_df["promoter_key"].eq(selected_promoter)
        ].copy()

        locations = sorted(
            promoter_projects["district_clean"]
            .dropna()
            .unique()
            .tolist()
        )

        # Display uploaded names as text rather than interpreting Markdown.
        st.text(promoter_labels[selected_promoter])
        st.caption(
            f"{len(promoter_projects):,} registrations · "
            f"{promoter_projects['Project Plots'].sum():,} recorded plots"
        )
        st.text(
            "Recognized districts: "
            + (", ".join(locations) if locations else "None available")
        )

        st.dataframe(
            promoter_projects[
                [
                    "RERA ID",
                    "Project Name",
                    "district_display",
                    "Project Taluk",
                    "Project Village",
                    "Project Plots",
                    "Registration Date",
                ]
            ].rename(columns={"district_display": "District"}),
            hide_index=True,
            width="stretch",
        )

# Project detail table.
st.subheader("Project explorer")

st.caption(
    "Build a project shortlist within the sidebar scope. "
    "These controls affect this table and its download."
)
explorer_df = filtered_df.copy()

search_query = st.text_input(
    "Search project name, promoter or RERA ID",
    placeholder="Enter a name or registration ID",
).strip()

if search_query:
    matches = pd.Series(False, index=explorer_df.index)
    for column in ["Project Name", "Promoter name", "RERA ID"]:
        matches |= explorer_df[column].astype("string").str.contains(
            search_query, case=False, regex=False, na=False,
        )
    explorer_df = explorer_df.loc[matches]

size_filter_column, taluk_filter_column, village_filter_column = st.columns(3)

with size_filter_column:
    present_sizes = explorer_df["project_size"].astype("string").unique().tolist()
    selected_sizes = st.multiselect(
        "Project sizes",
        options=[size for size in SIZE_LABELS + ["Needs review"] if size in present_sizes],
        help="Leave empty to include all sizes.",
    )
    if selected_sizes:
        explorer_df = explorer_df.loc[explorer_df["project_size"].isin(selected_sizes)]

with taluk_filter_column:
    selected_taluks = st.multiselect(
        "Taluks", options=sorted(explorer_df["Project Taluk"].dropna().unique().tolist()),
        help="Options follow the search and project-size selection.",
    )
    if selected_taluks:
        explorer_df = explorer_df.loc[explorer_df["Project Taluk"].isin(selected_taluks)]

with village_filter_column:
    selected_villages = st.multiselect(
        "Villages", options=sorted(explorer_df["Project Village"].dropna().unique().tolist()),
        help="Options also follow the selected taluks.",
    )
    if selected_villages:
        explorer_df = explorer_df.loc[explorer_df["Project Village"].isin(selected_villages)]

explorer_df = explorer_df.sort_values(
    "registration_date", ascending=False, na_position="last",
)

st.caption(
    f"{len(explorer_df):,} shortlisted registrations · "
    f"{explorer_df['plot_count'].sum():,.0f} recorded plots with valid counts"
)

display_df = explorer_df[
    [
        "RERA ID",
        "Project Name",
        "Promoter name",
        "district_display",
        "Project Taluk",
        "Project Village",
        "Project Plots",
        "project_size",
        "Registration Date",
    ]
].rename(columns={"district_display": "District", "project_size": "Project size"})

if display_df.empty:
    st.info("No projects match these filters. Clear a selection or try another search.")

st.dataframe(
    display_df,
    hide_index=True,
    width="stretch",
)

# Keep text fields as text when the CSV is opened in spreadsheet software.
export_df = display_df.copy()
for column in export_df.select_dtypes(include=["object", "string"]).columns:
    export_df[column] = export_df[column].map(
        lambda value: "'" + value
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@"))
        else value
    )

csv_data = export_df.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "Download project shortlist (CSV)",
    data=csv_data,
    file_name="rera_project_shortlist.csv",
    mime="text/csv",
    disabled=display_df.empty,
    on_click="ignore",
)
