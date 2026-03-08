from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
from flask import Flask, jsonify, render_template, request

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

SEASON = "2025-2026"

PLAYER_FULL_PATH = DATA_DIR / f"all_player_rankings_full_{SEASON.replace('-', '_')}.csv"
TEAM_STRENGTH_PATH = DATA_DIR / f"all_team_strength_{SEASON.replace('-', '_')}.csv"
TEAM_CONFERENCE_PATH = DATA_DIR / "team_conference.csv"

# Full conference names for qualitative answers
CONFERENCE_NAMES: Dict[str, str] = {
    "GMC": "Greater Middlesex Conference",
    "Big North": "Big North Conference",
    "BCSL": "Burlington County Scholastic League",
    "Cape-Atlantic": "Cape-Atlantic League",
    "CVC": "Colonial Valley Conference",
    "HCIAL": "Hudson County Interscholastic Athletic League",
    "NJAC": "North Jersey Athletic Conference",
    "NJIC": "North Jersey Interscholastic Conference",
    "Olympic": "Olympic Conference",
    "SEC": "Super Essex Conference",
    "Shore": "Shore Conference",
    "Skyland": "Skyland Conference",
    "Tri-County": "Tri-County Conference",
}

app = Flask(__name__)


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, Dict[str, str]]:
    players = pd.read_csv(PLAYER_FULL_PATH)
    teams = pd.read_csv(TEAM_STRENGTH_PATH)
    team_to_conference: Dict[str, str] = {}
    if TEAM_CONFERENCE_PATH.exists():
        conf_df = pd.read_csv(TEAM_CONFERENCE_PATH)
        for _, row in conf_df.iterrows():
            team_to_conference[str(row["team"]).strip()] = str(row["conference"]).strip()
    else:
        # Fallback: GMC teams from gmc_team_strength so "what conference is Monroe in" works
        gmc_path = DATA_DIR / "gmc_team_strength_2025_2026.csv"
        if gmc_path.exists():
            gmc_df = pd.read_csv(gmc_path)
            for t in gmc_df["team"].dropna().unique():
                team_to_conference[str(t).strip()] = "GMC"
    return players, teams, team_to_conference


players_df, teams_df, team_to_conference = load_data()


@app.route("/")
def index() -> str:
    top_players = players_df.to_dict(orient="records")
    top_teams = teams_df.to_dict(orient="records")
    return render_template(
        "index.html",
        season=SEASON,
        top_players=top_players,
        top_teams=top_teams,
    )


@app.get("/api/players")
def api_players() -> Any:
    query = request.args.get("q", "").strip()
    team = request.args.get("team", "").strip()

    df = players_df
    if query:
        df = df[df["player"].str.contains(query, case=False, na=False)]
    if team:
        df = df[df["team"].str.contains(team, case=False, na=False)]

    return jsonify(df.to_dict(orient="records"))


@app.get("/api/teams")
def api_teams() -> Any:
    query = request.args.get("q", "").strip()

    df = teams_df
    if query:
        df = df[df["team"].str.contains(query, case=False, na=False)]

    return jsonify(df.to_dict(orient="records"))


def _team_from_question(question: str) -> Optional[str]:
    """Find a team name from the question by matching known team names (longest match wins)."""
    q_low = question.lower()
    best: Optional[str] = None
    best_len = 0
    for team in teams_df["team"].dropna().unique():
        t = str(team).strip()
        if not t:
            continue
        if t.lower() in q_low and len(t) > best_len:
            best = t
            best_len = len(t)
    return best


def _top_n_from_question(question: str) -> int:
    """Extract 'top N' or 'best N' from the question; default 10."""
    q_low = question.lower()
    # e.g. "top 5", "best 10", "first 3", "top 5 players"
    for pattern in (r"top\s*(\d+)", r"best\s*(\d+)", r"first\s*(\d+)", r"(\d+)\s*players"):
        m = re.search(pattern, q_low, re.IGNORECASE)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 100:
                return n
    # any digit in the question when context suggests a count
    if "top" in q_low or "best" in q_low or "first" in q_low:
        for token in q_low.split():
            if token.isdigit():
                n = int(token)
                if 1 <= n <= 100:
                    return n
                break
    return 10


