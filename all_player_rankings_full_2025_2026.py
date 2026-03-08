from __future__ import annotations

from pathlib import Path

import pandas as pd

from scraper.rosters_2025_2026 import fetch_all_rosters

SEASON = "2025-2026"

DATA_DIR = Path("data")
TEAM_STRENGTH_PATH = DATA_DIR / f"all_team_strength_{SEASON.replace('-', '_')}.csv"
STATS_STRENGTH_PATH = DATA_DIR / f"all_player_rankings_strength_{SEASON.replace('-', '_')}.csv"

OUTPUT_PATH = DATA_DIR / f"all_player_rankings_full_{SEASON.replace('-', '_')}.csv"


def build_full_rankings() -> None:
    if not TEAM_STRENGTH_PATH.exists():
        raise SystemExit(f"{TEAM_STRENGTH_PATH} not found. Run all_team_strength_2025_2026.py first.")
    if not STATS_STRENGTH_PATH.exists():
        raise SystemExit(f"{STATS_STRENGTH_PATH} not found. Run all_player_rankings_2025_2026.py first.")

    teams = pd.read_csv(TEAM_STRENGTH_PATH)
    team_rating = dict(zip(teams["team"], teams["rating"]))
    avg_rating = float(teams["rating"].mean())

    stats = pd.read_csv(STATS_STRENGTH_PATH)
    # Drop previous rank; we'll recompute.
    stats = stats.drop(columns=["rank"])

    # Fetch full rosters (all conferences).
    roster_rows = fetch_all_rosters()
    roster = pd.DataFrame(roster_rows)

    # Merge rosters with stats so that everyone on a roster is present.
    full = roster.merge(stats, on=["player", "team"], how="left")

    # Players with stats but not on roster (rare) – append them too.
    stats_only = stats.merge(roster[["player", "team"]], on=["player", "team"], how="left", indicator=True)
    stats_only = stats_only[stats_only["_merge"] == "left_only"].drop(columns=["_merge"])
    # Add empty roster metadata.
    if not stats_only.empty:
        stats_only.insert(0, "player_class", "")
        stats_only.insert(0, "positions", "")
        stats_only.insert(0, "number", "")
        # Align column order with `full`
        full_cols = list(full.columns)
        stats_only = stats_only[full_cols]
        full = pd.concat([full, stats_only], ignore_index=True)

    # Fill missing stat values and positions for roster-only players.
    for col in ["goals", "assists", "points", "strength_points"]:
        if col in full.columns:
            full[col] = full[col].fillna(0)
        else:
            full[col] = 0

    if "positions" in full.columns:
        full["positions"] = full["positions"].fillna("")

    # Ensure strength_points for roster-only players reflects team strength.
    def assign_strength(row):
        if row["points"] > 0 or row["strength_points"] > 0:
            return row["strength_points"]
        return team_rating.get(row["team"], avg_rating)

    full["strength_points"] = full.apply(assign_strength, axis=1)

    # Sort with same primary criteria, now including 0-point players.
    full = full.sort_values(
        by=["points", "goals", "assists", "strength_points", "player"],
        ascending=[False, False, False, False, True],
    ).reset_index(drop=True)

    full.insert(0, "rank", full.index + 1)

    # We no longer want the is_goalie flag in the exported CSV.
    if "is_goalie" in full.columns:
        full = full.drop(columns=["is_goalie"])

    # Reorder columns for readability.
    desired_order = [
        "rank",
        "player",
        "team",
        "number",
        "positions",
        "player_class",
        "goals",
        "assists",
        "points",
        "strength_points",
    ]
    cols = [c for c in desired_order if c in full.columns] + [c for c in full.columns if c not in desired_order]
    full = full[cols]

    full.to_csv(OUTPUT_PATH, index=False)
    print(full.head(50).to_string(index=False))
    print(f"\nSaved full (stats + roster + goalies) player rankings to {OUTPUT_PATH}")


if __name__ == "__main__":
    build_full_rankings()

