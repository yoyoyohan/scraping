"""
One-time script: build data/team_conference.csv (team, conference) by fetching
each conference's team list and resolving team names from schedule pages.
Run with network access. Used by the website AI for "what conference is X in".
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from analysis.all_team_strength_2025_2026 import fetch_team_schedule
from scraper.teams import CONFERENCES, get_teams_for_conference

DATA_DIR = Path("data")
OUTPUT_PATH = DATA_DIR / "team_conference.csv"


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    rows = []
    seen_urls = set()
    for conf in CONFERENCES:
        urls = get_teams_for_conference(conf)
        for team_url in urls:
            if team_url in seen_urls:
                continue
            seen_urls.add(team_url)
            team_name, _ = fetch_team_schedule(team_url)
            if team_name:
                rows.append({"team": team_name, "conference": conf})
    df = pd.DataFrame(rows)
    df.drop_duplicates(subset=["team"], keep="first", inplace=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(df)} teams to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