def _answer_question(question: str) -> str:
    q = question.strip()
    if not q:
        return "Ask about a player (name), a team, conference, goalie, or things like 'top 10 players', 'top 5 players on Monroe', 'what conference is Monroe in', 'who is the goalie on Monroe', or 'who is the best player on Monroe'."

    q_low = q.lower()
    team_mentioned = _team_from_question(q)

    # ---- "What conference is [team] in?" / "Which conference is X in?"
    if ("conference" in q_low) and team_mentioned:
        conf = team_to_conference.get(team_mentioned)
        if conf:
            full = CONFERENCE_NAMES.get(conf, conf)
            return f"{team_mentioned} is in the {full}."
        return f"I don't have conference data for {team_mentioned}. Run 'python -m analysis.build_team_conference' (with network) to generate it, then restart the app."

    # ---- "Who is the goalie on [team]?" / "Goalie for X?"
    if ("goalie" in q_low or "goalkeeper" in q_low) and team_mentioned:
        pos = players_df["positions"].astype(str)
        goalies = players_df[
            (players_df["team"] == team_mentioned) & (pos.str.contains("G", na=False))
        ]
        if goalies.empty:
            return f"I don't see a player listed as goalie (G) for {team_mentioned} in the roster data."
        if len(goalies) == 1:
            row = goalies.iloc[0]
            cls = row.get("player_class", "")
            return f"The goalie for {team_mentioned} is {row['player']}" + (f" ({cls})." if cls else ".")
        lines = [f"The goalies for {team_mentioned} are:"]
        for _, row in goalies.iterrows():
            cls = row.get("player_class", "")
            lines.append(f"  • {row['player']}" + (f" ({cls})" if cls else ""))
        return "\n".join(lines)

    # ---- "Who is the best player on [team]?" / "Exact best player on X?" (single, qualitative)
    wants_single_best = (
        team_mentioned
        and ("best player" in q_low or "exact best" in q_low or "top player" in q_low or "who is the best" in q_low)
        and not re.search(r"\d+\s*players", q_low)
    )
    if wants_single_best:
        best = (
            players_df[players_df["team"] == team_mentioned]
            .sort_values(by=["points", "goals", "assists"], ascending=[False, False, False])
            .head(1)
        )
        if best.empty:
            return f"I don't have any players for {team_mentioned} in the dataset."
        row = best.iloc[0]
        return (
            f"The best player on {team_mentioned} is {row['player']}, with {int(row['points'])} points "
            f"({int(row['goals'])} goals, {int(row['assists'])} assists), ranked #{int(row['rank'])} statewide."
        )

    # ---- "Top N players on/from [team]"
    wants_top_players = any(x in q_low for x in ("top", "best", "first", "show", "list", "name")) and (
        "player" in q_low or "players" in q_low or "roster" in q_low
    )

    if wants_top_players and team_mentioned:
        n = _top_n_from_question(q)
        team_players = (
            players_df[players_df["team"] == team_mentioned]
            .sort_values(by=["points", "goals", "assists"], ascending=[False, False, False])
            .head(n)
        )
        if team_players.empty:
            return f"No players found for team '{team_mentioned}' in the dataset."
        lines = [f"Top {len(team_players)} players on {team_mentioned} (rank statewide, name, points):"]
        for _, row in team_players.iterrows():
            lines.append(
                f"  {int(row['rank'])}. {row['player']} — {int(row['points'])} pts ({int(row['goals'])}G, {int(row['assists'])}A)"
            )
        return "\n".join(lines)

    # ---- Top N players (statewide)
    if wants_top_players and not team_mentioned:
        n = _top_n_from_question(q)
        sub = players_df.head(min(n, len(players_df)))
        lines = [f"Top {len(sub)} players statewide (rank, name, team, points):"]
        for _, row in sub.iterrows():
            lines.append(
                f"{int(row['rank'])}. {row['player']} ({row['team']}) - {int(row['points'])} points"
            )
        return "\n".join(lines)

    # ---- Team strength query
    if "strongest team" in q_low or ("team" in q_low and "strong" in q_low):
        n = _top_n_from_question(q)
        sub = teams_df.head(min(n, len(teams_df)))
        lines = [f"Top {len(sub)} teams by rating:"]
        for _, row in sub.iterrows():
            lines.append(
                f"{int(row['rank'])}. {row['team']} - rating {row['rating']:.3f}, record {int(row['wins'])}-{int(row['losses'])}-{int(row['ties'])}"
            )
        return "\n".join(lines)

    # ---- Specific player query (name in question)
    matches = players_df[players_df["player"].str.contains(q, case=False, na=False)]
    if matches.empty:
        tokens = [t for t in q.split() if len(t) > 2]
        for i in range(len(tokens) - 1):
            frag = " ".join(tokens[i : i + 2])
            m2 = players_df[players_df["player"].str.contains(frag, case=False, na=False)]
            if not m2.empty:
                matches = m2
                break

    if not matches.empty:
        row = matches.iloc[0]
        return (
            f"{row['player']} ({row['team']}) is ranked #{int(row['rank'])} statewide "
            f"with {int(row['goals'])} goals, {int(row['assists'])} assists, "
            f"{int(row['points'])} points, and strength score {row['strength_points']:.2f}."
        )

    # ---- Specific team query (team name in question, or team found from question)
    if team_mentioned:
        row = teams_df[teams_df["team"] == team_mentioned].iloc[0]
        return (
            f"{row['team']} is ranked #{int(row['rank'])} among all teams with "
            f"record {int(row['wins'])}-{int(row['losses'])}-{int(row['ties'])}, "
            f"goal differential {int(row['goal_diff'])}, and rating {row['rating']:.3f}."
        )

    team_matches = teams_df[teams_df["team"].str.contains(q, case=False, na=False)]
    if not team_matches.empty:
        row = team_matches.iloc[0]
        return (
            f"{row['team']} is ranked #{int(row['rank'])} among all teams with "
            f"record {int(row['wins'])}-{int(row['losses'])}-{int(row['ties'])}, "
            f"goal differential {int(row['goal_diff'])}, and rating {row['rating']:.3f}."
        )

    return (
        "I couldn't find a matching player or team. Try: a player name, a team name (e.g. Monroe, Edison), "
        "'top 5 players on [team]', or 'top 10 players'."
    )


@app.post("/api/chat")
def api_chat() -> Any:
    data: Dict[str, Any] = request.get_json(force=True) or {}
    question = str(data.get("question", "")).strip()
    answer = _answer_question(question)
    return jsonify({"answer": answer})


if __name__ == "__main__":
    app.run(debug=True)

