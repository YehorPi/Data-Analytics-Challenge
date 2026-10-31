
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

VALID_DEVICES = {"desktop", "mobile", "tablet"}
VALID_EVENTS = {"page_view", "apply_cta_click", "application_email_click", "video_play"}

# Mapping suggested by the data dictionary. (direct)+(none) -> Direct.
CHANNEL_MAP = {
    "organic": "Organic Search",
    "social": "Social",
    "email": "Email",
    "referral": "Referral",
    "(none)": "Direct",
}

# Found during profiling: 1,350 one-page-view desktop sessions,
# exactly 450 per day on 14-16 Jan 2026. Flagged, NOT deleted.
SUSPECT_SOURCES = {"traffic-check.example"}

log = []  # exclusion / change log, written to outputs/exclusion_log.csv


def record(table, action, reason, n):
    log.append({"table": table, "action": action, "reason": reason, "rows_or_values": int(n)})


def read_raw(name):
    # dtype=str and keep_default_na=False: nothing is silently converted.
    return pd.read_csv(RAW / f"{name}.csv", dtype=str, keep_default_na=False)


def normalise_path(url):
    """Full URL -> canonical page path: drop query string and fragment,
    drop trailing slash (except for the home page '/')."""
    path = urlsplit(url.strip()).path or "/"
    if path != "/":
        path = path.rstrip("/")
    return path


sessions = read_raw("sessions")
events = read_raw("events")
pages = read_raw("pages")
raw_counts = {"sessions": len(sessions), "events": len(events)}


n = sessions.duplicated().sum()
sessions = sessions.drop_duplicates()
record("sessions", "removed rows", "exact duplicate row", n)

# Tidy device_category: trim spaces, lower-case, then validate.
before = sessions["device_category"].copy()
sessions["device_category"] = sessions["device_category"].str.strip().str.lower()
record("sessions", "values changed", "device_category trimmed/lower-cased",
       (before != sessions["device_category"]).sum())
bad_dev = ~sessions["device_category"].isin(VALID_DEVICES)
sessions.loc[bad_dev, "device_category"] = "unknown"
record("sessions", "values changed", "device_category not in valid set -> unknown", bad_dev.sum())

# Timestamps: strict ISO parse; keep the original text for traceability.
sessions["session_start_utc"] = pd.to_datetime(
    sessions["session_start_utc"], errors="coerce", utc=True)
bad_ts = sessions["session_start_utc"].isna()
record("sessions", "removed rows", "unparseable session_start_utc", bad_ts.sum())
sessions = sessions[~bad_ts]
sessions["session_date"] = sessions["session_start_utc"].dt.strftime("%Y-%m-%d")

# Missing values become explicit 'Unknown' labels (we do not guess).
for col in ["source", "medium", "country_code"]:
    blank = sessions[col].str.strip() == ""
    sessions.loc[blank, col] = "Unknown"
    record("sessions", "values changed", f"blank {col} -> 'Unknown'", blank.sum())
sessions["campaign_id"] = sessions["campaign_id"].replace("", pd.NA)

sessions["channel"] = sessions["medium"].map(CHANNEL_MAP).fillna("Unknown")

# Landing page: keep original URL, add canonical path.
sessions["landing_page_path"] = sessions["landing_page_url"].map(normalise_path)

# Flag (do not delete) suspected automated traffic.
sessions["is_suspected_automated"] = sessions["source"].isin(SUSPECT_SOURCES)
record("sessions", "flagged only", "suspected automated traffic (source in SUSPECT_SOURCES)",
       sessions["is_suspected_automated"].sum())

# Join page attributes. pages.csv is unique on page_path, so this cannot add rows.
assert pages["page_path"].is_unique
n_before = len(sessions)
sessions = sessions.merge(
    pages[["page_path", "page_group", "placement_role"]]
    .rename(columns={"page_path": "landing_page_path",
                     "page_group": "landing_page_group",
                     "placement_role": "landing_placement_role"}),
    on="landing_page_path", how="left")
assert len(sessions) == n_before, "join changed the session count!"
sessions["landing_page_group"] = sessions["landing_page_group"].fillna("unmapped")


n = events.duplicated().sum()
events = events.drop_duplicates()
record("events", "removed rows", "exact duplicate row", n)

