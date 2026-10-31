
import pandas as pd

sessions = pd.read_csv("outputs/sessions_clean.csv", keep_default_na=False)
events = pd.read_csv("outputs/events_clean.csv", keep_default_na=False)

# Turn each event into 1/0 flags, then collapse to one row per session.
events["is_page_view"] = events["event_name"] == "page_view"
events["is_apply_click"] = events["event_name"] == "apply_cta_click"
events["is_email_click"] = events["event_name"] == "application_email_click"

per_session = events.groupby("session_id").agg(
    page_views=("is_page_view", "sum"),         # how many page views
    has_apply_click=("is_apply_click", "max"),  # at least one? True/False
    has_email_click=("is_email_click", "max"),
).reset_index()

# per_session has exactly one row per session_id, so this join cannot
# multiply sessions.
facts = sessions.merge(per_session, on="session_id", how="left")

# Produces Daily summary
facts["is_eligible"] = ~facts["is_suspected_automated"]
eligible = facts[facts["is_eligible"]]

daily = pd.DataFrame({
    "tracked_sessions": facts.groupby("session_date").size(),
    "eligible_sessions": eligible.groupby("session_date").size(),
    "page_views": eligible.groupby("session_date")["page_views"].sum(),
    "apply_click_sessions": eligible.groupby("session_date")["has_apply_click"].sum(),
    "email_click_sessions": eligible.groupby("session_date")["has_email_click"].sum(),
})

# Make sure every calendar day appears, even a day with no sessions.
all_days = pd.date_range("2025-09-01", "2026-02-28").strftime("%Y-%m-%d")
daily = daily.reindex(all_days).fillna(0).astype(int)
daily["email_click_rate"] = (daily["email_click_sessions"] / daily["eligible_sessions"]).round(4)
daily.index.name = "date"

# This section splits the metrics by acquisition channel, device or placement role
def breakdown(column):
    out = eligible.groupby(column).agg(
        eligible_sessions=("session_id", "size"),
        apply_click_sessions=("has_apply_click", "sum"),
        email_click_sessions=("has_email_click", "sum"),
    )
    out["email_click_rate"] = (out["email_click_sessions"] / out["eligible_sessions"]).round(4)
    return out.sort_values("eligible_sessions", ascending=False)

# This section makes sure the numbers add up and nothing was lost or counted twice
checks = {
    "session_facts has one row per session": len(facts) == len(sessions),
    "daily tracked_sessions adds up to all sessions": daily["tracked_sessions"].sum() == len(sessions),
    "daily eligible_sessions adds up to eligible sessions": daily["eligible_sessions"].sum() == len(eligible),
    "channel breakdown adds up to eligible sessions": breakdown("channel")["eligible_sessions"].sum() == len(eligible),
    "email-click sessions can't exceed eligible sessions": (daily["email_click_sessions"] <= daily["eligible_sessions"]).all(),
    "every session has page_views >= 1": (facts["page_views"] >= 1).all(),
    "181 days present (1 Sep 2025 - 28 Feb 2026)": len(daily) == 181,
}

# This section is responsible for saving the results
facts.to_csv("outputs/session_facts.csv", index=False)
daily.to_csv("outputs/daily_summary.csv")
breakdown("channel").to_csv("outputs/breakdown_channel.csv")
breakdown("device_category").to_csv("outputs/breakdown_device.csv")
pd.Series(checks, name="passed").rename_axis("check").to_csv("outputs/metrics_checks.csv")

print(daily.head(), "\n")
print(breakdown("channel"), "\n")
print(breakdown("device_category"), "\n")
print(pd.Series(checks).to_string())
