# Tennis Betting System - Data Dictionary

Definitions of terms, fields, and concepts used throughout the system.

---

## Tennis Terms

| Term | Definition |
|------|------------|
| **ATP** | Association of Tennis Professionals - men's professional tour |
| **WTA** | Women's Tennis Association - women's professional tour |
| **Grand Slam** | The four major tournaments: Australian Open, Roland Garros, Wimbledon, US Open |
| **Masters 1000** | Top tier of ATP tournaments below Grand Slams |
| **Best of 3** | Match format: first to win 2 sets |
| **Best of 5** | Match format: first to win 3 sets (Grand Slam men's singles) |
| **H2H** | Head-to-head record between two players |
| **Surface** | Court type: Hard, Clay, Grass, or Carpet |
| **Seed** | Tournament seeding based on ranking (1 = highest) |

---

## Betting Terms

| Term | Definition |
|------|------------|
| **Decimal Odds** | European odds format (e.g., 2.50 means £1 bet returns £2.50 total) |
| **Implied Probability** | Probability implied by odds: `1 / odds` |
| **EV (Expected Value)** | `(probability × profit) - (1 - probability) × stake`. Positive = profitable long-term |
| **Stake** | Amount wagered |
| **Units** | Standardized stake size (1 unit = fixed % of bankroll) |
| **P/L** | Profit/Loss |
| **ROI** | Return on Investment: `(profit / total_staked) × 100%` |
| **Kelly Criterion** | Optimal stake sizing formula: `(bp - q) / b` where b=odds-1, p=probability, q=1-p |
| **Commission** | Fee taken by exchange (Betfair) on winnings |
| **Value Bet** | Bet where your probability > implied probability (positive EV) |
| **Edge** | Your advantage: `your_probability - implied_probability` |
| **Pinnacle** | Sharp bookmaker known for accurate odds - used as benchmark |
| **Sharp Bookmaker** | Bookmaker with low margins and well-priced odds (e.g., Pinnacle) |
| **Liquidity** | Amount of money available to back at a given price |

---

## Betting Models (M1-M7)

| Model | Name | Criteria |
|-------|------|----------|
| **M1** | All Bets | Every value bet identified |
| **M2** | Tiered | Extreme odds + filtered middle range |
| **M3** | Moderate Edge | 5-15% edge range |
| **M4** | Favorites | Model probability >= 60% |
| **M5** | Underdogs | Model probability < 45% |
| **M6** | Large Edge | Edge >= 10% |
| **M7** | Grind | 3-8% edge + odds < 2.50 |

Each bet is tagged with applicable models (e.g., "M1,M4,M6").

---

## Analysis Factors

| Factor | What It Measures |
|--------|------------------|
| **Form** | Recent match results, weighted by recency |
| **Surface** | Player's win rate on specific court type |
| **Ranking** | Current ATP/WTA ranking position |
| **H2H** | Historical record between the two players |
| **Fatigue** | Rest days, recent workload, match difficulty |
| **Injury** | Current injury status and severity |
| **Opponent Quality** | Strength of recent opponents faced |
| **Recency** | How recent the form data is |
| **Recent Loss** | Penalty for coming off a recent loss |
| **Momentum** | Winning streak on current surface |

---

## Database Fields

### Player Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Unique player identifier |
| `name` | Text | Full name (e.g., "Novak Djokovic") |
| `country` | Text | 3-letter ISO code (e.g., "SRB") |
| `hand` | Text | R=Right, L=Left, U=Unknown, A=Ambidextrous |
| `height` | Integer | Height in centimeters |
| `dob` | Text | Date of birth (YYYY-MM-DD) |
| `current_ranking` | Integer | Current ranking position |
| `peak_ranking` | Integer | Career-best ranking |

### Match Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | Text | Unique match identifier |
| `tournament` | Text | Tournament name |
| `date` | Text | Match date (YYYY-MM-DD) |
| `round` | Text | F, SF, QF, R16, R32, R64, R128, RR, BR |
| `surface` | Text | Hard, Clay, Grass, Carpet |
| `winner_id` | Integer | ID of winning player |
| `loser_id` | Integer | ID of losing player |
| `score` | Text | Match score (e.g., "6-4 7-5") |
| `sets_won_w` | Integer | Sets won by winner |
| `sets_won_l` | Integer | Sets won by loser |
| `minutes` | Integer | Match duration |
| `best_of` | Integer | 3 or 5 (sets) |

### Bet Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Unique bet identifier |
| `match_date` | Text | Date/time of match |
| `tournament` | Text | Tournament name |
| `match_description` | Text | "Player A vs Player B" |
| `market` | Text | Bet type: Match Winner, Set Betting, etc. |
| `selection` | Text | What was bet on |
| `stake` | Real | Units staked |
| `odds` | Real | Decimal odds at placement |
| `our_probability` | Real | Model's win probability (0.0-1.0) |
| `implied_probability` | Real | Odds-implied probability |
| `ev_at_placement` | Real | Expected value when bet was placed |
| `result` | Text | Win, Loss, Void, or NULL (pending) |
| `profit_loss` | Real | Actual P/L in units |
| `in_progress` | Integer | 1 if match is live |
| `model` | Text | Applicable betting models (e.g., "M1,M4,M6") |
| `factor_scores` | Text | JSON with 10-factor breakdown |

---

## Calculated Values

### Win Probability

Calculated from weighted sum of all analysis factors:

```
probability = Σ (factor_score × factor_weight)
```

Each factor produces a score from 0.0 to 1.0, weights sum to 1.0.

### Expected Value (EV)

```
EV = (our_prob × (odds - 1)) - (1 - our_prob)
```

- Positive EV = profitable long-term
- Higher = better value

### Kelly Stake

Full Kelly:
```
kelly_pct = (our_prob × odds - 1) / (odds - 1)
```

Fractional Kelly (safer):
```
stake = kelly_pct × kelly_fraction × bankroll
```

### Profit/Loss

```
Win:  P/L = stake × (odds - 1) × (1 - commission)
Loss: P/L = -stake
Void: P/L = 0
```

---

## Match Round Codes

| Code | Round |
|------|-------|
| F | Final |
| SF | Semi-Final |
| QF | Quarter-Final |
| R16 | Round of 16 |
| R32 | Round of 32 |
| R64 | Round of 64 |
| R128 | Round of 128 |
| RR | Round Robin |
| BR | Bronze Medal Match |
| ER | Early Round |

---

## Tournament Categories

| Category | Points | Example |
|----------|--------|---------|
| Grand Slam | 2000 | Australian Open |
| Masters 1000 | 1000 | Indian Wells |
| ATP 500 | 500 | Dubai |
| ATP 250 | 250 | Adelaide |
| ATP Finals | 1500 | Year-end Finals |
| Challenger | 50-175 | Various |

---

## Disagreement Levels

When model probability differs significantly from market:

| Level | Ratio Range | Meaning | Stake Adjustment |
|-------|-------------|---------|------------------|
| Minor | 1.0-1.5x | Normal variance | 100% stake |
| Moderate | 1.5-2.0x | Some disagreement | 75% stake |
| Major | 2.0-3.0x | Significant disagreement | 50% stake |
| Extreme | 3.0x+ | Likely model error | 25% stake |

Ratio = `our_probability / implied_probability`

---

## Status Values

### Bet Status
| Value | Meaning |
|-------|---------|
| NULL | Pending (not settled) |
| Win | Bet won |
| Loss | Bet lost |
| Void | Bet cancelled/voided |

### Injury Status
| Value | Meaning |
|-------|---------|
| Active | Fully fit |
| Minor Concern | Minor issue, likely to play |
| Questionable | May or may not play |
| Doubtful | Unlikely to play |
| Out | Confirmed out |
| Returning | Coming back from injury |

---

## Fatigue Scores

| Score Range | Status | Meaning |
|-------------|--------|---------|
| 90-100 | Fresh | Well-rested, optimal |
| 70-89 | Normal | Standard fatigue |
| 50-69 | Tired | Elevated fatigue |
| <50 | Exhausted | Significant fatigue concern |

---

## Pinnacle Comparison Values

When Betfair odds are compared against Pinnacle:

| Status | Condition | Meaning |
|--------|-----------|---------|
| **GOOD VALUE** | Betfair > Pinnacle | Betfair offers better odds - bet! |
| **CAUTION** | Betfair < Pinnacle by 7.5-15% | Slightly worse value - bet with caution |
| **SKIP** | Betfair < Pinnacle by >15% | Bad value - don't bet |
| **N/A** | No Pinnacle odds available | Cannot compare |

**Example:** Pinnacle offers 2.00, Betfair offers 1.80. Difference = 10%. Status = CAUTION.