bad_name = ~events["event_name"].isin(VALID_EVENTS)
record("events", "removed rows", "event_name not in the 4 documented types", bad_name.sum())
events = events[~bad_name]

# Referential integrity: every event must belong to a kept session.
orphan = ~events["session_id"].isin(sessions["session_id"])
record("events", "removed rows", "orphan: session_id not in cleaned sessions", orphan.sum())
events = events[~orphan]

# Timestamps: keep the event (counts are by session date) but null the bad
# timestamp and flag it, so ordered-funnel logic can ignore it.
events["event_timestamp_utc"] = pd.to_datetime(
    events["event_timestamp_utc"], errors="coerce", utc=True)
events["has_valid_timestamp"] = events["event_timestamp_utc"].notna()
record("events", "values changed", "unparseable event_timestamp_utc -> null, flagged",
       (~events["has_valid_timestamp"]).sum())

# Engagement seconds: numeric, negative is impossible -> null the measurement
# (the page view itself still happened).
events["engagement_seconds"] = pd.to_numeric(events["engagement_seconds"], errors="coerce")
neg = events["engagement_seconds"] < 0
events.loc[neg, "engagement_seconds"] = pd.NA
record("events", "values changed", "negative engagement_seconds -> null", neg.sum())

# URLs
events["page_path"] = events["page_url"].map(normalise_path)
events = events.merge(
    pages[["page_path", "page_group", "placement_role"]], on="page_path", how="left")
events["page_group"] = events["page_group"].fillna("unmapped")

# Data quality checks
checks = []


def check(name, passed, detail=""):
    checks.append({"check": name, "result": "PASS" if passed else "FAIL", "detail": detail})


check("sessions: session_id unique", sessions["session_id"].is_unique)
check("events: event_id unique", events["event_id"].is_unique)
check("events: no orphan session_id", events["session_id"].isin(sessions["session_id"]).all())
check("sessions: all timestamps valid and inside 2025-09-01..2026-02-28",
      sessions["session_date"].between("2025-09-01", "2026-02-28").all())
check("sessions: device_category valid", sessions["device_category"].isin(VALID_DEVICES).all())
check("sessions: every landing page maps to the catalogue",
      (sessions["landing_page_group"] != "unmapped").all(),
      f"unmapped={int((sessions['landing_page_group'] == 'unmapped').sum())}")
check("events: every page maps to the catalogue",
      (events["page_group"] != "unmapped").all(),
      f"unmapped={int((events['page_group'] == 'unmapped').sum())}")
check("events: engagement_seconds non-negative (nulls allowed)",
      (events["engagement_seconds"].dropna() >= 0).all())
check("events: non-page_view events have 0 engagement",
      (events.loc[events["event_name"] != "page_view", "engagement_seconds"] == 0).all())
check("sessions: every session has >= 1 page_view",
      sessions["session_id"].isin(events.loc[events["event_name"] == "page_view", "session_id"]).all())

removed = pd.DataFrame(log)
rem_s = removed[(removed.table == "sessions") & (removed.action == "removed rows")].rows_or_values.sum()
rem_e = removed[(removed.table == "events") & (removed.action == "removed rows")].rows_or_values.sum()
check("reconciliation: raw sessions - removed = clean sessions",
      raw_counts["sessions"] - rem_s == len(sessions),
      f"{raw_counts['sessions']} - {rem_s} = {len(sessions)}")
check("reconciliation: raw events - removed = clean events",
      raw_counts["events"] - rem_e == len(events),
      f"{raw_counts['events']} - {rem_e} = {len(events)}")


#This section produce outputs
sessions["session_start_utc"] = sessions["session_start_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
events["event_timestamp_utc"] = events["event_timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

sessions.sort_values("session_id").to_csv(OUT / "sessions_clean.csv", index=False)
events.sort_values("event_id").to_csv(OUT / "events_clean.csv", index=False)
removed.to_csv(OUT / "exclusion_log.csv", index=False)
pd.DataFrame(checks).to_csv(OUT / "dq_checks.csv", index=False)

print(f"sessions: {raw_counts['sessions']} raw -> {len(sessions)} clean")
print(f"events:   {raw_counts['events']} raw -> {len(events)} clean\n")
print(removed.to_string(index=False))
print()
print(pd.DataFrame(checks).to_string(index=False))
