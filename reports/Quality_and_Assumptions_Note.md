# Data-Analytics-Challenge

# Quality and Assumptions Note

## 1. Scope and grain of the outputs

| Output file | One row per | Rows |
|---|---|---|
| `sessions_clean.csv` | session (`session_id`) | 20,748 |
| `events_clean.csv` | event (`event_id`) | 45,366 |
| `session_facts.csv` | session, with page view and click flags | 20,748 |
| `daily_summary.csv` | day (session start date, UTC) | 181 |
| `breakdown_channel.csv`, `breakdown_device.csv` | channel / device | 6 / 3 |

The raw files in `data/raw/` are never changed. Every output is rebuilt from them each time the scripts run.

## 2. Records removed or changed

| Table | Action | Reason | Count |
|---|---|---|---|
| sessions | removed | exact duplicate rows | 30 |
| events | removed | exact duplicate rows | 120 |
| events | removed | orphan: session does not exist | 12 |
| sessions | changed, kept | device labels tidied (`Mobile`, ` DESKTOP`) | 60 |
| sessions | changed, kept | blank source, blank medium, blank country set to `Unknown` | 45, 45, 90 |
| events | changed, kept | invalid timestamp blanked and flagged | 8 |
| events | changed, kept | negative engagement seconds blanked | 10 |
| sessions | flagged, kept | suspected automated traffic | 1,350 |

Raw 20,778 sessions became 20,748 clean sessions, and raw 45,498 events became 45,366 clean events. Rates use the 19,398 "eligible" sessions, which are all clean sessions except the flagged automated ones.

## 3. Cleaning decisions

| Issue | Decision | Why |
|---|---|---|
| Exact duplicate rows | Remove | Every duplicated ID was a perfect copy, so no information is lost |
| Orphan events | Remove | Without a session we cannot tell device or channel |
| Blank source, medium, country | Label `Unknown`, keep the row | We do not guess, and the sessions are still real visits (9 also carry a campaign) |
| Invalid event timestamp | Keep the event, blank the timestamp, flag it | Daily counts use the session date, so the page view still counts |
| Negative engagement seconds | Blank the number, keep the page view | The value is impossible, but the view happened |
| URL variations (query string, fragment, trailing slash) | Normalise to the page path, keep the original URL | Otherwise one page splits into many; after cleaning, all URLs match the page catalogue |
| Suspected automated traffic | Flag, exclude from rates, do not delete | Keeps the issue visible and the decision reversible |

## 4. Checks performed

Both scripts run their checks every time and save the results (`dq_checks.csv`, `metrics_checks.csv`). All 18 passed.

- **Cleaning script (11):** session and event IDs are unique; every event has a session; all session dates fall inside 1 Sep 2025 to 28 Feb 2026; device values are valid; event names are the four documented types; every landing page and event page is in the catalogue; every session has at least one page view; raw minus removed equals clean for both tables.
- **Metrics script (7):** the join does not change the session count; daily totals and the channel breakdown add up to the session totals; email-click sessions never exceed sessions; every session has at least one page view; all 181 days are present.

## 5. Assumptions

- A day is the UTC date the session started.
- Channel comes from `medium` (organic = Organic Search, social = Social, email = Email, referral = Referral, `(none)` = Direct).
- The email click rate is sessions with at least one email click, divided by eligible sessions. Each session counts once and a click shows intent, not a completed application.
- Automated traffic is identified by its source name (`traffic-check.example`), after finding that all 1,350 sessions behave identically.
- The page catalogue has no Data Analyst page, so Data Engineer is used as a stand-in.
- A session is interested in a role if it viewed that role's page at least once. Role totals are not additive.
- The application journey is measured with distinct sessions and no required order, because visitors can land directly on `/application`.

## 6. Proposed daily pipeline

**Loading.** Each day the new export is saved unchanged in a dated raw folder and the raw store is never edited. The job processes by session date and writes one partition per day. Rows are matched on their keys (`session_id`, `event_id`), so a row is inserted if new and replaced if it already exists.

**Safe reruns.** The job rebuilds each day's output from raw, writes to a temporary location and swaps it in only if the checks pass. Running it twice on the same input gives identical results. I confirmed this by running the current scripts three times and comparing the output files.

**Monitoring.** Hard checks stop the run: duplicate keys, unreadable timestamps, a mismatch in the row-count reconciliation or an unknown page. Soft checks raise a warning: a sudden jump in daily sessions, a source whose sessions all have one page view and no clicks, more blanks or orphans than usual or a new device or event value. The number of rows removed is saved each day, so changes in data quality can be tracked.

**Late and corrected data.** Events can arrive after their session, so each run also reprocesses the last 7 days. Orphan events go to a holding table and are retried when their session arrives, instead of being deleted. If a corrected file arrives, the latest received row for each key wins, and the old version is kept in the raw store for audit. Daily reports are rebuilt for the affected dates.

## 7. Known limitations

- The data is synthetic and covers only tracked sessions. Untracked visits, applications completed, spend and impressions are unknown.
- The automated-traffic rule covers one source name, so a new automated source would not be caught until the monitoring warning flags it.
- Campaign overlap with traffic changes is not proof that campaigns caused them.