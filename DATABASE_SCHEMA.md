# Tennis Betting System - Database Schema

**Database:** SQLite
**Location (Dev):** `data/tennis_betting.db`
**Location (Installed):** `C:/Users/Public/Documents/Tennis Betting System/data/tennis_betting.db`

---

## Tables Overview

| Table | Purpose | Key Relationships |
|-------|---------|-------------------|
| players | Player profiles and metadata | Core entity |
| matches | Historical match results | References players (winner_id, loser_id) |
| tournaments | Tournament metadata | Referenced by matches |
| rankings_history | Weekly ranking snapshots | References players |
| player_surface_stats | Aggregated surface performance | References players |
| head_to_head | H2H records between players | References players |
| injuries | Injury tracking | References players |
| bets | Bet tracking and results | Standalone |
| upcoming_matches | Matches to analyze | References players |
| player_aliases | Maps alternate player IDs | References players |
| app_settings | Key-value app configuration | Standalone |

---

## Table Definitions

### players
Core player information.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (from data source) |
| name | TEXT | Full name (e.g., "Novak Djokovic") |
| first_name | TEXT | First name |
| last_name | TEXT | Last name |
| country | TEXT | 3-letter country code (e.g., "SRB") |
| hand | TEXT | R=Right, L=Left, U=Unknown, A=Ambidextrous |
| height | INTEGER | Height in cm |
| dob | TEXT | Date of birth (YYYY-MM-DD) |
| current_ranking | INTEGER | Current ATP/WTA ranking |
| peak_ranking | INTEGER | Career-best ranking |
| peak_ranking_date | TEXT | Date of peak ranking |
| last_ta_update | TEXT | Last Tennis Abstract update timestamp |
| created_at | TEXT | Record creation timestamp |
| updated_at | TEXT | Last update timestamp |

---

### matches
Historical match results.

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Primary key (unique match identifier) |
| tournament_id | TEXT | Foreign key to tournaments |
| tournament | TEXT | Tournament name (denormalized for convenience) |
| date | TEXT | Match date (YYYY-MM-DD) |
| round | TEXT | F, SF, QF, R16, R32, R64, R128, RR, BR |
| surface | TEXT | Hard, Clay, Grass, Carpet |
| winner_id | INTEGER | FK to players.id |
| loser_id | INTEGER | FK to players.id |
| score | TEXT | Match score (e.g., "6-4 6-3") |
| sets_won_w | INTEGER | Sets won by winner |
| sets_won_l | INTEGER | Sets won by loser |
| games_won_w | INTEGER | Total games won by winner |
| games_won_l | INTEGER | Total games won by loser |
| minutes | INTEGER | Match duration in minutes |
| winner_rank | INTEGER | Winner's ranking at match time |
| loser_rank | INTEGER | Loser's ranking at match time |
| winner_rank_points | INTEGER | Winner's ranking points |
| loser_rank_points | INTEGER | Loser's ranking points |
| winner_seed | INTEGER | Winner's tournament seed |
| loser_seed | INTEGER | Loser's tournament seed |
| best_of | INTEGER | 3 or 5 (sets) |
| w_ace | INTEGER | Winner's aces |
| w_df | INTEGER | Winner's double faults |
| w_svpt | INTEGER | Winner's serve points |
| w_1stIn | INTEGER | Winner's first serves in |
| w_1stWon | INTEGER | Winner's first serve points won |
| w_2ndWon | INTEGER | Winner's second serve points won |
| w_SvGms | INTEGER | Winner's service games |
| w_bpSaved | INTEGER | Winner's break points saved |
| w_bpFaced | INTEGER | Winner's break points faced |
| l_ace...l_bpFaced | INTEGER | Same stats for loser |
| created_at | TEXT | Record creation timestamp |

---

### tournaments
Tournament metadata.

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Primary key |
| name | TEXT | Tournament name |
| surface | TEXT | Primary surface |
| category | TEXT | Grand Slam, Masters 1000, ATP 500, ATP 250, etc. |
| location | TEXT | City/Country |
| draw_size | INTEGER | Main draw size |
| created_at | TEXT | Record creation timestamp |

