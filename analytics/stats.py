"""
Analytics module — uses Pandas & NumPy to derive task statistics.
"""

import pandas as pd
import numpy as np


def compute_analytics(tasks: list[dict]) -> dict:
    """
    Given a list of task dicts, return a statistics dictionary computed
    with Pandas DataFrames and NumPy aggregations.
    """
    if not tasks:
        return {
            "total": 0,
            "completed": 0,
            "pending": 0,
            "in_progress": 0,
            "completion_percentage": 0.0,
            "priority_breakdown": {"low": 0, "medium": 0, "high": 0},
            "status_breakdown": {"pending": 0, "in_progress": 0, "completed": 0},
        }

    df = pd.DataFrame(tasks)

    # ── Core counts (NumPy for the percentage) ──────────────────────────────
    total      = int(len(df))
    completed  = int((df["status"] == "completed").sum())
    pending    = int((df["status"] == "pending").sum())
    in_progress= int((df["status"] == "in_progress").sum())

    completion_pct = float(np.round((completed / total) * 100, 2)) if total else 0.0

    # ── Priority breakdown via Pandas value_counts ───────────────────────────
    priority_counts = df["priority"].value_counts().to_dict()
    priority_breakdown = {
        "low":    int(priority_counts.get("low",    0)),
        "medium": int(priority_counts.get("medium", 0)),
        "high":   int(priority_counts.get("high",   0)),
    }

    # ── Status breakdown ─────────────────────────────────────────────────────
    status_counts = df["status"].value_counts().to_dict()
    status_breakdown = {
        "pending":     int(status_counts.get("pending",     0)),
        "in_progress": int(status_counts.get("in_progress", 0)),
        "completed":   int(status_counts.get("completed",   0)),
    }

    # ── Tasks created per day (trend data) ──────────────────────────────────
    df["created_at"] = pd.to_datetime(df["created_at"])
    daily_counts = (
        df.groupby(df["created_at"].dt.date)
          .size()
          .reset_index(name="count")
    )
    trend = [
        {"date": str(row["created_at"]), "count": int(row["count"])}
        for _, row in daily_counts.iterrows()
    ]

    # ── Average tasks per day (NumPy mean) ───────────────────────────────────
    avg_per_day = float(np.mean(daily_counts["count"].values)) if len(daily_counts) else 0.0

    return {
        "total":                 total,
        "completed":             completed,
        "pending":               pending,
        "in_progress":           in_progress,
        "completion_percentage": completion_pct,
        "priority_breakdown":    priority_breakdown,
        "status_breakdown":      status_breakdown,
        "daily_trend":           trend,
        "avg_tasks_per_day":     round(avg_per_day, 2),
    }
