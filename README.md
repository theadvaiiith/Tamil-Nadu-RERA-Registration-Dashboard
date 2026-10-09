# Tamil Nadu RERA Registration Dashboard

An interactive data analytics dashboard for exploring Tamil Nadu real estate registrations, identifying concentrations of registered development, comparing promoter activity, and building project shortlists.

The project uses **Streamlit, Pandas, SQLite, Plotly, and PyDeck**. A new Excel workbook with the same source headers can be validated and imported through the dashboard, replacing the stored dataset and updating the analysis without editing the application code.

Built as a data analytics internship project by **Advaith Krishna S**.

## Business purpose

Registration records help a company decide which locations and promoter groups warrant further research or outreach. The dashboard turns project-level records into summaries that can be filtered, compared, and exported.

| Business question | Dashboard capability | Potential use |
| --- | --- | --- |
| Where is registered development concentrated? | District rankings, monthly activity, and a project map | Identify locations to investigate or target |
| Which promoter names appear most frequently? | Promoter rankings, plot totals, district coverage, and project drill-down | Build a list of potential clients, partners, or competitors |
| What project sizes dominate an area? | Plot-count bands and district size mix | Understand the scale of registered projects |
| Is activity shifting between locations? | District trends and monthly shares | Support location and expansion research |
| Which projects match a particular search? | Searchable explorer with location and size filters | Create a project shortlist for follow-up |

These are indicators of **registered activity**, not direct measures of sales, construction progress, prices, or customer demand.

## Dashboard features

### Shared filters and summary

- District selection; an empty selection includes all districts.
- An inclusive registration-date range.
- Four summary cards: registrations, recorded plots, recognized districts, and promoter name groups.
- Insight cards showing the leading district, most active promoter name group, and most common project-size band.
- Insight percentages calculated against all registrations in the sidebar selection. Ties are identified.
- A chart-measure selector for **Registrations** or **Recorded plots**.
- A light gray background, white cards, and green accents. Card labels and values wrap instead of being shortened with ellipses.

### Overview

- Monthly registration or recorded-plot trends.
- Leading district rankings.
- Months with no records in the selected scope are shown as zero.

### District Analysis

- Compare selected districts over time.
- View absolute activity or monthly share.
- Explore project locations on an interactive map.
- Hover over a point to see its **district, taluk, RERA ID, and promoter name**.
- Review records whose coordinates do not pass the map screening.
- Examine project-size distribution and size mix across leading districts.

### Promoters

- Rank promoter name groups by registrations or recorded plots.
- Inspect a summary table with counts, plots, and recognized district coverage.
- Select a promoter group to view its projects and locations.

### Project Explorer

- Search project names, promoter names, or RERA IDs using literal, case-insensitive text.
- Narrow the shortlist by project size, taluk, and village.
- View records ordered by registration date, newest first.
- Download the current shortlist as a UTF-8 CSV suitable for opening in Excel.

Explorer filters affect the explorer table and its download. The promoter selector affects its detail section. These controls do not change the shared KPI cards or other tabs.

## Technology stack

| Component | Responsibility |
| --- | --- |
| Python | Application and data preparation |
| Streamlit | Dashboard, filters, upload controls, and downloads |
| Pandas | Excel reading, preparation, filtering, and aggregation |
| OpenPyXL | `.xlsx` workbook support |
| SQLite | Local storage for prepared registrations and import metadata |
| Plotly | Interactive charts |
| PyDeck | Project map and hover details |
| Git / GitHub | Version control and source sharing |

SQLite is accessed through Python's built-in `sqlite3` module. A separate database server is not required.

## Data workflow

The workbook is read into Pandas, validated, and processed by the functions in `data_prep.py`. Prepared records are stored in SQLite. On each dashboard rerun, the app reads the `projects` table into Pandas and applies the selected filters before generating its summaries, charts, map, and tables.

For subsequent imports:

1. Upload an `.xlsx` workbook from the sidebar.
2. Validate its headers, registration IDs, plot counts, and dates.
3. Review the import summary and data-quality flags.
4. Click **Replace dataset** to import the complete workbook.
5. The app writes a staging table, then swaps the project table and updates import metadata in a database transaction.
6. After a successful import, the app reruns and displays the new dataset.

**An import replaces the complete dataset; it does not append rows or merge incremental changes.** Include all records you want to retain in the new workbook. The app does not watch a folder, poll for new files, or scrape a live registration service.

## Project files