---

### rankings_history
Weekly ranking snapshots for tracking ranking changes.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| player_id | INTEGER | FK to players.id |
| ranking_date | TEXT | Ranking date (YYYY-MM-DD) |
| ranking | INTEGER | Ranking position |
| points | INTEGER | Ranking points |

**Unique constraint:** (player_id, ranking_date)

---

### player_surface_stats
Pre-aggregated surface performance stats.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| player_id | INTEGER | FK to players.id |
| surface | TEXT | Hard, Clay, Grass, Carpet |
| matches_played | INTEGER | Total matches on surface |
| wins | INTEGER | Wins on surface |
| losses | INTEGER | Losses on surface |
| win_rate | REAL | Win percentage (0.0-1.0) |
| avg_games_won | REAL | Average games won per match |
| avg_games_lost | REAL | Average games lost per match |
| last_updated | TEXT | Last calculation timestamp |

**Unique constraint:** (player_id, surface)

---

### head_to_head
Head-to-head records between players.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| player1_id | INTEGER | FK to players.id (lower ID) |
| player2_id | INTEGER | FK to players.id (higher ID) |
| p1_wins | INTEGER | Player 1's wins |
| p2_wins | INTEGER | Player 2's wins |
| last_match_date | TEXT | Most recent match date |
| p1_wins_by_surface | TEXT | JSON: {"Hard": 2, "Clay": 1} |
| p2_wins_by_surface | TEXT | JSON: {"Hard": 1, "Clay": 0} |
| last_updated | TEXT | Last calculation timestamp |

**Unique constraint:** (player1_id, player2_id)

---

### injuries
Player injury tracking.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| player_id | INTEGER | FK to players.id |
| injury_type | TEXT | Type of injury |
| body_part | TEXT | Affected body part |
| reported_date | TEXT | When injury was reported |
| status | TEXT | Active, Minor Concern, Questionable, Doubtful, Out, Returning |
| severity | TEXT | Severity level |
| expected_return | TEXT | Expected return date |
| notes | TEXT | Additional notes |
| created_at | TEXT | Record creation timestamp |
| updated_at | TEXT | Last update timestamp |

---

### bets
Bet tracking and results.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| match_date | TEXT | Match date/time (YYYY-MM-DD or YYYY-MM-DD HH:MM) |
| tournament | TEXT | Tournament name |
| match_description | TEXT | "Player A vs Player B" |
| player1 | TEXT | First player name |
| player2 | TEXT | Second player name |
| market | TEXT | Match Winner, Set Betting, Handicap, Total Games, Other |
| selection | TEXT | What was bet on (player name, score, etc.) |
| stake | REAL | Units staked |
| odds | REAL | Decimal odds at placement |
| our_probability | REAL | Model's win probability (0.0-1.0) |
| implied_probability | REAL | Odds-implied probability |
| ev_at_placement | REAL | Expected value at placement |
| result | TEXT | Win, Loss, Void, or NULL (pending) |
| profit_loss | REAL | Actual P/L in units |
| notes | TEXT | User notes |
| in_progress | INTEGER | 1 if match is live, 0 otherwise |
| model | TEXT | Applicable betting models (e.g., "M1,M4,M6") |
| factor_scores | TEXT | JSON object with 10-factor breakdown |
| created_at | TEXT | Bet creation timestamp |
| settled_at | TEXT | Settlement timestamp |

**model column:** Comma-separated list of models this bet qualifies for (M1-M7).

**factor_scores column:** JSON with detailed factor breakdown:
```json
{
  "form": 0.65,
  "surface": 0.58,
  "ranking": 0.72,
  "h2h": 0.50,
  "fatigue": 0.55,
  "injury": 0.50,
  "opponent_quality": 0.60,
  "recency": 0.62,
  "recent_loss": 0.50,
  "momentum": 0.52
}
```

---

