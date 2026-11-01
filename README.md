# Data-Analytics-Challenge

Analysis of a fictional analytics export for a student placement website (1 Sep 2025 to 28 Feb 2026), plus the Databricks setup tasks. All data is fictional.

## Folder structure

| Path | Contents |
|---|---|
| `data/raw/` | The supplied raw files (never changed; not stored in this repo) |
| `src/Data_Cleaner_SCR.py` | Cleans the raw files |
| `src/Data_Metrics_SCR.py` | Builds the daily summary and breakdowns |
| `notebooks/Data_Profiling.ipynb` | Profile of the raw data and its quality problems |
| `notebooks/01_analysis.ipynb` | Charts and answers to the four questions |
| `outputs/` | Analysis-ready CSV files and check results |
| `reports/` | Findings presentation, quality note and chart images |

## How to run

1. Install Python 3 and open a terminal in the project folder.
2. Create and activate a virtual environment, then install the packages:
   
   python -m venv venv
   venv\Scripts\activate (Mac/Linux: source venv/bin/activate)
   pip install -r requirements.txt
   
3. Put the supplied files (`sessions.csv`, `events.csv`, `pages.csv`, `campaigns.csv`) in `data/raw/`.
4. Run the two scripts **from the project root, in this order**:

python src/Data_Cleaner_SCR.py
python src/Data_Metrics_SCR.py

5. To see the profiling and the analysis, run `jupyter notebook`, open the notebooks in `notebooks/`, and choose Kernel > Restart & Run All. The analysis notebook needs step 4 first, because it reads the files in `outputs/`.

The scripts rebuild every output from the raw files, so running them again gives identical results.

## Dependencies

Python 3, `pandas`, `matplotlib`, `jupyter` (full list in `requirements.txt`).

## Outputs (`outputs/`)

| File | One row per |
|---|---|
| `sessions_clean.csv` | session |
| `events_clean.csv` | event |
| `session_facts.csv` | session, with page view and click flags |
| `daily_summary.csv` | day (UTC session start date) |
| `breakdown_channel.csv`, `breakdown_device.csv` | channel / device |
| `exclusion_log.csv` | what was removed or changed, with counts |
| `dq_checks.csv`, `metrics_checks.csv` | pass/fail results of the data-quality checks |

## Method in brief

- **Cleaning:** removed exact duplicates and orphan events, tidied labels, marked blanks as `Unknown`, blanked invalid values, and normalised URLs to page paths. The details and counts are in the quality and assumptions note.
- **Eligible sessions:** all clean sessions except 1,350 suspected automated sessions, which are flagged and excluded from rates but not deleted.
- **Email click rate:** sessions with at least one `application_email_click` divided by eligible sessions. It shows intent, not a completed application.
- **Data Analyst question:** the data has no Data Analyst page, so Data Engineer is used as a stand-in.

## Time spent

Approximately 3 hours on the website data challenge