| Path | Purpose |
| --- | --- |
| `app.py` | Dashboard, upload validation, dataset replacement, and visual styling |
| `data_prep.py` | Coordinate, district, date, and promoter preparation functions |
| `inspect_data.py` | Local workbook inspection and data-quality checks |
| `load_data.py` | Initial Excel-to-SQLite import |
| `requirements.txt` | Python dependencies for the project |
| `.streamlit/config.toml` | Streamlit's light green theme |
| `.gitignore` | Excludes local data, databases, virtual environments, and credentials |
| `README.md` | Project documentation |
| `data/Cleaned RERA Data.xlsx` | Local input workbook; excluded from Git |
| `data/rera.db` | Local SQLite database; excluded from Git |

The dashboard requires the supporting project files, particularly `data_prep.py`; `app.py` is not a standalone application.

## Run locally

### 1. Get the source

Clone the repository or download its source, then open a terminal in the project folder. Use a Python version compatible with the dependencies in `requirements.txt`.

### 2. Create and activate a virtual environment

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

The required packages include `streamlit`, `pandas`, `openpyxl`, `plotly`, and `pydeck`.

### 4. Provide the local workbook

```bash
mkdir -p data
```

On Windows, create the `data` folder in File Explorer if needed.

Place your compatible workbook at:

```text
data/Cleaned RERA Data.xlsx
```

The workbook and database are not supplied with the source repository. Obtain a workbook you are authorized to use.

### 5. Inspect and import the initial dataset

```bash
python inspect_data.py
python load_data.py
```

Use `load_data.py` for the initial import. Once the database exists, use the dashboard's **Replace dataset** workflow for subsequent full-workbook updates.

### 6. Start the dashboard

```bash
streamlit run app.py
```

Open the local address printed in the terminal. Stop the server with **Control+C**. Restart it after changing `.streamlit/config.toml`.

## Excel input contract

The dashboard reads the **first worksheet** of an `.xlsx` workbook. It expects the following 18 source headers. Header order can vary, and leading/trailing header whitespace is removed. Missing, extra, or duplicate headers are rejected by the uploader.

| Header | Expected content |
| --- | --- |
| `S. No` | Source serial number |
| `RERA ID` | Non-empty, unique registration identifier |
| `Registration Date` | Excel date cell or readable date text, preferably day/month/year |
| `Promoter name` | Source promoter name |
| `Project Name` | Project name |
| `Latitude` | Latitude in decimal degrees |
| `Longitude` | Longitude in decimal degrees |
| `Approval Board` | Approval authority or board |
| `Project Plots` | Positive whole-number plot count |
| `Project District` | District name |
| `Project Taluk` | Taluk name |
| `Project Village` | Village name |
| `Approval Date` | Excel date cell or readable date text |
| `Current Status of the Project` | Source project-status text |
| `Days after Approval` | Source value; retained for reference |
| `Approval Period` | Source approval-period value |
| `Plot Range` | Source size-band value; dashboard bands are recalculated |
| `Year` | Source year; a registration year is derived from parsed dates |

Use the source headers when preparing a future workbook, rather than exporting the database's additional derived columns into it.

## Validation and preparation

The uploader rejects empty workbooks, missing or duplicate RERA IDs, invalid plot counts, unreadable registration dates, and raw numeric cells in the two date columns. Excel date cells should be stored as dates rather than unformatted serial numbers.

The preparation pipeline also:

- Converts coordinates to numbers and flags invalid pairs.
- Normalizes district names using the project's recognized names and aliases; unresolved labels remain available as **Needs review**.
- Parses dates and flags approval/registration chronology issues.
- Cleans promoter whitespace and groups names without regard to capitalization.
- Builds project-size bands from valid plot counts.

Review flags do not all cause an import to fail. For example, records with questionable coordinates can remain available for non-map analysis while being excluded from the map.

### Project-size bands

| Band | Recorded plots |
| --- | --- |
| 1–30 plots | 1 to 30 |
| 31–60 plots | 31 to 60 |
| 61–100 plots | 61 to 100 |
| 101–200 plots | 101 to 200 |
| More than 200 plots | Above 200 |

Records with missing or invalid plot counts are labeled **Needs review** and excluded from size charts. Such counts are rejected for new uploads.

## Database design

| Table | Contents |
| --- | --- |
| `projects` | Source records and derived preparation fields |
| `import_metadata` | Latest imported filename, row count, and UTC import timestamp |

