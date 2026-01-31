# Session Log - January 31, 2026

## Bug Fix: Discord `!refresh` Settling All Bets as Losses

### Problem
Overnight bets settled via `!refresh` → Tennis Explorer (Phase 2) were ALL marked as losses, regardless of actual outcome. Two bets that were actually wins (Simakin, Shimabukuro) were recorded as losses, and one match that hadn't even been played yet (Baptiste vs Kostovic) was also incorrectly settled as a loss.

### Root Cause (Two Bugs)

**Bug 1 — `settle_from_result` name comparison (`local_monitor.py:730`)**
Tennis Explorer returns names in "Lastname F." format (e.g., "Sinner J.", "Krueger M."). The `settle_from_result` function compared `selection.split()[-1]` (e.g., "sinner") to `winner_name.split()[-1]` (e.g., "j."). The last word of a TE name is always the initial, never the surname. So the comparison **always failed** → every bet = Loss.

**Bug 2 — `players_match` partial match was too loose (`local_monitor.py:546`)**
After normalization, TE initials became single letters ("n", "j", "c"). The partial match checked `"n" in "djokovic"` → True, because single letters are substrings of almost any name. This caused `find_result_for_bet` to match the **wrong TE result** to each bet — the first random match where both initials happened to be substrings of the bet player names. This is why Baptiste vs Kostovic (not yet played) was "found" and settled.

### What Was Changed

**`local_monitor.py`** — 3 changes:

1. **New `get_last_name()` helper** — Extracts the actual surname from any format. For TE "Lastname F." format (last word is single letter), returns the last significant part (2+ chars). For normal "Firstname Lastname" format, returns the last word as before.

2. **New `names_match_single()` and `get_significant_name_parts()` helpers** — Used by `settle_from_result` to compare player names. Strips initials (single-letter parts) from both names, then checks if any significant name part from one name exactly matches any from the other. E.g., "Jannik Sinner" → ["jannik","sinner"], "Sinner J." → ["sinner"] → match on "sinner".

3. **`partial_match` in `players_match` now rejects single-letter matches** — Added `len(name1) <= 1 or len(name2) <= 1` guard. Prevents TE initials from matching as substrings of unrelated names.

4. **`players_match` now uses `get_last_name()` for last-name extraction** — Properly handles TE "Lastname F." format by extracting the actual surname instead of the initial.

### Data Corrections

Found and verified correct results via Tennis Explorer scraping:

| ID | Match | Selection | Was | Correct | Action |
|----|-------|-----------|-----|---------|--------|
| 1188 | Simakin vs Sakellaridis | Simakin | Loss (-1.00) | Win (+1.44) | Corrected |
| 1187 | Shimabukuro vs Hijikata | Shimabukuro | Loss (-1.00) | Win (+1.58) | Corrected |
| 1183 | Baptiste vs Kostovic | Kostovic | Loss (-0.50) | Not played | Reset to pending |
| 1185 | Vekic vs Osorio | Osorio | Win | Win | Already correct (Betfair path) |
| 1180 | Hon vs Sasnovich | Hon | Loss | Loss | Already correct |
| 1179 | Kartal vs Starodubtseva | Starodubtseva | Loss | Loss | Already correct |
| 1186 | Krueger vs Svajda | Krueger | Loss | Loss | Already correct |
| 1182 | Korda vs Draxl | Draxl | Loss | Loss | Already correct |

**Net P/L correction**: +1.44 + 1.58 + 1.00 + 1.00 + 0.50 = **+5.42u swing** (two losses became wins, one false loss removed)

Updated in both local SQLite DB and Supabase.

### Files Modified
- `local_monitor.py` (root + synced to dist)

---

## Lookahead Bias Fix: Cloud Backtester

### Problem
Backtest showed +20-30% ROI across all models, but live betting showed -10% ROI over 500+ bets. Investigation revealed 6 of 8 factors in `match_analyzer.py` had **lookahead bias** — they used current/future data when analyzing historical matches (e.g., current rankings instead of match-time rankings, all-time H2H including future matches, `datetime.now()` instead of match date).

### Evidence
- H2H factor had 99.6% accuracy in backtest (knew all future results)
- Calibration broke down badly at high confidence: 75-100% predicted → 60.2% actual
- Surface, ranking, momentum, recent_loss, injury, performance_elo all used future data

### What Was Changed

**`cloud_backtester.py`** — 2 changes:
1. **SQL query**: Changed `w.current_ranking` / `l.current_ranking` to `COALESCE(m.winner_rank, w.current_ranking)` / `COALESCE(m.loser_rank, l.current_ranking)` — uses match-time rankings recorded in the `matches` table
2. **`process_match()`**: Passes `p1_rank_override` and `p2_rank_override` to `calculate_win_probability()`

**`match_analyzer.py`** — 12 changes across 9 methods:

| Method | Change | Bias Fixed |
|--------|--------|-----------|
| `calculate_win_probability()` | Added `p1_rank_override`, `p2_rank_override` params; computes `backtest_date`; propagates to all factor calls | Orchestrator |
| `calculate_form_score()` | Added `player_rank_override`; uses it for player's own Elo instead of current ranking | Player ranking |
| `get_surface_stats()` | Added `as_of_date`; backtest path computes from raw matches before date instead of pre-aggregated table; 2yr window uses match date not `datetime.now()` | Surface stats + time window |
| `get_ranking_factors()` | Added `p1_rank_override`, `p2_rank_override`; overrides cache/DB ranking lookup | Current ranking |
| `get_performance_elo_factors()` | Added rank overrides; uses `_ranking_to_elo(override)` instead of stored performance Elo | Current perf Elo |
| `get_h2h()` | Added `before_date`; backtest path calculates from raw matches filtered by date | All-time H2H |
| `get_injury_status()` | Added `as_of_date`; returns neutral (score=100) for backtest | Current injury status |
| `calculate_recent_loss_penalty()` | Added `as_of_date`; filters matches before date; uses match date as reference | `datetime.now()` |
| `calculate_momentum()` | Added `as_of_date`; filters matches before date; uses match date as reference | `datetime.now()` |
| Breakout recomputation block | Passes rank overrides through to `get_ranking_factors` and `get_performance_elo_factors` | Breakout path |

### Backward Compatibility
All new parameters default to `None`. When `None`, every method behaves exactly as before. The live app is completely unaffected.

### Verification
Ran `--sample 20` locally. Key result confirming fix works:
- **H2H accuracy dropped from 99.6% → 50.0%** (no longer knows future results)
- **Injury shows "No data"** (correctly returns neutral for backtest)
- No crashes, 60% overall accuracy on 20-match sample

### Files Modified
- `src/cloud_backtester.py` (+ synced to dist)
- `src/match_analyzer.py` (+ synced to dist)

### Next Step
Push changes and run full backtest via GitHub Actions to get realistic ROI numbers.

---
