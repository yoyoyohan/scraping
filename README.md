## NJ.com Boys Soccer Scraper and Rankings

This project scrapes boys soccer player stats from `highschoolsports.nj.com` across all conferences and builds a statewide player leaderboard based purely on the site's stats (points, goals, assists).

### Setup

- **Python**: 3.10+ recommended
- Install dependencies:

```bash
pip install -r requirements.txt
```

### Run the scraper

From the project root:

```bash
python -m scraper.stats
```

This will:

- Walk all configured conferences and team pages
- Discover player pages
- Scrape each player's game log table
- Append rows to `data/raw_stats.csv` with columns:
  - `player`, `player_url`, `date`, `opponent`, `result`, `goals`, `assists`, `points`

The scraper de-duplicates players in memory and periodically flushes to disk so you can safely interrupt and re-run; new rows are simply appended.

### Build rankings

After `data/raw_stats.csv` exists, run:

```bash
python -m analysis.ranking
```

This will:

- Aggregate season totals per player
- Rank by:
  - **primary**: `points`
  - **secondary**: `goals`
  - **tertiary**: `assists`
- Write `data/rankings.csv`
- Print the top 50 players to stdout

### Project layout

```text
scraper/
  teams.py    # conference → team URLs
  players.py  # team URL → player URLs
  stats.py    # player URL → game logs → raw_stats.csv
analysis/
  ranking.py  # raw_stats.csv → rankings.csv
data/
  raw_stats.csv
  rankings.csv
```

