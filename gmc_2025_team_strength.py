from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple

import math
import pandas as pd
import requests
from bs4 import BeautifulSoup

from scraper.teams import HEADERS, get_all_team_urls

SEASON = "2025-2026"
CONFERENCE = "GMC"

DATA_DIR = Path("data")
OUTPUT_PATH = DATA_DIR / f"gmc_team_strength_{SEASON.replace('-', '_')}.csv"


def season_url_for_team(team_url: str) -> str:
    """
    Base season URL (schedule / scoreboard) for a team and season.
    Example:
    https://.../school/monroe-twp-monroe/boyssoccer/season/2024-2025
    -> https://.../school/monroe-twp-monroe/boyssoccer/season/2025-2026
    """
    root = team_url.split("/season/")[0]
    return f"{root}/season/{SEASON}"


def fetch_html(url: str) -> BeautifulSoup | None:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        return None
    return BeautifulSoup(resp.text, "html.parser")


def parse_result_cell(result_text: str) -> Tuple[str, int, int]:
    """
    Parse a result string like 'W5-1' or 'L2-3' or 'T1-1'.
    Returns (outcome, goals_for, goals_against).
    """
    result_text = result_text.strip()
    if not result_text:
        return "", 0, 0

    outcome = result_text[0]  # W/L/T
    score_part = result_text[1:]
    if "-" not in score_part:
        return outcome, 0, 0

    try:
        a_str, b_str = score_part.split("-", 1)
        goals1 = int(a_str)
        goals2 = int(b_str)
    except ValueError:
        return outcome, 0, 0

    if outcome == "W":
        goals_for, goals_against = goals1, goals2
    elif outcome == "L":
        # For a loss, the first score is opponent's
        goals_for, goals_against = goals2, goals1
    else:  # Tie or other
        goals_for, goals_against = goals1, goals2

    return outcome, goals_for, goals_against


def clean_opponent_name(raw: str) -> str:
    """
    Strip '@' / 'vs' prefixes and collapse whitespace.
    """
    txt = raw.strip()
    for prefix in ("@", "vs", "vs.", "at"):
        if txt.startswith(prefix):
            txt = txt[len(prefix) :].strip()
            break
    return " ".join(txt.split())


@dataclass
class Game:
    team: str
    opponent: str
    outcome: str  # 'W', 'L', 'T', or ''
    goals_for: int
    goals_against: int

    @property
    def margin(self) -> int:
        return self.goals_for - self.goals_against


def fetch_team_schedule(team_url: str) -> Tuple[str, List[Game]]:
    """
    Fetch the 2025-2026 schedule/scoreboard for a team and return the
    team name plus a list of Game objects.
    """
    url = season_url_for_team(team_url)
    soup = fetch_html(url)
    if soup is None:
        return "", []

    h1 = soup.find("h1")
    team_name = h1.get_text(strip=True) if h1 else ""

    table = soup.find("table")
    if not table:
        return team_name, []

    games: List[Game] = []
    rows = table.find_all("tr")[1:]  # skip header
    for tr in rows:
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue

        date_txt = tds[0].get_text(strip=True)
        if not date_txt:
            continue

        opp_txt = tds[1].get_text(strip=True)
        opp_name = clean_opponent_name(opp_txt)

        result_txt = tds[2].get_text(strip=True)
        outcome, gf, ga = parse_result_cell(result_txt)
        if not outcome:
            continue

        games.append(Game(team=team_name, opponent=opp_name, outcome=outcome, goals_for=gf, goals_against=ga))

    return team_name, games


@dataclass
class TeamSummary:
    team: str
    games: int
    wins: int
    losses: int
    ties: int
    goals_for: int
    goals_against: int
    goal_diff: int
    win_pct: float
    opp_win_pct: float
    goal_diff_per_game: float
    max_win_margin: int
    rating: float


def compute_team_summaries(team_games: Dict[str, List[Game]]) -> Dict[str, TeamSummary]:
    """
    First pass: compute records and basic stats (without opp_win_pct/rating).
    """
    summaries: Dict[str, TeamSummary] = {}

    for team, games in team_games.items():
        wins = sum(1 for g in games if g.outcome == "W")
        losses = sum(1 for g in games if g.outcome == "L")
        ties = sum(1 for g in games if g.outcome not in {"W", "L"} and g.outcome)
        goals_for = sum(g.goals_for for g in games)
        goals_against = sum(g.goals_against for g in games)
        games_played = wins + losses + ties
        goal_diff = goals_for - goals_against
        win_pct = (wins + 0.5 * ties) / games_played if games_played else 0.0
        max_win_margin = max((g.margin for g in games if g.outcome == "W"), default=0)
        goal_diff_per_game = goal_diff / games_played if games_played else 0.0

        summaries[team] = TeamSummary(
            team=team,
            games=games_played,
            wins=wins,
            losses=losses,
            ties=ties,
            goals_for=goals_for,
            goals_against=goals_against,
            goal_diff=goal_diff,
            win_pct=win_pct,
            opp_win_pct=0.0,  # placeholder
            goal_diff_per_game=goal_diff_per_game,
            max_win_margin=max_win_margin,
            rating=0.0,  # placeholder
        )

    return summaries


def compute_opponent_win_pct(team_games: Dict[str, List[Game]], summaries: Dict[str, TeamSummary]) -> None:
    """
    Second pass: for each team, compute average opponent win% using
    GMC opponents only. If a team has no GMC opponents, fallback to 0.5.
    """
    for team, games in team_games.items():
        opp_pcts: List[float] = []
        for g in games:
            opp_summary = summaries.get(g.opponent)
            if opp_summary and opp_summary.games > 0:
                opp_pcts.append(opp_summary.win_pct)
        if opp_pcts:
            summaries[team].opp_win_pct = sum(opp_pcts) / len(opp_pcts)
        else:
            summaries[team].opp_win_pct = 0.5


def compute_ratings(summaries: Dict[str, TeamSummary]) -> None:
    """
    Combine stats into a single rating score.
    Heavier weight on own record, then strength of schedule, then margins.
    """
    for s in summaries.values():
        # Scale goal metrics down to keep comparable.
        rating = (
            3.0 * s.win_pct
            + 1.5 * s.opp_win_pct
            + 0.04 * s.goal_diff_per_game
            + 0.01 * s.max_win_margin
        )
        s.rating = rating


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)

    # Discover all GMC teams (URLs) and pull schedules.
    team_urls = get_all_team_urls([CONFERENCE])

    team_games: Dict[str, List[Game]] = {}
    for team_url in team_urls:
        team_name, games = fetch_team_schedule(team_url)
        if not team_name:
            continue
        team_games[team_name] = games

    if not team_games:
        print(f"No schedules found for {CONFERENCE} {SEASON}.")
        return

    summaries = compute_team_summaries(team_games)
    compute_opponent_win_pct(team_games, summaries)
    compute_ratings(summaries)

    rows = [asdict(s) for s in summaries.values()]
    df = pd.DataFrame(rows)
    df = df.sort_values(by="rating", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", df.index + 1)

    # Round some columns for readability
    df["win_pct"] = df["win_pct"].round(3)
    df["opp_win_pct"] = df["opp_win_pct"].round(3)
    df["goal_diff_per_game"] = df["goal_diff_per_game"].round(3)
    df["rating"] = df["rating"].round(3)

    df.to_csv(OUTPUT_PATH, index=False)
    print(df.to_string(index=False))
    print(f"\nSaved GMC {SEASON} team strength rankings to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

