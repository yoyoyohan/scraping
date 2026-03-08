from pathlib import Path

import pandas as pd

DATA_DIR = Path("data")
RAW_STATS_PATH = DATA_DIR / "raw_stats.csv"
RANKINGS_PATH = DATA_DIR / "rankings.csv"


def build_leaderboard(raw_stats_path: Path = RAW_STATS_PATH) -> pd.DataFrame:
    df = pd.read_csv(raw_stats_path)

    # Basic aggregation: season totals per player
    player_totals = (
        df.groupby("player")
        .agg(
            {
                "goals": "sum",
                "assists": "sum",
                "points": "sum",
                "date": "count",
            }
        )
        .rename(columns={"date": "games"})
        .reset_index()
    )

    # Ranking by points, then goals, then assists
    player_totals = player_totals.sort_values(
        by=["points", "goals", "assists"],
        ascending=False,
    )
    player_totals.insert(0, "rank", range(1, len(player_totals) + 1))

    leaderboard = player_totals[["rank", "player", "goals", "assists", "points", "games"]]
    return leaderboard


def main() -> None:
    if not RAW_STATS_PATH.exists():
        raise SystemExit(f"{RAW_STATS_PATH} not found. Run the scraper first.")

    leaderboard = build_leaderboard()
    DATA_DIR.mkdir(exist_ok=True)
    leaderboard.to_csv(RANKINGS_PATH, index=False)

    # Show top 50 in console
    print(leaderboard.head(50).to_string(index=False))


if __name__ == "__main__":
    main()

