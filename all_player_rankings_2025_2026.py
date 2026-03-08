from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from analysis.all_team_strength_2025_2026 import clean_opponent_name

SEASON = "2025-2026"

DATA_DIR = Path("data")
GAMES_PATH = DATA_DIR / f"all_player_games_{SEASON.replace('-', '_')}.csv"
TEAM_STRENGTH_PATH = DATA_DIR / f"all_team_strength_{SEASON.replace('-', '_')}.csv"

BASIC_OUTPUT = DATA_DIR / f"all_player_rankings_basic_{SEASON.replace('-', '_')}.csv"
STRENGTH_OUTPUT = DATA_DIR / f"all_player_rankings_strength_{SEASON.replace('-', '_')}.csv"


def build_player_rankings() -> None:
    if not GAMES_PATH.exists():
        raise SystemExit(f"{GAMES_PATH} not found. Run the all-player games scraper first.")
    if not TEAM_STRENGTH_PATH.exists():
        raise SystemExit(f"{TEAM_STRENGTH_PATH} not found. Run the statewide team strength script first.")

    games = pd.read_csv(GAMES_PATH)
    teams = pd.read_csv(TEAM_STRENGTH_PATH)

    # Basic per-player totals
    agg_basic = (
        games.groupby(["player", "team"], as_index=False)[["goals", "assists", "points"]]
        .sum()
        .sort_values(by=["points", "goals", "assists", "player"], ascending=[False, False, False, True])
        .reset_index(drop=True)
    )
    agg_basic.insert(0, "rank", agg_basic.index + 1)
    agg_basic.to_csv(BASIC_OUTPUT, index=False)

    # Strength-adjusted ranking
    rating_map = dict(zip(teams["team"], teams["rating"]))
    avg_rating = float(teams["rating"].mean())

    games = games.copy()
    games["opp_clean"] = games["opponent"].astype(str).map(clean_opponent_name)
    games["opp_rating"] = games["opp_clean"].map(rating_map).fillna(avg_rating)
    games["weighted_points"] = games["points"] * games["opp_rating"]

    agg_strength = (
        games.groupby(["player", "team"], as_index=False)[["goals", "assists", "points", "weighted_points"]]
        .sum()
        .rename(columns={"weighted_points": "strength_points"})
    )

    agg_strength = agg_strength.sort_values(
        by=["points", "goals", "assists", "strength_points", "player"],
        ascending=[False, False, False, False, True],
    ).reset_index(drop=True)

    agg_strength.insert(0, "rank", agg_strength.index + 1)

    agg_strength.to_csv(STRENGTH_OUTPUT, index=False)

    print("Top 50 players by strength-adjusted ranking:")
    print(agg_strength.head(50).to_string(index=False))
    print(f"\nSaved basic rankings to {BASIC_OUTPUT}")
    print(f"Saved strength-adjusted rankings to {STRENGTH_OUTPUT}")


if __name__ == "__main__":
    build_player_rankings()

