# Tennis Betting System v3.1 - Operations Guide

**Daily Operations Manual for System Operators**

Last updated: February 5, 2026

---

## Table of Contents

1. [Daily Workflow](#1-daily-workflow)
2. [System Startup](#2-system-startup)
3. [Odds Capture](#3-odds-capture)
4. [Match Analysis](#4-match-analysis)
5. [Bet Placement](#5-bet-placement)
6. [Bet Monitoring](#6-bet-monitoring)
7. [Settlement](#7-settlement)
8. [Quick Refresh](#8-quick-refresh)
9. [Discord Bot Operations](#9-discord-bot-operations)
10. [Cloud Sync](#10-cloud-sync)
11. [Common Scenarios](#11-common-scenarios)
12. [End of Day](#12-end-of-day)
13. [Weekly/Monthly Tasks](#13-weeklymonthly-tasks)

---

## 1. Daily Workflow

This is the typical order of operations each day. The entire workflow takes approximately 15-20 minutes of active work, with the system running in the background for the rest of the day.

### Morning (Before First Matches Start)

| Step | Action | Time | Details |
|------|--------|------|---------|
| 1 | Start the main application | 30 sec | `python src/main.py` from the project directory |
| 2 | Verify startup tasks complete | 1-2 min | Watch the footer status bar -- it should say "Loaded X matches from Betfair" |
| 3 | Run Quick Refresh | ~5 min | Click **Quick Refresh** on the home screen to update match results and stats |
| 4 | Open Betfair Tennis | 30 sec | Click the **Betfair Tennis** card to capture current odds |
| 5 | Click **Capture All** | 1-2 min | Fetches all upcoming tennis match odds from Betfair Exchange |
| 6 | Open Bet Suggester | 30 sec | Click the **Bet Suggester** card |
| 7 | Click **Analyze All** | 1-3 min | System analyzes every upcoming match with odds |
| 8 | Review value bets | 2-5 min | Examine suggested bets, double-click matches for detailed analysis |
| 9 | Add bets to tracker | 1-2 min | Click **Add Bet** for individual bets, or use **Auto Mode** |
| 10 | Verify Discord bot is running | 30 sec | Check that `local_monitor.py` is running (or start it) |

### During the Day

- **Auto Mode** (optional): Toggle on from the home screen. It runs every 30 minutes, automatically capturing odds, analyzing, and adding qualifying bets.
- **Discord Bot**: Monitors bet status via Betfair API every 30 seconds. Sends live alerts and result notifications automatically.
- **Manual Check**: Periodically open Bet Tracker to view live scores and pending bet status.

### Evening

- Run `!refresh` in Discord to settle any remaining bets
- Open Bet Tracker and verify all completed matches are settled
- Check the day's P/L on the Statistics tab

---

## 2. System Startup

### Starting the Main Application

**From a terminal or command prompt:**

```
cd "C:\Users\marca\OneDrive\Documents\claude-playground\tennis betting"
python src/main.py
```

**If using the installed version:** Launch "Tennis Betting System" from the Start menu or desktop shortcut.

The application window launches maximized with a dark slate theme. On startup, the system automatically:

1. **Checks bet model tags** -- Backfills any bets missing their model classification. The footer status bar will briefly show "Checking bet model tags...".
2. **Fetches Betfair matches** -- Connects to the Betfair Exchange API and imports upcoming match odds for the next 48 hours. The footer shows "Fetching Betfair matches..." then "Loaded X matches from Betfair".

**What you should see after startup:**

- The header reads **"Tennis Betting System"** with subtitle "ATP/WTA/ITF match analysis, form tracking & expected value betting".
- Five stat cards across the top: **PLAYERS**, **MATCHES**, **ANALYSED**, **TOTAL BETS**, and **ROI** (color-coded: green = positive, red = negative).
- The **Getting Started** guide shows three numbered steps: (1) Betfair Tennis, (2) Bet Suggester, (3) Quick Refresh.
- Five feature cards in a grid: **Betfair Tennis**, **Bet Suggester**, **Bet Tracker**, **Rankings**, **Database**.
- A row of action buttons along the bottom: **Full Refresh**, **Quick Refresh**, **TE Import**, **Clear Matches**, **Manual Bet**, and **Auto Mode** on the right.
- The footer bar shows surface pills (Hard, Clay, Grass, Carpet), a status indicator dot, and a data source checksum.
- The **Last:** label near Quick Refresh shows how long ago data was last refreshed (e.g., "3h ago"). If it shows in amber/yellow, data is more than a day old.

**If the Betfair footer shows "Betfair credentials not configured":**
Edit `credentials.json` in the project root directory with your Betfair API key, username, and password. See Section 11 for details.

### Starting the Discord Bot (Local Monitor)

The Discord bot runs as a separate process. You have two options:

**Option A -- Visible console window (recommended for debugging):**
```
python local_monitor.py
```

**Option B -- Silent background startup (no console window):**
Double-click `start_monitor.vbs` in the project root directory. This uses `pythonw` so no console window appears.

**What happens on bot startup:**

1. Loads credentials from `credentials.json` (Betfair, Supabase, Discord bot token).
2. Logs in to Betfair Exchange API.
3. Connects to Discord and appears online.
4. Checks for currently live bets and adds them to tracking *without* sending duplicate alerts.
5. Syncs in-progress status from the local SQLite database to Supabase.
6. Starts two recurring loops:
   - **Monitor loop** (every 30 seconds): Checks Betfair for in-play matches and settles completed bets.
   - **Local DB sync loop** (every 2 minutes): Syncs `in_progress` flags from local DB to Supabase.

The console output (Option A) shows timestamped log messages like:
```
[2026-01-31 09:00:00] Tennis Betting Monitor + Bot starting...
[2026-01-31 09:00:01] Discord bot connected as TennisBetBot#1234
[2026-01-31 09:00:02] Betfair login successful
[2026-01-31 09:00:03] Checking for currently live bets (no alerts on startup)...
[2026-01-31 09:00:04] Initial local DB sync completed
```

**Required credentials in `credentials.json`:**
```json
{
  "betfair_app_key": "your-betfair-app-key",
  "betfair_username": "your-betfair-username",
  "betfair_password": "your-betfair-password",
  "supabase_url": "https://your-project.supabase.co",
  "supabase_key": "your-supabase-anon-key",
  "discord_bot_token": "your-discord-bot-token",
  "discord_webhook_url": "https://discord.com/api/webhooks/..."
}
```

### Verify Everything Is Running

After startup, confirm these three things:

1. **Main app footer** shows "Loaded X matches from Betfair" (not "Betfair credentials not configured").
2. **Discord bot** console shows "Discord bot connected as [bot name]" and "Betfair login successful".
3. **Discord channel**: Send `!pending` to verify the bot responds.

---

## 3. Odds Capture

### How Betfair Capture Works

The Betfair capture system connects to the Betfair Exchange API to fetch pre-match odds for tennis matches. It does NOT place any bets -- it only reads publicly available market data.

### Running a Manual Capture

1. On the home screen, click the **Betfair Tennis** card (cyan glow on hover) or its **Open** button.
2. The Betfair Capture window opens. It shows connection status and a list of available matches.
3. Click **Capture All** to fetch all upcoming tennis match odds (next 48 hours by default).

### What the Capture Cycle Does

For each match on Betfair, the system:

1. **Logs in** to Betfair using credentials from `credentials.json`.
2. **Calls `listMarketCatalogue`** to get all Tennis Match Odds markets starting within 48 hours.
3. **Filters out** in-play matches, doubles matches (player names containing "/"), and markets with no odds.
4. **Sorts runners** by `sortPriority` to ensure consistent player ordering between captures.
5. **Fetches odds** via `listMarketBook` for all markets (batched in groups of 40 per API limits).
6. **Detects surface** from the competition/tournament name using the centralized `get_tournament_surface()` function in `config.py`.
7. **Matches player names** to the database using the name matcher (multiple strategies: exact match, reversed name, fuzzy match, stored mappings in `name_mappings.json`).
8. **Normalizes tournament names** (strips year suffixes like "2026", removes "Ladies/Men's" prefixes).
9. **Compares against Pinnacle odds** (optional, if the Odds API key is configured) to flag potential discrepancies.
10. **Saves to the `upcoming_matches` table** in the SQLite database.
11. **Logs low-liquidity matches** but still captures them (the system does not skip matches based on liquidity).

### When to Run Capture

- **On app startup**: Happens automatically. The footer status shows progress.
- **Before analyzing bets**: Always capture fresh odds before running Analyze All in the Bet Suggester.
- **Auto Mode**: Captures odds every 30 minutes when enabled.
- **Manual**: Click Betfair Tennis > Capture All whenever you want the latest prices.

### How to Verify Odds Are Current

1. Check the footer status bar on the home screen -- it should show "Loaded X matches from Betfair" with a recent count.
2. Open the Betfair Tennis window and verify the "Captured At" timestamps are recent.
3. In the Bet Suggester, the matches list shows odds columns. If odds are stale (many hours old), the P1/P2 odds may not reflect current market conditions.

### Key Notes

- **Minimum liquidity filter**: Set to 0 (captures all matches regardless of liquidity), but matches with less than 25 GBP total matched are filtered out in the Bet Suggester.
- **In-play matches**: Always skipped during capture. The system is pre-match only.
- **Session expiry**: Betfair sessions can expire. If capture fails, re-run it (the system auto-logs in each time).

---

## 4. Match Analysis

### How to Open Match Analysis

There are two ways to analyze a match:

**From the Bet Suggester:**
1. Open the Bet Suggester.
2. After running **Analyze All**, double-click any match row in the results table.
3. A detailed analysis popup opens.

**From the Manual Bet feature:**
1. Click **Manual Bet** on the home screen (purple button).
2. Type a player name in the "Player 1" field (minimum 2 characters). A dropdown appears with matching database players.
3. Select both players from the dropdowns.
4. Choose a surface (Hard, Clay, or Grass).
5. Click **Analyze**.

### What Each Section Means

The analysis popup is organized into several sections:

#### Top Section: Player Comparison

- **Player 1** (blue, left side): Name, database ID, win probability percentage, and number of matches in the database.
- **Player 2** (yellow/gold, right side): Same information.
- **Confidence**: A percentage indicating how much data supports the analysis. Higher = more reliable. Below 30% is unreliable.
- **LOW DATA warning**: Appears if a player has fewer than 10 matches in the database.

#### Factor Analysis Table

The system evaluates 9 factors, each contributing a weighted score. The table shows:

| Column | Description |
|--------|-------------|
| **Factor** | The analysis factor name |
| **P1 Score** | Player 1's normalized score (0.0 to 1.0) |
| **P2 Score** | Player 2's normalized score (0.0 to 1.0) |
| **Advantage** | Difference favoring one player (positive = favors P1) |
| **Weight** | How much this factor contributes to the final probability |

**The 8 factors and what they measure (v3.1 weights):**

| Factor | Weight | What It Measures |
|--------|--------|-----------------|
| **Surface** | 22% | Historical win rate on this specific surface — strongest market-beating signal |
| **Form** | 20% | Win/loss record in last 10-20 matches, weighted by recency and opponent quality |
| **Fatigue** | 17% | Days since last match, workload in 7/14/30 days — market underweights this |
| **Ranking** | 13% | Current ATP/WTA ranking converted to Elo |
| **Perf Elo** | 13% | Rolling 12-month Elo calculated from actual match results |
| **Recent Loss** | 8% | Penalty for losing in last 3 days (-10%) or last 7 days (-5%) |
| **H2H** | 5% | Head-to-head record between these specific players, surface-weighted |
| **Momentum** | 2% | Consecutive wins on the same surface type in last 14 days |

**Note:** Injury factor has been **deprecated** and replaced by the Activity Edge Modifier.

**Edge Modifiers** (post-probability adjustments, not weighted factors):
- **Serve Edge Modifier**: Reduces edge up to 20% when serve stats (DR) conflict with the pick
- **Activity Edge Modifier**: Reduces edge up to 40% for returning/inactive players

#### Value Analysis Section

For each player, if odds are available:

- **Our Probability**: What the model thinks the player's chance of winning is. This is after calibration (0.60 shrinkage) and market blend (0.35 weight).
- **Implied Probability**: What the betting odds imply (1 / odds).
- **Edge**: Our probability minus implied probability. Positive = we see value.
- **Expected Value (EV)**: The expected return per unit staked. Positive means profitable long-term.
- **Recommended Stake**: Kelly Criterion calculation (0.375 fractional Kelly, rounded to 0.5 units, capped at 3.0 units). M1 bets get 1.5x boost.
- **Model**: Which betting models this bet qualifies for (M1-M12, or None). M1+M11 is the highest-confidence combination.

#### Serve Stats Comparison Table

If serve/return statistics are available from Tennis Ratio, a comparison table shows:

- 1st Serve %, 1st Serve Won %, 2nd Serve Won %
- Aces per match, Double Faults per match
- Service Games Won %, Return 1st/2nd Won %
- Break Points Saved %, Break Points Converted %
- Return Games Won %

**DR (Dominance Ratio)** is the key metric for the Serve Edge Modifier: `service_games_won / return_games_won`. A higher DR indicates serve-dominant play. When DR conflicts with the model's pick by 0.10+, edge is reduced up to 20%.

#### Activity Scores

Each player shows an activity score (0-100) based on:
- Match count in last 90 days (0-60 points)
- Largest gap in last 120 days (0-40 points)

Labels: Active (≥80), Moderate (≥60), Low Activity (≥40), Returning (≥20), Inactive (<20). When the minimum activity score is low, edge is reduced up to 40%.

### What to Look For

When reviewing an analysis:

1. **M1+M11 qualification**: Bets with both M1 (triple confirmation) and M11 (surface edge) have the strongest track record (65% win rate, +55.6% ROI at n=40).
2. **Multiple factors agreeing**: If form, surface, AND ranking all favor the same player, the signal is stronger.
3. **Edge of 5% or more**: Edges below 3% are generally noise.
4. **Serve alignment**: Check if DR (Dominance Ratio) supports or conflicts with the pick. Conflicting DR reduces edge.
5. **Activity scores**: Both players should be "Active" (≥80) for maximum confidence. Returning/Inactive players add uncertainty.
6. **Surface data available**: Check if both players have surface-specific win rates. Surface is the strongest factor (22% weight).
7. **Fatigue mismatches**: One player fresh, the other heavy workload -- this is a market inefficiency the model exploits.
8. **LOW DATA warnings**: Be cautious with bets where either player has few matches in the database.
9. **Avoid Pure M3**: Bets that ONLY qualify for M3 (no M1, M11, or other hard models) have a 7.7% win rate historically.

---

## 5. Bet Placement

### Manual Mode vs Auto Mode

**Manual Mode** (default): You review each bet suggestion, decide whether to add it, and click through the add bet dialog. Gives you full control.

**Auto Mode**: The system automatically captures odds, analyzes all matches, and adds qualifying value bets to the tracker every 30 minutes. No human approval is required per bet. Only bets that qualify for a model (M3, M4, M7, or M8) are added.

### How Auto Mode Works

1. Click the **Auto Mode** button (purple, right side of the action bar). The label changes to **"Stop Auto"** and the status shows **"Auto: ON"**.
2. The system immediately runs the first cycle:
   - **Step 1**: Captures Betfair odds (48 hours ahead).
   - **Step 1b**: Updates closing odds for CLV tracking on pending bets.
   - **Step 1c**: Fetches serve stats from Tennis Ratio for players in upcoming matches (cached for 7 days).
   - **Step 2**: Runs Analyze All to find value bets.
   - **Step 3**: Adds qualifying value bets to the tracker automatically.
3. After each cycle, the status shows "Auto: Next run at HH:MM" with the time of the next scheduled run (30 minutes later).
4. To stop, click **Stop Auto**. The status reverts to "Auto: OFF".

**What Auto Mode adds:**
- Only bets that qualify for at least one hard model (M1, M3, M4, M5, M7, M8).
- Only bets with positive EV above 5%.
- Only bets with stake of at least 0.25 units.
- Duplicate detection prevents betting the same match twice or both sides of a match.
- Odds floor of 1.70 applies -- no bets below this price.
- M1 bets receive 1.5x staking boost automatically.

### The 11 Betting Models

**Hard Models** (stake-determining):

| Model | Name | Criteria | Philosophy |
|-------|------|----------|------------|
| **M1** | Triple Confirmation | Model edge + serve aligned + active players | Premium model with 1.5x staking |
| **M3** | Sharp Zone | 5-15% edge | Moderate, realistic edges. "Sharp" betting territory. |
| **M4** | Favorites | Our prob >= 60% | High confidence plays regardless of edge size. |
| **M5** | Underdog | Edge >= 10%, odds 3-10, 15+ matches | Upset value plays |
| **M7** | Grind | 3-8% edge AND odds < 2.50 | Small edges on short-priced favorites. |
| **M8** | Profitable Baseline | Our prob >= 55% AND odds < 2.50 | Moderate confidence on short odds. |

**Soft Models** (tag-only, no staking impact):

| Model | Criteria | Use Case |
|-------|----------|----------|
| **M2** | Serve data available + both active | Data confirmed |
| **M9** | Odds 2.00-2.99, serve data, edge 5-10% | Value zone |
| **M10** | Odds < 2.20, prob >= 55%, both active | Confident grind |
| **M11** | Surface factor >= 0.15, odds 2.00-3.50, edge >= 5% | Surface edge |

**Fade Model:**

| Model | Criteria | Use Case |
|-------|----------|----------|
| **M12** | Pure M3/M5 triggers + opponent odds 1.20-1.50 | Bet opponent 2-0 scoreline |

**Key performance data (n=160 settled bets):**
- **M1+M11 together**: 65.0% win rate, +55.6% ROI — proven edge
- **Pure M3 only**: 7.7% win rate — avoid in isolation

A bet can qualify for multiple models simultaneously (e.g., "Model 1, Model 3, Model 11"). Bets that qualify for **no model** are filtered out and never added.

### Adding a Bet Manually (From Bet Suggester)

1. Open **Bet Suggester** and click **Analyze All**.
2. The results table shows all matches with columns: Match, Tournament, Surface, P1 Odds, P2 Odds, Our Prob, Edge, EV, Units, Model.
3. **Double-click** a match row to open the detailed analysis popup. Review the factors.
4. To add the bet: Click **Add Bet** in the analysis popup, or select the row in the results table and click the **Add Bet** button.
5. The Add Bet dialog pre-fills all fields from the analysis. Review and click **Confirm**.
6. The system performs duplicate checks:
   - **Match already bet**: If any bet exists on this match (even the other player), it blocks with a warning.
   - **Exact duplicate**: If the same selection on the same match already exists, it blocks.
7. On success, the bet is saved to the local SQLite database, synced to Supabase (if configured), and a Discord notification is sent.

### Adding a Bet Manually (Manual Bet Feature)

For matches not yet on Betfair or when you want to analyze any two players:

1. Click **Manual Bet** (purple button on the home screen).
2. Type Player 1's name -- a searchable dropdown appears after 2 characters. Select the correct player.
3. Type Player 2's name -- same searchable dropdown. Select the correct player.
4. Choose the surface (Hard, Clay, Grass) from the dropdown.
5. Click **Analyze**.
6. The analysis popup opens showing full factor analysis, but without odds-based value calculations (since no Betfair odds are provided).

### Data Quality Checks

For bets of 2 or more units, the system applies stricter checks:

- Both players must have at least 5 recent matches (3+ for smaller stakes).
- If the database shows insufficient matches, the system checks Tennis Explorer online for verification.
- The selection player's 2026 form must not be 15%+ worse than the opponent's.
- If a player has played recently but has few matches in the database, the stake may be halved instead of blocking.

### Stake Confidence Adjustments

For bets of 2+ units, the system may reduce stakes based on data quality:

- No surface data for either player: -20%.
- Surface data missing for one player: -10%.
- No head-to-head history: -10%.
- Limited form data (fewer than 5 matches per player): -15%.
- Ranking dominates the edge (>40% of weighted advantage): -10%.
- The floor is 50% of the original stake. The minimum stake is 0.5 units.

---

## 6. Bet Monitoring

### The Bet Tracker Interface

Open the Bet Tracker by clicking the **Bet Tracker** card on the home screen. The window opens maximized with several sections:

#### Summary Stats (Top)

Four stat cards along the top:
- **Total Bets**: Count of all bets placed.
- **Win Rate**: Percentage of settled bets that won.
- **P/L**: Total profit/loss in units (green if positive, red if negative).
- **ROI**: Return on investment percentage.

#### Pending Bets Tab

Shows all unsettled bets in a sortable table with columns:

| Column | Description |
|--------|-------------|
| **Date** | Match date |
| **Tournament** | Tournament name |
| **Match** | "Player 1 vs Player 2" |
| **Selection** | The player you bet on |
| **Odds** | Odds at placement |
| **Stake** | Units staked |
| **Model** | Which model(s) the bet qualifies for |
| **Our Prob** | Model's win probability |
| **EV** | Expected value at placement |
| **Live** | Shows "In-Play" (blue highlight) if the match is currently being played |
| **Close** | Closing odds captured just before the match went in-play |
| **CLV** | Closing Line Value -- how much better/worse you got compared to closing odds |

#### Live Score Detection

The Bet Tracker automatically connects to Betfair every 30 seconds to detect which of your pending bets are currently in-play:

- Rows with live matches are **highlighted in blue** with "In-Play" in the Live column.
- The status bar at the bottom shows "Live: X live (HH:MM:SS)" with a timestamp.
- When a match goes live, the `in_progress` flag is set in the local database.
- The Discord bot also detects live status independently via its own Betfair connection.

#### Settled Bets Tab

Shows all completed bets with Win/Loss/Void result, profit/loss amount, and settled date.

#### Statistics Tab

Multiple breakdown views:
- **By Model**: Performance of each model (M1-M12) with bets, wins, ROI, and average CLV. Pay special attention to M1+M11 combinations.
- **By Tour**: Grand Slam, ATP, WTA, Challenger, ITF.
- **By Surface**: Hard, Clay, Grass.
- **By Gender**: Male vs Female.
- **By Odds Range**: 1.00-1.50, 1.50-2.00, 2.00-3.00, 3.00-5.00, 5.00+.
- **By Stake Size**: 0.5u, 1.0u, 1.5u, 2.0u, 2.5u, 3.0u.
- **By Disagreement Level**: How far our model diverges from the market.
- **Weekly P/L Grid**: Day-by-day (Mon-Sun) breakdown of staked/returned/profit/ROI for the current and previous week. Uses `settled_at` date, not match date.

#### P/L Chart

A cumulative profit/loss line chart with gradient fill and grid lines. Tracks P/L over time across all settled bets.

### Tracking Live Bets

To see which bets are currently live:

1. Open Bet Tracker and look at the Pending Bets tab.
2. Blue-highlighted rows = currently in-play.
3. The "Live" column shows "In-Play" for active matches.
4. Alternatively, use `!inplay` in Discord to see a formatted table of live bets.

### Refreshing Closing Odds

Click the **Refresh Odds** button in the Bet Tracker to update closing odds for pending bets. This fetches the latest Betfair odds and stores them in the `odds_at_close` field. CLV is then calculated as the difference between your placement odds and the closing odds.

---

## 7. Settlement

### Settlement Sources (In Priority Order)

Bets are settled through three methods, attempted in this order:

#### 1. Betfair API (Primary -- Automatic)

The Discord bot's monitor loop checks Betfair every 30 seconds:

1. When a previously in-play match's market status changes to **CLOSED**, the system checks the runners for a **WINNER** status.
2. It compares the winning runner's `selectionId` to the stored selection IDs for the bet.
3. If the bet's selection matches the winner, it is settled as **Win**. Otherwise, **Loss**.
4. **Win P/L** = stake x (odds - 1) x 0.95 (after 5% Betfair commission). Note: The actual commission rate is configurable (currently set to 2% in `config.py`).
5. **Loss P/L** = -stake.
6. The result is written to both the local SQLite database and Supabase.
7. A result alert is sent to Discord (green embed for wins, red for losses).

#### 2. Tennis Explorer (Fallback -- On Demand)

If a bet cannot be settled via Betfair (market expired, no selection IDs, etc.), Tennis Explorer is used:

1. The `!refresh` Discord command triggers this check.
2. The system scrapes Tennis Explorer results pages for the last 2-3 days across all tour types (ATP, WTA, ITF men, ITF women).
3. It matches player names from the bet to the winner/loser names on Tennis Explorer using normalized last-name comparison.
4. Settlement results show "[TE]" in the summary to distinguish from Betfair settlements "[BF]".

#### 3. Manual Settlement

If automated settlement fails (name mismatch, walkover, retirement, etc.):

1. Open the **Bet Tracker**.
2. Select the pending bet.
3. Click **Win**, **Loss**, or **Void** button.
4. Confirm the action.
5. The P/L is calculated automatically (with Betfair commission for wins).

### The Discord Bot !refresh Command

Type `!refresh` in the Discord channel to force-check all pending bets:

1. The bot syncs local data to the cloud first.
2. **Phase 1 (Betfair)**: Checks all pending bets against the full Betfair tennis market catalogue. Settles any with CLOSED status.
3. **Phase 2 (Tennis Explorer)**: For bets that Betfair could not settle, scrapes Tennis Explorer for completed match results.
4. Sends a summary message showing:
   - Settled bets (with W/L indicators and P/L)
   - Currently live bets
   - Remaining unsettled bets
   - Total P/L for settled bets

Example output:
```
Refresh complete:

Settled (3) -- +1.45u:
  W Djokovic v Sinner (+1.90u) [BF]
  L Swiatek v Sabalenka (-1.00u) [TE]
  W Alcaraz v Rublev (+0.55u) [BF]

Currently live (2):
  Zverev v Medvedev
  Gauff v Zheng

2 bet(s) still pending (not yet played or not found on TE)
```

### How to Verify Settlements

1. After `!refresh`, compare the settled bets against actual match results on ATP/WTA websites.
2. In the Bet Tracker, check the Settled Bets tab. Verify that Win/Loss assignments match actual results.
3. If a settlement is wrong (e.g., name mismatch caused wrong result), you can re-settle:
   - Select the bet in the Settled tab.
   - Click the correct Win/Loss button.
   - Confirm the change when prompted ("Change result?").

---

## 8. Quick Refresh

### What It Does

Quick Refresh updates the system's match database and derived statistics. It runs four operations in sequence:

1. **GitHub Data Download** (~2-3 min): Downloads the latest 7 days of match results from the GitHub tennis data repository. This includes ATP, WTA, Challenger, and ITF results scraped from Tennis Explorer.
2. **Surface Stats Recalculation** (~30 sec): Recalculates surface-specific win rates for all players based on updated match data.
3. **Performance Elo Ratings** (~1 min): Recomputes rolling 12-month Performance Elo ratings from actual match results. K-factors vary by tournament level (Grand Slam: 48, ATP: 32, Challenger: 24, etc.).
4. **Tennis Ratio Serve Stats** (~1-2 min): Fetches/updates serve and return statistics from Tennis Ratio for players in upcoming matches. Stats are cached for 7 days.

### When to Run It

- **Once each morning** before analyzing bets. This ensures the system has yesterday's results and updated form data.
- **After a big day of tennis** (e.g., after a Grand Slam day), to get all results into the database.
- **Before the first bet placement** of the day.

### How to Run It

1. On the home screen, click **Quick Refresh** (cyan button).
2. A dialog opens showing "Quick Refresh (7 Days)" with a progress log.
3. Click **Start Refresh**.
4. Watch the log for progress messages. Typical output:
   ```
   Starting quick refresh (last 7 days only)...
   Downloading atp_matches_2026.csv...
   Downloading wta_matches_2026.csv...
   Processing matches: 847 found
   Matches imported: 312
   Matches skipped: 15 (unknown players)

   Quick refresh complete!
     Matches found: 847
     Matches imported: 312
   Recalculating surface statistics...
     Surface stats updated: 3102 records
   Recalculating Performance Elo ratings...
     Performance Elo updated: 2847 players
   Updating serve stats from Tennis Ratio...
     Serve stats: 45 updated, 120 cached, 3 failed
   ```
5. The "Last:" timestamp near the Quick Refresh button updates to show "Just now".

### Expected Duration

Approximately **5 minutes** total. The GitHub download is the longest step. Serve stats fetching depends on how many players need updating.

### Full Refresh vs Quick Refresh

| Feature | Quick Refresh | Full Refresh |
|---------|--------------|--------------|
| Data source | GitHub (tennisdata repo) | GitHub (tennisdata repo) |
| Time range | Last 7 days | Last 12 months |
| Duration | ~5 minutes | ~30-40 minutes |
| When to use | Daily, morning routine | Weekly, or after major data issues |
| Button | **Quick Refresh** (cyan) | **Full Refresh** (green) |
| Updates Elo | Yes | Yes (after serve stats) |
| Updates serve stats | Yes | Yes |

---

## 9. Discord Bot Operations

### Available Commands

All commands use the `!` prefix and are sent in the designated Discord channel.

#### !inplay

Shows all currently in-play bets in a formatted ASCII table.

```
LIVE BETS (2)
+----------------------+--------------+------+------+----------------------+
| Match                | Selection    | Odds | Stake| Tournament           |
+----------------------+--------------+------+------+----------------------+
| Djokovic v Sinner    | Djokovic     | 1.85 | 1.5u | Australian Open      |
| Swiatek v Sabalenka  | Sabalenka    | 2.10 | 1.0u | Australian Open      |
+----------------------+--------------+------+------+----------------------+
```

The bot syncs local database live status before responding, so it reflects the latest state from the main app's Bet Tracker.

#### !pending

Shows all pending (unsettled) bets, sorted by stake descending.

```
PENDING BETS (8)
+----------------------+--------------+------+------+----------------------+
| Match                | Selection    | Odds | Stake| Tournament           |
+----------------------+--------------+------+------+----------------------+
| Alcaraz v Rublev     | Alcaraz      | 1.55 | 2.0u | Australian Open      |
| Gauff v Zheng        | Gauff        | 1.72 | 1.5u | Australian Open      |
| ...                  | ...          | ...  | ...  | ...                  |
+----------------------+--------------+------+------+----------------------+
Total stake: 8.5u
```

Shows the first 12 bets if there are more. Shows total stake at the bottom.

#### !stats

Shows today's settlement statistics.

```
TODAY'S STATS
Record: 5W - 2L
P/L: +3.45u
Bets Settled: 7
```

Color-coded: green if profitable, red if losing.

#### !refresh

Forces a check of all pending bets against Betfair and Tennis Explorer. See Section 7 for full details. This is the most important command for settling bets.

Use it:
- After matches have finished but the bot missed them.
- When you want to force-settle bets that the 30-second monitor loop has not caught.
- At end of day to clean up remaining pending bets.

#### !alert win/loss [match description]

Manually sends a result alert to the channel. Usage:

```
!alert win Djokovic vs Sinner
!alert loss Swiatek vs Sabalenka
```

The bot searches pending and settled bets for a match description containing the text you provide. If found, it sends a formatted embed alert.

#### !resend

Re-sends the most recent result alert with full CLV/closing odds data. Useful if the original alert was missed or if CLV data has been updated since the alert was first sent.

### Automatic Alerts

The bot sends alerts automatically without any commands:

**Live Alert (blue embed):**
Sent when a pending bet's match goes in-play on Betfair. Shows match, selection, odds, stake, model, tournament, closing odds, and CLV.

**Result Alert (green/red embed):**
Sent when a match finishes and the bet is settled. Shows match, selection, odds, P/L, closing odds, and CLV. Green for wins, red for losses.

### CLV (Closing Line Value) in Alerts

CLV measures whether you got better or worse odds than the closing line:
- **Positive CLV** (e.g., +3.5%): You got better odds than the market closing price. This is the primary indicator of long-term profitability.
- **Negative CLV** (e.g., -2.1%): The odds shortened after you placed the bet, meaning the closing market disagreed with you.

CLV is included in both live and result alerts when available.

---

## 10. Cloud Sync

### Supabase Integration

The system uses Supabase (hosted PostgreSQL) as a cloud database to bridge between the main app and the Discord bot. The local SQLite database is the source of truth; Supabase is a sync target.

### When Sync Runs

- **On bet placement**: When a bet is added via the main app, it is immediately synced to Supabase via `sync_bet_to_cloud()`.
- **On settlement**: When a bet is settled (manually or via the bot), both the local DB and Supabase are updated.
- **Every 2 minutes**: The Discord bot's `local_db_sync_loop` reads all pending bets from the local SQLite database and upserts them to Supabase.
- **On every Discord command**: Before responding to `!inplay`, `!pending`, etc., the bot runs `sync_local_to_cloud()` to ensure Supabase has the latest data.
- **Live status sync**: The local DB's `in_progress` field (set by the Bet Tracker's live score detection) is synced to Supabase's `is_live` field every 2 minutes.

### How to Verify Sync

1. Add a bet in the main app.
2. Wait up to 2 minutes.
3. Run `!pending` in Discord -- the new bet should appear.
4. Alternatively, log into your Supabase dashboard and check the `pending_bets` table directly.

### What Gets Synced

The Supabase `pending_bets` table stores:
- `id` (matches local bet ID)
- `match_date`, `tournament`, `match_description`, `selection`
- `odds`, `stake`, `model`, `our_probability`
- `result`, `profit_loss`
- `is_live` (boolean -- synced from local `in_progress`)
- `market_id` (Betfair market ID for result checking)
- `selection_ids` (JSON mapping of runner names to Betfair selection IDs)
- `created_at`, `updated_at`, `finished_at`

### If Sync Fails

Cloud sync is non-blocking. If Supabase is unreachable:
- The main app continues working normally with the local SQLite database.
- The Discord bot will use stale data until sync resumes.
- Errors are logged to the console but do not interrupt normal operation.

---

## 11. Common Scenarios

### "Betfair session expired"

**Symptoms**: Capture All fails, or the Discord bot stops detecting live matches.

**Fix**:
- **Main app**: Simply run Betfair Tennis > Capture All again. The system re-authenticates on every capture attempt.
- **Discord bot**: The bot automatically retries login when an API call fails with a 401 error. If persistent, restart `local_monitor.py`.

### "No odds available" for a match

**Symptoms**: A match appears in the upcoming matches list but has no P1/P2 odds.

**Possible causes**:
- The match has not been listed on Betfair yet (try again later).
- The match was listed but removed (walkover, withdrawal).
- Betfair liquidity is extremely low.

**Fix**: Wait and re-capture. If the match is today and still no odds, it likely will not be tradeable.

### "Match cancelled / Player withdrew"

**Symptoms**: A pending bet is on a match that has been cancelled or a player withdrew.

**Fix**:
1. Open the Bet Tracker.
2. Select the pending bet.
3. Click **Void** to settle it with zero P/L.
4. The bet will move to the Settled tab with "Void" status.

### "Wrong settlement" (bet marked Win but actually Lost, or vice versa)

**Symptoms**: The result in the Bet Tracker does not match the actual match outcome.

**Likely cause**: Name matching confusion (e.g., "De Minaur" matched to the wrong runner).

**Fix**:
1. Open the Bet Tracker.
2. Go to the Settled Bets tab.
3. Find the incorrectly settled bet.
4. Click the correct result button (Win/Loss).
5. Confirm when prompted "Change result?".
6. The P/L will be recalculated.

### "Player name not matched" (Unknown player)

**Symptoms**: In the Bet Suggester or Betfair capture, a match shows as "Unknown" for one or both players. The analysis cannot run.

**Fix (immediate)**:
1. When you run **Analyze All** and there are unknown players, the system may show an "Unknown Player Resolver" dialog.
2. In the dialog, search for the player in the database.
3. If found, select them and click **Use Selected Player**. Check "Save name mapping permanently" to prevent this recurring.
4. If the player is genuinely new, click **Add as New Player** and fill in their details.

**Fix (permanent)**:
The name mapping is saved to `data/name_mappings.json`. Once a mapping is saved (e.g., "Novak Djokovic" on Betfair maps to database player ID 12345), it will be used automatically in all future captures and analyses.

### "Betfair credentials not configured"

**Symptoms**: The home screen footer shows this message. Betfair capture does not work.

**Fix**:
1. Create or edit `credentials.json` in the project root directory (same folder as `local_monitor.py`).
2. Add your Betfair API credentials:
   ```json
   {
     "betfair_app_key": "YOUR_ACTUAL_APP_KEY",
     "betfair_username": "your_betfair_username",
     "betfair_password": "your_betfair_password"
   }
   ```
3. Restart the application.

### "Discord bot not responding"

**Symptoms**: Commands like `!pending` or `!stats` get no response in Discord.

**Check**:
1. Is `local_monitor.py` running? Check for a `pythonw` process or the console window.
2. Is the bot online in Discord (green dot next to its name)?
3. Are the Supabase credentials correct in `credentials.json`?
4. Is the `discord_bot_token` correct?

**Fix**: Restart `local_monitor.py`. Check the console output for error messages.

### "Duplicate bet blocked"

**Symptoms**: Trying to add a bet gives an error "A bet already exists for this match".

**Explanation**: The system prevents betting on both sides of the same match. If you already have a bet on Player A in "Player A vs Player B", you cannot add a bet on Player B.

**Fix**: This is intentional. If you genuinely want to change your selection, void the existing bet first, then add the new one.

---

## 12. End of Day

### Checklist Before Closing

Perform these checks before shutting down for the day:

#### 1. Settle All Completed Bets

- Run `!refresh` in Discord.
- Open the Bet Tracker and check the Pending Bets tab.
- All matches that have finished should be settled (no blue "In-Play" highlights, and ideally the only remaining pending bets are for tomorrow's matches).
- If any today's-date bets remain pending, settle them manually (look up the result online).

#### 2. Check Today's P/L

- In the Bet Tracker, go to the Statistics tab.
- Look at the **Weekly P/L Grid** -- today's column should show the day's staked, returned, profit, and ROI.
- Alternatively, use `!stats` in Discord for a quick summary.

#### 3. Verify Pending Bets Are Correct

- Review the Pending Bets tab. All remaining bets should be for future matches (tomorrow or later).
- If you see any stale bets from past dates, investigate and settle or void them.

#### 4. Review Auto Mode Status

- If Auto Mode was running, check how many bets it added today.
- Review the notes column -- auto-added bets show "[AUTO]" in the notes.
- Decide whether to leave Auto Mode running overnight or disable it.

#### 5. Stop or Leave Running

- **If leaving Auto Mode running overnight**: The system will continue capturing odds and adding bets for tomorrow's early matches. The Discord bot will monitor and settle.
- **If shutting down**: Click the X button on the main app. This stops Auto Mode and the background updater. The Discord bot (`local_monitor.py`) runs independently and can be left running.

### Closing the Application

Close the main app window with the X button. This:
- Stops the Auto Mode timer if running.
- Stops any background update threads.
- Does NOT affect the Discord bot (it runs as a separate process).

---

## 13. Weekly/Monthly Tasks

### Weekly Tasks

#### Review Model Performance

1. Open Bet Tracker > Statistics tab > By Model view.
2. Check each model's:
   - **Win rate**: Is it above the implied probability? (This means the model is finding genuine edges.)
   - **ROI**: Is it positive? Negative ROI after 100+ bets suggests the model criteria may need adjustment.
   - **Average CLV**: Positive average CLV is the strongest indicator of long-term edge.
3. Note which models are performing best and worst.

**Critical rule**: Do NOT adjust model criteria until you have at least 100 bets per model. Small samples are statistically meaningless.

#### Check Data Quality

1. Open Database > Players tab.
2. Run **Check Data** to identify players with:
   - Missing rankings
   - No recent matches
   - Stale data (not updated recently)
3. For players who are clearly active (competing in current tournaments) but have no recent matches in the database, run Quick Refresh or Full Refresh.

#### Review Flagged Bets

The Bet Tracker identifies bets that should be reviewed:
- **Extreme disagreement** (model 3x+ more confident than market)
- **High stake on longshot** (2+ units on odds of 5.00+)
- **Max stake losses** (3-unit losses)

Check these bets to understand why the model disagreed with the market so strongly.

#### Run Full Refresh (Weekly)

Run a Full Refresh once a week (Saturday or Sunday is ideal). This downloads 12 months of match data and ensures the database is comprehensive. Takes approximately 30-40 minutes.

### Monthly Tasks

#### Review Bankroll

1. Calculate total units profit/loss for the month using the Statistics tab.
2. Determine if the unit size needs adjusting based on bankroll growth/decline.
3. The current unit size is 2% of bankroll (configurable in `config.py` under `KELLY_STAKING["unit_size_percent"]`).

#### Review by Tour Level

1. Check the By Tour breakdown in Statistics.
2. Are you profitable on ATP but losing on ITF? Or vice versa?
3. After 100+ bets per level, consider whether certain tour levels should receive higher/lower weighting.

#### Review by Surface

1. Check the By Surface breakdown.
2. The model's surface factor (22% weight) is its **strongest** edge source.
3. Large discrepancies in performance between surfaces may indicate the model's surface data needs improvement.

#### Check Serve Stats Coverage

1. The Tennis Ratio scraper updates serve stats for players in upcoming matches.
2. If many players are showing "failed" in the serve stats update log, check whether Tennis Ratio's website has changed format.
3. Serve stats are cached for 7 days -- if a player has stale serve stats, a Quick Refresh will attempt to update them.

#### Review CLV Trends

1. In the Statistics tab, the By Model view shows average CLV per model.
2. **Consistently positive CLV** (even small, like +1-2%) is the strongest evidence that your model has an edge.
3. **Negative CLV** suggests the market is correcting against your positions -- re-evaluate model assumptions.
4. CLV analysis requires at least 200+ bets to be statistically meaningful.

---

## Appendix: System Architecture Quick Reference

### File Locations

| Item | Path |
|------|------|
| Source code | `src\` (41 modules) |
| Main application | `src\main.py` |
| Discord bot | `local_monitor.py` (project root) |
| Configuration | `src\config.py` |
| Database | `C:\Users\Public\Documents\Tennis Betting System\data\tennis_betting.db` |
| Credentials | `credentials.json` (project root) |
| Name mappings | `data\name_mappings.json` |
| Documentation | `docs\` |

### Data Sources

| Source | What It Provides | Update Frequency |
|--------|-----------------|------------------|
| Betfair Exchange API | Pre-match odds, live market status, settlement results | Real-time (per capture) |
| GitHub tennisdata | Historical match results (ATP/WTA/ITF) | Daily (Quick Refresh) |
| Tennis Explorer | Match results for settlement fallback | On demand (!refresh) |
| Tennis Ratio | Serve/return statistics (13 metrics per player) | Cached 7 days |

### Database Tables (Key Tables)

| Table | Purpose |
|-------|---------|
| `players` | Player names, rankings, Elo, country, hand |
| `matches` | Historical match results |
| `upcoming_matches` | Betfair captures with odds |
| `bets` | All placed bets (pending and settled) |
| `surface_stats` | Per-player surface win rates |
| `player_serve_stats` | Tennis Ratio serve/return metrics |
| `match_analyses` | Logged match analyses for backtesting |
| `performance_elo` | Rolling 12-month Performance Elo ratings |

### Key Configuration (config.py)

| Setting | Current Value | Description |
|---------|--------------|-------------|
| Kelly fraction | 0.375 | Portion of full Kelly used for staking |
| M1 boost | 1.5x | M1 (triple confirmation) gets 50% higher stakes |
| Exchange commission | 2% | Betfair commission on winnings |
| Min odds floor | 1.70 | No bets placed below this price |
| Min units | 0.25 | Minimum stake to place a bet |
| Max units | 3.0 | Maximum stake cap |
| Min EV threshold | 5% | Minimum expected value for a bet |
| Shrinkage factor | 0.60 | Probability calibration (asymmetric, favorites only) |
| Market blend | 0.35 | 35% market odds, 65% calibrated model |
| Data quality min matches | 3 (5 for 2u+) | Minimum recent matches required per player |

---

*Document version: 3.1 | System version: v3.1 | Updated: Feb 5, 2026*