### upcoming_matches
Matches captured from Betfair for analysis.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| tournament | TEXT | Tournament name |
| date | TEXT | Match date |
| round | TEXT | Match round |
| surface | TEXT | Playing surface |
| player1_id | INTEGER | FK to players.id (or NULL if unknown) |
| player2_id | INTEGER | FK to players.id (or NULL if unknown) |
| player1_name | TEXT | Player 1 name from Betfair |
| player2_name | TEXT | Player 2 name from Betfair |
| player1_odds | REAL | Current Betfair odds for P1 |
| player2_odds | REAL | Current Betfair odds for P2 |
| pinnacle_odds_p1 | REAL | Pinnacle odds for P1 (from The Odds API) |
| pinnacle_odds_p2 | REAL | Pinnacle odds for P2 (from The Odds API) |
| analyzed | INTEGER | 1 if analyzed, 0 if pending |
| created_at | TEXT | Capture timestamp |

**Pinnacle odds columns:** Populated during Betfair capture when The Odds API is enabled. Used for value comparison - matches where Betfair offers worse odds than Pinnacle by >15% are flagged.

---

### player_aliases
Maps alternate player IDs to canonical IDs.

| Column | Type | Description |
|--------|------|-------------|
| alias_id | INTEGER | Primary key (the alternate ID) |
| canonical_id | INTEGER | FK to players.id (the main ID to use) |
| source | TEXT | Where this alias came from |
| created_at | TEXT | Creation timestamp |

---

### app_settings
Key-value store for application settings.

| Column | Type | Description |
|--------|------|-------------|
| key | TEXT | Primary key (setting name) |
| value | TEXT | Setting value |
| updated_at | TEXT | Last update timestamp |

**Known keys:**
- `discord_webhook_url` - Discord webhook for notifications
- `last_full_refresh` - Last data refresh timestamp
- `last_quick_refresh` - Last quick refresh timestamp

---

## Indexes

| Index | Table | Columns | Purpose |
|-------|-------|---------|---------|
| idx_matches_winner | matches | winner_id | Fast lookup by winner |
| idx_matches_loser | matches | loser_id | Fast lookup by loser |
| idx_matches_date | matches | date | Date range queries |
| idx_matches_surface | matches | surface | Surface filtering |
| idx_matches_tournament | matches | tournament_id | Tournament queries |
| idx_rankings_player | rankings_history | player_id | Player ranking history |
| idx_rankings_date | rankings_history | ranking_date | Ranking by date |
| idx_surface_stats_player | player_surface_stats | player_id | Surface stats lookup |
| idx_h2h_players | head_to_head | player1_id, player2_id | H2H lookup |
| idx_bets_date | bets | match_date | Bet date queries |
| idx_players_name | players | name | Name search |

---

## Entity Relationship Diagram

```
┌─────────────┐       ┌─────────────┐
│   players   │◄──────│   matches   │
│             │       │             │
│ id (PK)     │       │ winner_id   │──┐
│ name        │       │ loser_id    │──┘
│ country     │       │ tournament  │
│ ranking     │       │ date        │
└──────┬──────┘       │ surface     │
       │              │ score       │
       │              └─────────────┘
       │
       ├──────────────┐
       │              │
       ▼              ▼
┌─────────────┐ ┌─────────────┐
│ rankings_   │ │ surface_    │
│ history     │ │ stats       │
│             │ │             │
│ player_id   │ │ player_id   │
│ ranking     │ │ surface     │
│ date        │ │ win_rate    │
└─────────────┘ └─────────────┘
       │
       ├──────────────┬──────────────┐
       │              │              │
       ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ head_to_    │ │  injuries   │ │ upcoming_   │
│ head        │ │             │ │ matches     │
│             │ │ player_id   │ │             │
│ player1_id  │ │ status      │ │ player1_id  │
│ player2_id  │ │ body_part   │ │ player2_id  │
│ p1_wins     │ └─────────────┘ │ odds        │
└─────────────┘                 └─────────────┘


┌─────────────┐                 ┌─────────────┐
│    bets     │                 │ app_settings│
│             │                 │             │
│ match_date  │                 │ key (PK)    │
│ selection   │                 │ value       │
│ stake/odds  │                 └─────────────┘
│ result      │
└─────────────┘
```
