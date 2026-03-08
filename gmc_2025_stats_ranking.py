from pathlib import Path
from typing import Dict, List

import pandas as pd
import requests
from bs4 import BeautifulSoup

from scraper.teams import HEADERS, get_all_team_urls

SEASON = "2025-2026"
CONFERENCE = "GMC"

DATA_DIR = Path("data")
OUTPUT_PATH = DATA_DIR / f"rankings_{CONFERENCE.lower()}_{SEASON.replace('-', '_')}.csv"


def team_stats_url(team_url: str) -> str:
    """
    Convert a team season URL into that season's stats page URL.

    Example:
    https://.../school/monroe-twp-monroe/boyssoccer/season/2024-2025
    -> https://.../school/monroe-twp-monroe/boyssoccer/season/2025-2026/stats
    """
    root = team_url.split("/season/")[0]
    return f"{root}/season/{SEASON}/stats"


def parse_int(value: str) -> int:
    value = value.strip()
    if value in {"", "—", "-", "–"}:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def fetch_team_scoring(team_url: str) -> List[Dict]:
    """
    Fetch the 2025-2026 team scoring table for a given team and return
    one row per player with season totals for goals, assists, and points.
    """
    url = team_stats_url(team_url)
    resp = requests.get(url, headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    h1 = soup.find("h1")
    team_name = h1.get_text(strip=True) if h1 else ""

    rows: List[Dict] = []
    for tr in table.find_all("tr")[1:]:  # skip header
        tds = tr.find_all("td")
        if not tds:
            continue

        first_text = tds[0].get_text(strip=True)
        if first_text.startswith("Total"):
            # Skip the totals row
            continue

        player_link = tds[0].find("a")
        player_name = player_link.get_text(strip=True) if player_link else first_text
        player_url = player_link["href"] if player_link and player_link.has_attr("href") else ""

        goals = parse_int(tds[1].get_text())
        assists = parse_int(tds[2].get_text())
        points = parse_int(tds[3].get_text())

        rows.append(
            {
                "conference": CONFERENCE,
                "team": team_name,
                "team_url": team_url,
                "player": player_name,
                "player_url": player_url,
                "goals": goals,
                "assists": assists,
                "points": points,
            }
        )

    return rows


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)

    team_urls = get_all_team_urls([CONFERENCE])

    all_rows: List[Dict] = []
    for team_url in team_urls:
        all_rows.extend(fetch_team_scoring(team_url))

    if not all_rows:
        print(f"No player scoring data found for {CONFERENCE} {SEASON}.")
        return

    df = pd.DataFrame(all_rows)

    # Aggregate by player+team in case of duplicates.
    df_agg = (
        df.groupby(["player", "team"], as_index=False)[["goals", "assists", "points"]]
        .sum()
        .sort_values(by=["points", "goals", "assists"], ascending=False)
    )

    df_agg.insert(0, "rank", range(1, len(df_agg) + 1))

    df_agg.to_csv(OUTPUT_PATH, index=False)

    print(df_agg.head(50).to_string(index=False))
    print(f"\nSaved full GMC {SEASON} rankings to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