Dashboard imports create a unique index on `RERA ID`. A staging table is written before the transactional replacement. If the swap fails, the transaction is rolled back and the staging table is cleaned up.

The database stores the current dataset, not a history of every workbook import. The initial loader may not create import metadata; the dashboard creates it when a replacement import succeeds.

The app currently retrieves records with SQL and performs its interactive aggregations in Pandas. For example, the stored data can also be queried directly:

```sql
SELECT
    district_clean AS district,
    COUNT(*) AS registrations,
    SUM("Project Plots") AS recorded_plots
FROM projects
WHERE district_clean IS NOT NULL
GROUP BY district_clean
ORDER BY registrations DESC;
```

This example summarizes the whole stored dataset, rather than the dashboard's current filter selection.

## Interpreting the results

- **Registrations** counts records in the selected date and district scope. Unique RERA IDs make each record a distinct registration.
- **Recorded plots** sums the source plot counts. It is not a sales or inventory measure.
- **Recognized districts** excludes unresolved district labels.
- **Promoter name groups** groups cleaned names; it does not establish legally unique developers or companies.
- **District monthly share** uses all recognized districts in the sidebar scope as its denominator, including comparison lines that are hidden. Months with no activity have undefined shares.
- **Monthly trends** include only the selected dates. The first and last months may be partial.
- **Zero months** mean no records in the selected dataset and scope, not proof that no development occurred.

## Data coverage and limitations

The working cleaned dataset reported during development contains **2,372 registrations and 125,088 recorded plots**, with 18 source columns and no duplicate RERA IDs. These are reference totals for that workbook, not hard-coded dashboard values. Future imports change the totals.

Records without location data were removed during the user's initial workbook preparation. Consequently, this dataset is a subset of the original extract; district totals and trends describe that subset and may be affected by location-data availability.

The map accepts numeric coordinate pairs within global limits and screens them using a broad regional window: latitude **8–14** and longitude **76–81**. This rectangle is not a Tamil Nadu boundary check. Passing it does not verify a project's position or confirm that it belongs to the recorded district. Suspicious coordinates are flagged rather than automatically guessed or converted from an unknown format.

Overlapping coordinates can place multiple registrations at the same map position. A hover tooltip identifies the picked point; use the explorer to inspect additional records.

The source does not provide a confirmed residential/commercial classification or an expected completion date. Therefore, the dashboard does not currently offer project-type analysis, upcoming completion alerts, or completion forecasts. Approval dates and approval periods are not treated as promised completion dates.

The app uses an uploaded workbook, not a live connection to the official registration portal. It has no user authentication or role-based permissions and is intended for local analysis in its current form. Map basemap tiles require an internet connection.

## Verification checklist

After setup or a dashboard change:

- [ ] Confirm the all-data totals against the local workbook. For the development workbook: 2,372 registrations and 125,088 plots.
- [ ] Change district and date filters and check all tabs.
- [ ] Check empty selections and periods with no matching records.
- [ ] Confirm complete KPI labels and values are visible.
- [ ] Hover over map points and verify all four tooltip fields.
- [ ] Inspect records in the coordinate-review section.
- [ ] Check a promoter group against its project table.
- [ ] Search and filter the explorer, then confirm the CSV matches its shortlist.
- [ ] Use a separate local copy of the database to exercise workbook replacement and invalid-upload handling without changing the working dataset.

This checklist describes manual acceptance checks, not an automated test suite.

## Troubleshooting

| Issue | Suggested action |
| --- | --- |
| Database not found | Confirm the workbook path and run `python load_data.py` for the initial import |
| Module not found | Activate `.venv` and install `requirements.txt` |
| Upload validation fails | Check the first worksheet, exact headers, IDs, plot counts, and date cells |
| Map shows fewer points than the registration count | Review the coordinate screening; excluded map records remain in applicable non-map analysis |
| Theme does not change | Confirm the file is `.streamlit/config.toml`, then stop and restart Streamlit |
| No matching projects | Expand the date range or clear district, search, and explorer selections |
| Initial loader reports an existing table | Use the dashboard's replacement import for an existing dataset; do not repeatedly run the initial loader |

## Source sharing and future work

Keep workbooks, databases, virtual environments, and credentials outside version control. The repository contains application code and configuration; company data remains local. No license is currently specified; add one deliberately before offering the code under particular reuse terms.

Possible extensions include verified expected-completion and project-type fields, documented coordinate-format conversion, true boundary validation, workbook import history, and access controls for a hosted company deployment. These are future enhancements, not implemented features.
