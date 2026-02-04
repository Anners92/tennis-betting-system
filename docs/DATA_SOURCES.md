# DATA SOURCES - Tennis Betting System v3.1

## Data Integration Reference

**Audience:** Data Engineering Team
**Last Updated:** February 5, 2026
**System Version:** 3.1

---

## Table of Contents

1. [Data Source Overview Table](#1-data-source-overview-table)
2. [Betfair Exchange API](#2-betfair-exchange-api)
3. [GitHub tennisdata / Tennis Explorer Scraper](#3-github-tennisdata--tennis-explorer-scraper)
4. [Tennis Explorer (Direct Scraping)](#4-tennis-explorer-direct-scraping)
5. [Tennis Ratio](#5-tennis-ratio)
6. [Player Name Matching](#6-player-name-matching)
7. [Data Freshness and TTL](#7-data-freshness-and-ttl)
8. [Data Quality Controls](#8-data-quality-controls)
9. [Data Flow Diagrams](#9-data-flow-diagrams)
10. [Error Handling by Source](#10-error-handling-by-source)
11. [Monitoring and Alerts](#11-monitoring-and-alerts)

---

## 1. Data Source Overview Table

| Source | URL | Data Type | Update Frequency | Auth Method | Rate Limits | Failure Mode | Fallback |
|--------|-----|-----------|------------------|-------------|-------------|--------------|----------|
| **Betfair Exchange API** | `api.betfair.com/exchange/betting/rest/v1.0/` | Pre-match odds, market status, liquidity, in-play detection, closing odds | Every auto-cycle (~30s for monitoring, on-demand for capture) | App Key + Username/Password session token | 40 markets per `listMarketBook` request; 200ms sleep between batches | Login failure halts capture; API errors skip affected markets | Betfair public navigation endpoints (no auth, limited data) |
| **Betfair Navigation (Public)** | `www.betfair.com/www/sports/navigation/facet/v1/search` | Market listings, competition structure, basic odds | On-demand via UI | None (public `_ak` token embedded) | Standard HTTP rate limits | Returns empty results; silent degradation | None (secondary source already) |
| **Betfair Exchange Readonly** | `ero.betfair.com/www/sports/exchange/readonly/v1/bymarket` | Exchange odds, runner descriptions, market state | On-demand via UI | None (public `_ak` token embedded) | Standard HTTP rate limits | Returns empty results | Betfair Navigation endpoint |
| **Tennis Explorer** | `www.tennisexplorer.com` | Match results (ATP/WTA/ITF/Challenger), player profiles, rankings, match history | Full import: monthly; Quick refresh: daily (last 7 days) | None (web scraping with User-Agent) | 0.3-0.5s delay between requests | HTTP errors skip affected pages; layout changes break parsing | None (primary historical data source) |
| **Tennis Ratio** | `www.tennisratio.com/players/{PascalCase}.html` | 13 serve/return statistical metrics per player | TTL-based: every 7 days per player | None (web scraping with User-Agent) | 1.0s delay between requests | Generic page detection (HTTP 200 without `window.playerData`); failure cached as `tennis_ratio_not_found` | Empty stats record persisted; analysis proceeds without serve data |
| **The Odds API** (Optional) | External API | Pinnacle odds for cross-validation | Per Betfair capture cycle | API key | Per-plan limits | Warning logged; capture continues without comparison | Betfair odds used alone |

---

## 2. Betfair Exchange API

### 2.1 Overview

The Betfair Exchange API is the most critical data source. It provides real-time pre-match odds, market liquidity, in-play status, and is the basis for closing line value (CLV) tracking. The system uses two distinct integration paths:

- **Authenticated API** (`betfair_capture.py`): Full Exchange API with session tokens, used for production odds capture
- **Public Endpoints** (`betfair_tennis.py`): Unauthenticated navigation/readonly endpoints, used as UI fallback

### 2.2 Authenticated API Endpoints

#### Login Endpoint

```
POST https://identitysso.betfair.com/api/login
```

**Request Headers:**
```
X-Application: {app_key}
Content-Type: application/x-www-form-urlencoded
Accept: application/json
```

**Request Body:**
```
username={username}&password={password}
```

**Response (Success):**
```json
{
    "status": "SUCCESS",
    "token": "session-token-string"
}
```

**Response (Failure):**
```json
{
    "status": "FAIL",
    "error": "INVALID_USERNAME_OR_PASSWORD"
}
```

The session token is stored in `self.session_token` and reused for all subsequent API calls. There is no automatic refresh -- if the session expires, the next capture cycle triggers a full re-login.

#### Keep Alive Endpoint

```
POST https://identitysso.betfair.com/api/keepAlive
```

Defined in constants but not actively called in the current codebase. Session tokens are assumed to persist for the duration of a capture cycle.

#### List Events

```
POST https://api.betfair.com/exchange/betting/rest/v1.0/listEvents/
```

**Request Headers (all API calls):**
```
X-Application: {app_key}
X-Authentication: {session_token}
Content-Type: application/json
```

**Request Body:**
```json
{
    "filter": {
        "eventTypeIds": ["2"],
        "marketStartTime": {
            "from": "2026-01-31T12:00:00Z",
            "to": "2026-02-02T12:00:00Z"
        }
    }
}
```

Tennis event type ID is always `"2"`.

**Response fields extracted:** `event.id`, `event.name`, `event.countryCode`, `event.timezone`, `event.openDate`, `marketCount`

#### List Competitions

```
POST https://api.betfair.com/exchange/betting/rest/v1.0/listCompetitions/
```

Returns all active tennis competitions (tournaments). Used for the "List Competitions" feature. Results are sorted by `marketCount` descending.

#### List Market Catalogue (Primary Discovery Endpoint)

```
POST https://api.betfair.com/exchange/betting/rest/v1.0/listMarketCatalogue/
```

**Request Body:**
```json
{
    "filter": {
        "eventTypeIds": ["2"],
        "marketTypeCodes": ["MATCH_ODDS"],
        "marketStartTime": {
            "from": "{utc_now}",
            "to": "{utc_now + hours_ahead}"
        }
    },
    "marketProjection": [
        "RUNNER_DESCRIPTION",
        "MARKET_START_TIME",
        "EVENT",
        "COMPETITION"
    ],
    "maxResults": "1000",
    "sort": "FIRST_TO_START"
}
```

**Key behaviors:**
- Default look-ahead window: 48 hours (configurable via `--hours` CLI or UI spinbox)
- Only `MATCH_ODDS` markets are captured (match winner, not set betting)
- Results are filtered to exactly 2 runners (excludes doubles matches)
- Doubles are also filtered by the `/` character in runner names
- Optional `competitionIds` filter narrows to specific tournaments
- Maximum 1000 results per request

**Response fields extracted per market:**
- `marketId` -- unique market identifier
- `marketName`, `marketStartTime`
- `event.id`, `event.name`
- `competition.id`, `competition.name`
- `runners[].selectionId`, `runners[].runnerName`, `runners[].sortPriority`

**Runner ordering:** Runners are sorted by `sortPriority` to ensure consistent player 1/player 2 ordering across captures. This prevents odds from being swapped between captures when Betfair returns runners in different orders.

#### List Market Book (Odds Retrieval)

```
POST https://api.betfair.com/exchange/betting/rest/v1.0/listMarketBook/
```

**Request Body:**
```json
{
    "marketIds": ["1.234567890", "1.234567891", ...],
    "priceProjection": {
        "priceData": ["EX_BEST_OFFERS"],
        "virtualise": true
    }
}
```

**Rate limiting:**
- Maximum 40 market IDs per request (Betfair hard limit)
- Requests are batched: `for i in range(0, len(market_ids), 40)`
- 200ms sleep (`time.sleep(0.2)`) between batches
- This means 100 markets takes 3 requests with 400ms total delay

**Response fields extracted per runner:**
```python
{
    'back_odds': ex.availableToBack[0].price,    # Best back price
    'back_size': ex.availableToBack[0].size,      # Liquidity at best back
    'lay_odds': ex.availableToLay[0].price,       # Best lay price
    'lay_size': ex.availableToLay[0].size,         # Liquidity at best lay
    'status': runner.status,                        # ACTIVE, WINNER, LOSER, REMOVED
    'total_matched': runner.totalMatched            # Total money matched on this runner
}
```

**Market-level fields:**
```python
{
    'status': market.status,           # OPEN, SUSPENDED, CLOSED
    'inplay': market.inplay,           # Boolean - True if match is live
    'total_matched': market.totalMatched  # Total market liquidity
}
```

### 2.3 Market Filtering Logic

Captured markets go through multiple filters before being stored:

1. **In-play filter:** Markets with `inplay=True` are skipped entirely. Only pre-match odds are captured.
2. **Doubles filter:** Runner names containing `/` are skipped (e.g., "Player A / Player B").
3. **Runner count filter:** Only markets with exactly 2 runners are accepted.
4. **No-odds filter:** Markets where either player has `None` back odds are skipped (logged as "SKIPPED (no odds)").
5. **Competition filter (optional):** CLI `--competition` or UI text field narrows to matching tournament names.
6. **Liquidity logging:** Markets where either player has less than GBP 100 in best back liquidity are flagged as "LOW LIQUIDITY" but still captured. `MIN_LIQUIDITY_GBP` is set to 0 (capture all).
7. **Pinnacle comparison (optional):** If The Odds API is configured, Betfair odds are compared against Pinnacle. Discrepancies are logged as WARNING/CAUTION/GOOD VALUE but never cause matches to be skipped. `MAX_ODDS_DISCREPANCY` is set to 1.0 (100%), effectively disabling skipping.

### 2.4 Odds Format

All odds from Betfair are **decimal odds** (European format). Example: odds of 2.50 mean a GBP 1 bet returns GBP 2.50 (GBP 1.50 profit). The system stores and uses decimal odds throughout.

### 2.5 Surface Detection from Betfair Data

Betfair does not provide surface information. The system infers surface from the competition name using centralized detection in `config.py`:

```python
surface = get_tournament_surface(competition_name, date_str)
```

This function checks against:
- 60+ known clay tournament name patterns
- 20+ known grass tournament name patterns (only matched during June-July grass season)
- Explicit surface markers in names: `" - clay"`, `"(clay)"`, `" - grass"`, etc.
- Default: `"Hard"` (most common surface)

Word boundary matching prevents false positives (e.g., "halle" does not match inside "challenger").

### 2.6 Player Matching from Betfair to Database

When Betfair runner names are received (e.g., "Novak Djokovic"), the system attempts to match them to existing database players in this priority order:

1. **Name Matcher JSON lookup** (`name_matcher.get_db_id(betfair_name)`): Checks `name_mappings.json` for explicit Betfair-to-database-ID mappings.
2. **Database player lookup by mapped ID** (`db.get_player(mapped_id)`): If a mapping to an integer ID exists, fetch that player.
3. **Database player lookup by name** (`db.get_player_by_name(betfair_name)`): Direct name match in the players table.
4. **Auto-create player** (`_create_missing_player(betfair_name)`): If no match found, create a new player entry with a deterministic negative ID (hash-based, range -100000 to -999999) to avoid collisions with real ATP/WTA IDs.

Player lookups are cached per capture cycle to avoid repeated database queries.

### 2.7 Closing Odds and CLV Tracking

The system captures closing odds for CLV (Closing Line Value) tracking:

- Each auto-cycle, after Betfair capture, `update_pending_bets_closing_odds()` is called
- For every pending bet, the system looks up the latest odds for that player matchup in `upcoming_matches`
- The last capture before a match goes in-play becomes the "closing odds"
- CLV is calculated as the difference between placement odds and closing odds
- Stored in the `bets` table: `odds_at_close REAL`, `clv REAL`

### 2.8 Tournament Name Normalization

Betfair tournament names are normalized before storage:

```python
normalize_tournament_name(name)
```

- Strips year suffixes: `"Concepcion Challenger 2026"` becomes `"Concepcion Challenger"`
- Removes gendered prefixes: `"Ladies Wimbledon"` becomes `"Wimbledon"`, `"Men's Australian Open"` becomes `"Australian Open"`
- Strips trailing whitespace

### 2.9 Public Endpoint Fallback (betfair_tennis.py)

The `BetfairTennisScraper` class provides an unauthenticated alternative using public Betfair endpoints:

**Navigation endpoint:**
```
GET https://www.betfair.com/www/sports/navigation/facet/v1/search
    ?_ak=nzIFcwyWhrlwYMrh
    &alt=json
    &currencyCode=GBP
    &exchangeLocale=en_GB
    &locale=en_GB
    &marketTypes=MATCH_ODDS
    &eventTypeIds=2
    &facets=eventType,competition,event,market
```

**Exchange readonly endpoint:**
```
GET https://ero.betfair.com/www/sports/exchange/readonly/v1/bymarket
    ?_ak=nzIFcwyWhrlwYMrh
    &alt=json
    &currencyCode=GBP
    &locale=en_GB
    &marketProjections=EVENT,COMPETITION,MARKET_DESCRIPTION,RUNNER_DESCRIPTION
    &marketTypes=MATCH_ODDS
    &eventTypeIds=2
```

**Market-specific odds:**
```
GET https://ero.betfair.com/www/sports/exchange/readonly/v1/bymarket
    ?_ak=nzIFcwyWhrlwYMrh
    &alt=json
    &currencyCode=GBP
    &locale=en_GB
    &marketIds={market_id}
    &marketProjections=RUNNER_DESCRIPTION
    &priceProjections=BEST_OFFERS
```

The public `_ak` token `nzIFcwyWhrlwYMrh` is a well-known Betfair public application key. SSL verification is disabled for these requests (`ssl.CERT_NONE`). These endpoints are less reliable and return less data than the authenticated API.

### 2.10 Data Stored from Betfair

Each captured match is stored in the `upcoming_matches` table with:

| Column | Type | Source |
|--------|------|--------|
| `tournament` | TEXT | Normalized competition name |
| `date` | TEXT | `market_start_time` (format: `YYYY-MM-DD HH:MM:SS`) |
| `surface` | TEXT | Inferred from tournament name + date |
| `player1_id` | INTEGER | Matched/created player ID |
| `player2_id` | INTEGER | Matched/created player ID |
| `player1_name` | TEXT | Betfair runner name |
| `player2_name` | TEXT | Betfair runner name |
| `player1_odds` | REAL | Best back price |
| `player2_odds` | REAL | Best back price |
| `player1_liquidity` | REAL | GBP at best back price |
| `player2_liquidity` | REAL | GBP at best back price |
| `total_matched` | REAL | Total market volume matched |
| `analyzed` | INTEGER | 0 = not yet analyzed, reset on odds update |

Deduplication: If a match already exists (same `player1_name`, `player2_name`, `tournament`), odds are updated and `analyzed` is reset to 0 so the match will be re-analyzed with fresh odds.

---

## 3. GitHub tennisdata / Tennis Explorer Scraper

### 3.1 Overview

Despite the module name `github_data_loader.py`, this system no longer downloads from the GitHub repository `https://github.com/Anners92/tennisdata`. The `download_data()` method is a pass-through stub. All match data is now scraped directly from Tennis Explorer via `TennisExplorerScraper`.

The reference URL in config:
```python
TENNIS_EXPLORER_DATA_URL = "https://github.com/Anners92/tennisdata/raw/main/tennis_data.db.gz"
```
This URL is defined but not used in current code. The scraper has fully replaced the GitHub CSV/database download.

### 3.2 Data Extracted

The scraper fetches:
- **Match results:** Winner name, loser name, score, date, tournament, surface
- **Player profiles:** Name, country, DOB, height, hand (L/R), ranking
- **Match history per player:** Year-specific pages with opponent, score, round, tournament

### 3.3 Import Pipeline

#### Full Import (`import_to_main_database`)

1. Verify player count > 0 (players must exist before matches can be imported)
2. Build `PlayerNameMatcher` index from all players in database
3. Scrape 4 tour types sequentially:
   - `atp-single` (ATP singles)
   - `wta-single` (WTA singles)
   - `itf-women-single` (ITF women's singles)
   - `itf-men-single` (ITF men's singles)
4. Default: 12 months of data per tour type (`self.months_to_fetch = 12`)
5. For each month, day-by-day fetching is used (not month-only URLs) to capture ALL tournaments including ATP 250 events
6. Rate limiting: 0.3s between daily page requests, 0.5s between monthly blocks
7. For each match:
   - Look up winner and loser via `PlayerNameMatcher.find_player_id()`
   - If either player not found, skip match (players are LOCKED -- no new players created)
   - Check for duplicates: same `winner_id` + `loser_id` within +/- 3 days
   - Generate unique match ID: `TE_{date}_{winner_id}_{loser_id}`
   - Use `INSERT OR IGNORE` to avoid overwriting existing data
8. Report name matching failures (first 20 logged for debugging)

#### Quick Refresh (`quick_refresh_recent`)

Identical pipeline but:
- Only fetches last N days (default: 7 days)
- Uses `fetch_recent_days()` instead of full month fetching
- Much faster: ~5 minutes vs potentially hours for full import
- Same duplicate detection and player matching

### 3.4 URL Format for Tennis Explorer Results

**Day-specific results:**
```
https://www.tennisexplorer.com/results/?type={tour_type}&year={year}&month={month:02d}&day={day:02d}
```

**Month results (legacy, less complete):**
```
https://www.tennisexplorer.com/results/?type={tour_type}&year={year}&month={month:02d}
```

**Player profile:**
```
https://www.tennisexplorer.com/player/{slug}/
```

**Player year-specific matches:**
```
https://www.tennisexplorer.com/player/{slug}/?annual={year}
```

**Player search:**
```
https://www.tennisexplorer.com/list-players/?search-text-pl={last_name}
```

### 3.5 Player Matching Across Sources

The `PlayerNameMatcher` class (in `tennis_explorer_scraper.py`) is purpose-built for matching Tennis Explorer names (format: `"Lastname F."`) to database names (format: `"Firstname Lastname"`). See Section 6 for the complete matching strategy.

Players are LOCKED during import -- only matches are imported, linked to existing players. If a player cannot be matched, the match is skipped. This prevents database pollution from misspelled or ambiguous names.

### 3.6 Data Quality Notes

- Tennis Explorer sometimes shows matches multiple times on a page; deduplication handles this
- Day-by-day fetching produces more complete data than month-only URLs
- Scores are parsed from HTML tables with paired rows (winner row has class `bott`, loser in next row)
- Seeding numbers like "(20)" are stripped from player names
- The current year is inferred from the page date, which can fail around year boundaries

---

## 4. Tennis Explorer (Direct Scraping)

### 4.1 Base URL and Scraping Method

```
Base URL: https://www.tennisexplorer.com
Parser: BeautifulSoup (html.parser)
```

**Session headers:**
```python
{
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}
```

Request timeout: 15 seconds (player profiles), 30 seconds (results pages).

### 4.2 Pages Scraped

| Page Type | URL Pattern | Data Extracted |
|-----------|-------------|----------------|
| Results (day) | `/results/?type={tour}&year={y}&month={m}&day={d}` | Winner, loser, score, tournament, surface |
| Results (month) | `/results/?type={tour}&year={y}&month={m}` | Same as above (less complete) |
| Player profile | `/player/{slug}/` | Name, country, DOB, height, hand, ranking |
| Player year matches | `/player/{slug}/?annual={year}` | Match history with opponents |
| Player search | `/list-players/?search-text-pl={name}` | Player slugs for profile lookup |
| Rankings | Rankings pages (via scraper settings) | Current rankings (15 pages, 100/page = 1500 players per tour) |

### 4.3 Name Format

Tennis Explorer uses the format `"Lastname F."` (e.g., `"Grubor A."`, `"Djokovic N."`). Player profiles show names as `"Lastname Firstname"` in `<h3>` tags. The system converts these to `"Firstname Lastname"` format for database storage.

### 4.4 Rate Limiting

| Operation | Delay |
|-----------|-------|
| Between daily result pages | 0.3 seconds |
| Between monthly result blocks | 0.5 seconds |
| Between player ranking updates | 0.5 seconds |
| Between player year-page fetches | 0.3 seconds |

### 4.5 How Results Are Matched to Pending Bets

Tennis Explorer results are not directly matched to pending bets. Instead:
1. Results are imported into the `matches` table as historical data
2. The local monitor (`local_monitor.py`) checks Betfair market status for settled markets
3. When a Betfair market closes, the winner is determined from Betfair runner status (`WINNER`/`LOSER`)
4. Tennis Explorer data enriches the historical record post-settlement

### 4.6 Known Issues

1. **Layout changes:** Tennis Explorer periodically changes HTML structure. Match rows rely on specific CSS classes (`bott`) and table structure. Breaking changes require scraper updates.
2. **Blocking:** Aggressive scraping may trigger rate limiting or IP blocks. The system uses conservative delays and standard User-Agent headers.
3. **Incomplete data:** Month-only URLs miss some ATP 250 and lower-tier events. Day-by-day fetching was implemented as a fix.
4. **Year boundary issues:** Date parsing assumes current year for DD.MM. format dates, which can misattribute dates near January 1.
5. **Name ambiguity:** Common surnames (e.g., "Wang", "Zhang") with only first initials can match wrong players. The system uses ranking-based disambiguation.

---

## 5. Tennis Ratio

### 5.1 URL Format

```
https://www.tennisratio.com/players/{PascalCase}.html
```

**Examples:**
- Carlos Alcaraz: `https://www.tennisratio.com/players/CarlosAlcaraz.html`
- Novak Djokovic: `https://www.tennisratio.com/players/NovakDjokovic.html`

### 5.2 Name Normalization for URL Construction

The `_format_player_name_for_url()` method performs these transformations:

1. **Unicode normalization:** `unicodedata.normalize('NFKD', name)` followed by stripping combining characters. This converts accented characters to ASCII equivalents (e.g., "Ruud" stays "Ruud", "Baez" from "Baez" with accent stays "Baez").
2. **Hyphen replacement:** Hyphens become spaces so each part gets capitalized separately.
3. **Non-alpha removal:** `re.sub(r"[^a-zA-Z\s]", "", name)` strips periods, digits, etc.
4. **PascalCase conversion:** Each word is capitalized (first letter upper, rest preserved), then concatenated without spaces.

**Examples of transformation:**
```
"Carlos Alcaraz"     -> "CarlosAlcaraz"
"Novak Djokovic"     -> "NovakDjokovic"
"Felix Auger-Aliassime" -> "FelixAugerAliassime"
```

### 5.3 Reversed Name Fallback

If the first URL attempt fails, the system tries reversed word order:

```python
parts = player_name.strip().split()
reversed_name = parts[-1] + ' ' + ' '.join(parts[:-1])
```

This handles database names stored as `"Lastname Firstname"` vs Tennis Ratio expecting `"Firstname Lastname"`.

### 5.4 Generic Page Detection

Tennis Ratio does **not** return HTTP 404 for unknown players. Instead, it returns HTTP 200 with a generic listing page. The scraper detects this by checking for the presence of `window.playerData` in the response HTML:

```python
if 'window.playerData' not in response.text:
    return None  # Generic page, player not found
```

This is a critical check -- without it, the scraper would attempt to parse a player listing page as individual stats.

### 5.5 Data Extraction

The scraper extracts a JavaScript object from the page HTML:

```python
match = re.search(r'window\.playerData\s*=\s*(\{.*?\});', html, re.DOTALL)
data = json.loads(match.group(1))
```

Stats are extracted from the `ovr` (overall) section of `playerData`:

### 5.6 The 13 Metrics

| Metric Key | playerData Field | Description |
|------------|-----------------|-------------|
| `first_serve_pct` | `ovr.first_serve_accuracy` | First serve percentage |
| `first_serve_won_pct` | `ovr.first_serve_points` | Points won on first serve |
| `second_serve_won_pct` | `ovr.second_serve_points` | Points won on second serve |
| `aces_per_match` | `ovr.aces_per_match` | Average aces per match |
| `dfs_per_match` | `ovr.doublefaults_per_match` | Average double faults per match |
| `service_games_won_pct` | `ovr.service_games_won_ratio` | Service games won percentage |
| `return_1st_won_pct` | `ovr.return_1st_serve_points` | Points won returning first serve |
| `return_2nd_won_pct` | `ovr.return_2nd_serve_points` | Points won returning second serve |
| `bp_saved_pct` | `ovr.breakpoints_saved_ratio` | Break points saved percentage |
| `bp_converted_pct` | `ovr.breakpoints_converted_ratio` | Break points converted percentage |
| `return_games_won_pct` | `ovr.return_games_won_ratio` | Return games won percentage |
| `dominance_ratio` | `ovr.dominance_ratio` | Overall dominance ratio |
| `tiebreak_won_pct` | `ovr.tiebreak_won_perc` | Tiebreak win percentage |

All values are converted to `float` and rounded to 2 decimal places. `None` is used for missing values.

### 5.7 Failure Caching

When a player is not found on Tennis Ratio, an **empty record** is stored in the database:

```python
empty_stats = {k: None for k in [...all 13 keys...]}
self.db.upsert_player_serve_stats(player_id, empty_stats, source='tennis_ratio_not_found')
```

The `source` column is set to `'tennis_ratio_not_found'` (vs `'tennis_ratio'` for successful fetches). This serves as a negative cache -- the TTL check will skip this player until the TTL expires, preventing repeated failed lookups.

### 5.8 TTL (Time to Live)

Default TTL: **7 days** (`ttl_days=7` in `update_players_in_upcoming()`).

The `player_needs_serve_stats_update()` method checks the `updated_at` timestamp in `player_serve_stats`. If the record was updated within the last 7 days (regardless of whether it was a success or `not_found`), the player is skipped.

### 5.9 Rate Limiting

Between each player lookup: **1.0 second** (`time.sleep(1.0)` in `update_players_in_upcoming()`). This is the most conservative rate limit in the system.

### 5.10 Database Storage

Stats are stored in the `player_serve_stats` table with `UNIQUE(player_id)` constraint. The `upsert_player_serve_stats()` method uses `INSERT OR REPLACE` for atomic upserts.

---

## 6. Player Name Matching

### 6.1 Overview

Player name matching is one of the most complex subsystems. There are two independent matchers:

1. **`NameMatcher`** (in `name_matcher.py`): Used for Betfair-to-database matching during odds capture. Uses explicit JSON mappings + fuzzy matching.
2. **`PlayerNameMatcher`** (in `tennis_explorer_scraper.py`): Used for Tennis Explorer-to-database matching during result imports. Uses multi-strategy indexed matching.

### 6.2 The 6 Matching Strategies (from state_machines.txt)

When matching a Betfair name to the database, the system uses these strategies in order:

| Strategy | Method | Example |
|----------|--------|---------|
| **0. JSON Mappings** | Explicit lookup in `name_mappings.json` | `"Carlos Alcaraz Garfia"` -> player ID 207989 |
| **1. Exact Match** | Case-insensitive normalized comparison | `"Novak Djokovic"` == `"novak djokovic"` |
| **2. Reversed Name** | Swap first/last: `"A B"` becomes `"B A"` | `"Sinner Jannik"` -> `"Jannik Sinner"` |
| **3. All Parts Present** | All significant name parts found in any order | `"Juan Martin Del Potro"` matches regardless of order |
| **4. First + Last Any Order** | First and last name found in candidate | `"Alcaraz Carlos"` matches `"Carlos Alcaraz"` |
| **5. Fuzzy Match** | SequenceMatcher with 0.85 threshold (NameMatcher) or ranked candidate selection (PlayerNameMatcher) | `"Aleksandar Kovacevic"` ~= `"Aleksander Kovacevic"` |

If all strategies fail, the player is marked as UNKNOWN (`player_id = NULL` for Betfair capture, or match is skipped for Tennis Explorer imports).

### 6.3 PlayerNameMatcher Detailed Strategies

The `PlayerNameMatcher` in `tennis_explorer_scraper.py` uses a more sophisticated 6-strategy approach with indexed lookups:

1. **Exact match on normalized full name** (includes no-spaces variant). Only accepts if player has a ranking (avoids duplicate/abbreviated entries).
2. **Longest name part + initial match.** Searches `by_last_name` index, filters by initial. Skips parts shorter than 3 chars (to avoid "de", "da" prefix matches).
3. **Last name + initial combination lookup.** Uses `by_last_initial` index (e.g., `"djokovic_n"`). Supports 2-char last names for Asian surnames (Xu, Li, Wu, Ma).
4. **Fuzzy match -- all significant parts.** All parts with 3+ chars must appear in the candidate's name parts (bidirectional substring matching).
5. **Single significant part + initial.** Last resort for abbreviated names like `"Lastname X."`.
6. **Reversed name order.** Tries `"Jannik Sinner"` reversed to `"Sinner Jannik"`.

**Ranking-based disambiguation:** When multiple candidates match, `_pick_best_candidate()` selects:
1. The player with the best (lowest) ranking, if any are ranked
2. Players with positive IDs over negative IDs (real players over auto-created)
3. First candidate as final fallback

### 6.4 Name Normalization

Both matchers normalize names for comparison:

**NameMatcher normalization:**
- Replace hyphens with spaces
- Collapse multiple spaces
- Convert to lowercase
- Replace accented characters via a manual mapping table (40+ character substitutions)

**PlayerNameMatcher normalization:**
- Convert to lowercase
- Strip whitespace
- Remove periods
- Collapse multiple spaces

### 6.5 Cross-Source Matching Challenges

| Challenge | Source Formats | Resolution |
|-----------|---------------|------------|
| Name order | Betfair: `"Carlos Alcaraz"`, Tennis Explorer: `"Alcaraz C."`, Database: `"Carlos Alcaraz"` | Reversed name strategy |
| Accented characters | Betfair: `"Baez"`, Database: `"Baez"` (with accent) | Unicode normalization |
| Abbreviated names | Tennis Explorer: `"Djokovic N."` | Last name + initial matching |
| Compound names | `"Del Potro J."`, `"Van de Zandschulp"` | Multi-part matching with short-part skip |
| Asian names | `"Cody Wong Hong Yi"` vs `"Wong H."` | Multi-initial indexing (all parts indexed as potential initials) |
| Hyphenated names | `"Auger-Aliassime"` | Hyphen-to-space conversion before matching |
| Multiple players same surname | Two players named `"Wang"` | Ranking-based disambiguation |

### 6.6 The Hyphenated Name Fix

Hyphenated surnames (e.g., "Auger-Aliassime", "Navarro-Pastor") are handled by:

1. **NameMatcher:** Replaces hyphens with spaces during normalization
2. **Tennis Ratio scraper:** Replaces hyphens with spaces before PascalCase conversion (`name.replace('-', ' ')`)
3. **PlayerNameMatcher:** Each part of the hyphenated name is indexed separately in `by_name_parts` and `by_last_name`

### 6.7 Handling Unmatched Players

| Context | Behavior |
|---------|----------|
| **Betfair capture** | Auto-create player with negative hash-based ID (range -100000 to -999999). Deterministic: same name always gets same ID. |
| **Tennis Explorer import (players locked)** | Skip the match entirely. Log as name match failure. |
| **Tennis Explorer import (players unlocked)** | Create new player with sequential negative ID. After import, attempt to merge auto-created players to real players. |
| **Player history import** | Create opponents as new players with negative IDs, then merge to real players post-import. Deduplication removes resulting duplicate matches. |

---

## 7. Data Freshness and TTL

### 7.1 Per-Source Freshness

| Source | Freshness Mechanism | TTL / Refresh Interval |
|--------|--------------------|-----------------------|
| **Betfair odds** | Captured on-demand or per auto-cycle. Existing matches updated with latest odds on each capture. `analyzed` flag reset to 0 when odds change. | No TTL -- refreshed every capture cycle. Stale if no capture in 48+ hours. |
| **Tennis Explorer (full import)** | Manual trigger. Checks `MAX(date) FROM matches` to determine last imported data point. | Configurable: default 12 months lookback. No automatic TTL. |
| **Tennis Explorer (quick refresh)** | Automatic on startup or manual trigger. Fetches last 7 days. | 7 days default. Quick refresh timing: ~5 minutes. |
| **Tennis Ratio serve stats** | Per-player TTL check via `player_needs_serve_stats_update()`. | 7 days. Checked via `updated_at` column in `player_serve_stats`. Both successful and `not_found` results count. |
| **Player rankings** | Updated from Tennis Explorer player profiles on demand. | No automatic TTL. Updated per-player when ranking update is triggered for upcoming matches. |

### 7.2 Cache Invalidation

| Trigger | What Gets Invalidated |
|---------|----------------------|
| New Betfair capture | `upcoming_matches` rows updated with fresh odds; `analyzed` reset to 0 |
| "Clear All" button | All rows deleted from `upcoming_matches` |
| Full data import | Matches inserted with `INSERT OR IGNORE` (existing data preserved) |
| Player merge | Auto-created players merged to real players; duplicate matches removed |
| Tournament name sync | `normalize_tournament_name()` applied across `matches`, `bets`, `upcoming_matches` tables |

### 7.3 Staleness Detection

The system detects stale data through:

1. **Betfair:** If `upcoming_matches` is empty or has fewer than 10 matches, auto-capture is triggered on UI startup
2. **Matches:** `get_last_updated()` checks `MAX(date) FROM matches` to determine how current the historical data is
3. **Serve stats:** SQL query compares `updated_at` against `datetime('now', '-{days} days')`
4. **Rankings:** No automatic staleness detection; updated on-demand per player

---

## 8. Data Quality Controls

### 8.1 Validation Rules (data_validation.py)

All match data passes through the `DataValidator` before database insertion:

**Critical Rules (reject data):**

| Rule | Check | Consequence |
|------|-------|-------------|
| Winner != Loser | `winner_id != loser_id` | Match rejected, logged to CSV |
| Valid Winner ID | `winner_id` is not None, not 0, not empty | Match rejected |
| Valid Loser ID | `loser_id` is not None, not 0, not empty | Match rejected |
| Valid Date | Parseable as `YYYY-MM-DD`, not more than 7 days in future | Match rejected |
| Valid Score Format | At least 2 sets or RET/W/O notation | Warning only (logged, not rejected) |

**Warning Rules (log but allow):**

| Rule | Check |
|------|-------|
| Missing Tournament | `tourney_name` or `tournament` is empty |
| Missing Surface | `surface` is empty |

**Auto-fix Capabilities:**
- Convert IDs to integers (handles float-encoded IDs)
- Normalize date format (accepts `YYYY-MM-DD`, `DD-MM-YYYY`, `YYYY/MM/DD`, `DD/MM/YYYY`)
- Normalize surface names to canonical form (`"hard"` -> `"Hard"`, `"c"` -> `"Clay"`)

### 8.2 Validation Logging

All validation failures are logged to: `logs/data_validation.csv`

CSV columns: `timestamp`, `source`, `rule_violated`, `severity`, `winner_id`, `loser_id`, `winner_name`, `loser_name`, `date`, `tournament`, `details`

### 8.3 Duplicate Detection

| Context | Deduplication Method |
|---------|---------------------|
| **Match import (Tennis Explorer)** | Same `winner_id` + `loser_id` within +/- 3 days: skip. Match ID format `TE_{date}_{winner_id}_{loser_id}` with `INSERT OR IGNORE`. |
| **Betfair capture** | Same `player1_name` + `player2_name` + `tournament`: update odds instead of creating duplicate. |
| **Bet placement** | Check `match_description` + `tournament` in pending bets. Blocks betting on both sides of same match. |
| **Post-merge deduplication** | After auto-created players are merged to real players, duplicate matches (same date + winner_id + loser_id + normalized score digits) are removed, keeping the record with more tournament info. |

### 8.4 The 3,665 Match Cleanup Incident (v2.1.0)

In v2.1.0, a data quality incident required deleting 3,665 corrupted match records. The root cause was the surface detection bug where the string `"halle"` (Halle Open, a grass tournament) was matching inside the word `"challenger"`, causing widespread surface misclassification.

**Resolution:**
1. Centralized all surface detection into `config.py` (`get_tournament_surface()`)
2. Implemented word boundary matching (`\b` regex) for short tournament keywords
3. Added grass season check (only June-July)
4. Deleted and re-imported affected match records

### 8.5 Data Quality Checks for Bet Placement

The `check_data_quality_for_stake()` function in `config.py` performs live quality checks before bets are placed:

1. **Minimum recent matches:** For standard stakes, both players need 3+ matches in last 60 days. For high stakes (2u+), both need 5+.
2. **Tennis Explorer verification:** If database shows insufficient matches, the system checks Tennis Explorer live to verify. If TE shows enough matches, the bet passes (stale database).
3. **Form comparison for high stakes:** If the selection's year-to-date win rate is 15%+ worse than the opponent's, the bet is BLOCKED.
4. **Stake reduction:** If TE shows insufficient matches but the player has played this month, the bet is allowed at 50% reduced stake.

---

## 9. Data Flow Diagrams

### 9.1 Betfair Odds Capture Flow

```
Betfair Exchange API                    System                         Database
       |                                  |                              |
       |  POST /api/login                 |                              |
       |<---------------------------------|                              |
       |  {token: "..."}                  |                              |
       |--------------------------------->|                              |
       |                                  |                              |
       |  POST /listMarketCatalogue      |                              |
       |  (Tennis, MATCH_ODDS, 48h)       |                              |
       |<---------------------------------|                              |
       |  [{marketId, runners, comp}...]  |                              |
       |--------------------------------->|                              |
       |                                  |                              |
       |                                  |  Filter: 2 runners,         |
       |                                  |  no doubles, no in-play     |
       |                                  |                              |
       |  POST /listMarketBook           |                              |
       |  (40 markets per batch)          |                              |
       |<---------------------------------|                              |
       |  [{odds, liquidity, status}...]  |  sleep(0.2) between batches |
       |--------------------------------->|                              |
       |                                  |                              |
       |                                  |  For each match:            |
       |                                  |    - Detect surface         |
       |                                  |    - Match player names     |
       |                                  |    - Normalize tournament   |
       |                                  |                              |
       |                                  |  INSERT/UPDATE              |
       |                                  |  upcoming_matches            |
       |                                  |------------------------------>|
       |                                  |                              |
       |                                  |  Update closing odds        |
       |                                  |  for pending bets           |
       |                                  |------------------------------>|
```

### 9.2 Tennis Explorer Import Flow

```
Tennis Explorer                         System                         Database
       |                                  |                              |
       |                                  |  Load PlayerNameMatcher     |
       |                                  |<-----------------------------|
       |                                  |  {3100 players indexed}     |
       |                                  |                              |
       |  GET /results/?type=atp-single  |                              |
       |  &year=2026&month=01&day=31      |                              |
       |<---------------------------------|                              |
       |  <html>match rows</html>         |                              |
       |--------------------------------->|  sleep(0.3)                 |
       |                                  |                              |
       |  ... repeat for each day ...     |                              |
       |  ... repeat for WTA, ITF ...     |                              |
       |                                  |                              |
       |                                  |  For each match:            |
       |                                  |    - find_player_id(winner) |
       |                                  |    - find_player_id(loser)  |
       |                                  |    - Duplicate check (3d)   |
       |                                  |    - Validate (data_validation)|
       |                                  |                              |
       |                                  |  INSERT OR IGNORE matches   |
       |                                  |------------------------------>|
       |                                  |  ID: TE_{date}_{w_id}_{l_id}|
```

### 9.3 Tennis Ratio Stats Flow

```
Tennis Ratio                            System                         Database
       |                                  |                              |
       |                                  |  Get upcoming matches       |
       |                                  |<-----------------------------|
       |                                  |  Collect unique player IDs  |
       |                                  |                              |
       |                                  |  For each player:           |
       |                                  |    Check TTL (7 days)       |
       |                                  |<-----------------------------|
       |                                  |                              |
       |  GET /players/CarlosAlcaraz.html |                              |
       |<---------------------------------|                              |
       |  <html>window.playerData={...}   |                              |
       |--------------------------------->|  sleep(1.0)                 |
       |                                  |                              |
       |                                  |  Extract 13 serve metrics   |
       |                                  |  from window.playerData.ovr |
       |                                  |                              |
       |                                  |  UPSERT player_serve_stats  |
       |                                  |  source='tennis_ratio'      |
       |                                  |------------------------------>|
       |                                  |                              |
       |  If not found:                   |                              |
       |  GET /players/AlcarazCarlos.html |  (reversed name attempt)    |
       |<---------------------------------|                              |
       |  <html> NO window.playerData     |                              |
       |--------------------------------->|                              |
       |                                  |                              |
       |                                  |  UPSERT empty stats         |
       |                                  |  source='tennis_ratio_not_found'|
       |                                  |------------------------------>|
```

### 9.4 Complete Data Flow Overview

```
+------------------+     +------------------+     +------------------+
|   Betfair API    |     | Tennis Explorer   |     |  Tennis Ratio    |
|  (Authenticated) |     |   (Scraping)     |     |   (Scraping)    |
+--------+---------+     +--------+---------+     +--------+---------+
         |                         |                        |
         | Odds, Liquidity,       | Match Results,         | 13 Serve/
         | Market Status          | Player Profiles,       | Return Metrics
         |                         | Rankings              |
         v                         v                        v
+--------+---------+     +--------+---------+     +--------+---------+
| Surface Detection|     | PlayerName       |     | Name->PascalCase |
| (config.py)      |     | Matcher          |     | URL Builder      |
+--------+---------+     | (6 strategies)   |     +--------+---------+
         |                +--------+---------+              |
         |                         |                        |
         v                         v                        v
+--------+-------------------------+------------------------+---------+
|                        SQLite Database                               |
|  +----------------+  +----------------+  +------------------------+  |
|  |upcoming_matches|  |    matches     |  | player_serve_stats     |  |
|  | (live odds)    |  | (65K+ history) |  | (13 metrics/player)   |  |
|  +----------------+  +----------------+  +------------------------+  |
|  +----------------+  +----------------+  +------------------------+  |
|  |    players     |  |     bets       |  |   match_analyses       |  |
|  | (3100+ ranked) |  | (tracked P/L)  |  | (analysis log)        |  |
|  +----------------+  +----------------+  +------------------------+  |
|  +----------------+  +----------------+  +------------------------+  |
|  | player_surface |  |  head_to_head  |  | rankings_history       |  |
|  |   _stats       |  |                |  |                        |  |
|  +----------------+  +----------------+  +------------------------+  |
+----------------------------------------------------------------------+
         |                    |                        |
         v                    v                        v
+--------+---------+  +------+-------+  +-------------+---------+
|  Match Analyzer  |  | Bet Tracker  |  | Discord Notifications |
|  (8 factors +    |  | (P/L, CLV)   |  | (webhooks + bot)     |
|  2 edge mods)    |  +--------------+  +-----------------------+
+------------------+
```

**Note:** The Match Analyzer uses 8 weighted factors (surface 22%, form 20%, fatigue 17%, ranking 13%, perf_elo 13%, recent_loss 8%, h2h 5%, momentum 2%) plus 2 post-probability edge modifiers (Serve Edge up to -20%, Activity Edge up to -40%).

---

## 10. Error Handling by Source

### 10.1 Betfair Exchange API

| Error Condition | Detection | Response | Retry | Degraded Mode |
|----------------|-----------|----------|-------|---------------|
| Login failure (wrong credentials) | `result.status != 'SUCCESS'` | Print error, return empty list | No automatic retry; user must fix credentials | No capture, system runs without fresh odds |
| Login failure (network) | `requests` exception | Print error with traceback | No automatic retry; next cycle will retry | Same as above |
| Non-JSON response | Content-Type check | Print "Unexpected content type" | No | Same as above |
| API error (non-200) | `response.status_code != 200` | Print status code and body | No; that market batch skipped | Other batches still processed |
| Market with < 2 runners | `len(runners) != 2` | Skip silently | N/A | Other matches still captured |
| Session expiry | API returns auth error | Next capture cycle triggers fresh login | Yes (implicit) | Current cycle's remaining markets fail |
| Rate limit exceeded | Betfair returns 429 or error | Not explicitly handled | 200ms delay should prevent this | N/A |

### 10.2 Tennis Explorer

| Error Condition | Detection | Response | Retry | Degraded Mode |
|----------------|-----------|----------|-------|---------------|
| HTTP error (non-200) | `response.status_code != 200` | Print "Failed to fetch results: {code}" | No per-page retry; continues to next page | Partial data imported |
| Network timeout | `requests` exception (15s/30s timeout) | Print error, return empty list for that page | No | Other pages still fetched |
| HTML parse failure | BeautifulSoup exceptions | Skip affected row/match | N/A | Other matches on page still parsed |
| Player not found in search | No matching `<a href="/player/">` links | Return `None` for slug | N/A | Player profile not fetched |
| Name match failure | `find_player_id()` returns `None` | Match skipped (players locked) | N/A | Match not imported; logged in first 20 failures |
| Duplicate match detected | SQL query finds same players within 3 days | Skip via `INSERT OR IGNORE` | N/A | Existing data preserved |

### 10.3 Tennis Ratio

| Error Condition | Detection | Response | Retry | Degraded Mode |
|----------------|-----------|----------|-------|---------------|
| HTTP 404 | `response.status_code == 404` | Return `None` | No | Empty stats cached |
| HTTP 200 but generic page | `'window.playerData' not in response.text` | Return `None` | No; tries reversed name first | Empty stats cached with `source='tennis_ratio_not_found'` |
| JSON parse failure | `json.JSONDecodeError` | Log warning, return `None` | No | Empty stats cached |
| Network error | `requests.RequestException` | Log warning, return `None` | No | Player skipped; `failed` count incremented |
| All stats `None` | `all(v is None for v in stats.values())` | Return `None` | N/A | Empty stats cached |
| Request timeout | 15-second timeout | `RequestException` raised | No | Same as network error |

### 10.4 Data Validation

| Error Condition | Detection | Response |
|----------------|-----------|----------|
| `winner_id == loser_id` | Equality check | Match rejected, logged to CSV |
| Invalid player ID (None/0) | Null/zero check | Match rejected, logged to CSV |
| Invalid date format | `datetime.strptime` failure | Match rejected, logged to CSV |
| Future date (7+ days) | Date comparison | Match rejected, logged to CSV |
| Invalid score format | Regex check for set pattern | Warning logged, match still accepted |
| Missing tournament name | Empty string check | Warning logged, match still accepted |
| Missing surface | Empty string check | Warning logged, match still accepted |

---

## 11. Monitoring and Alerts

### 11.1 Discord Notifications

The system sends Discord notifications via webhooks and a dedicated Discord bot for real-time monitoring.

**Notification types:**

| Event | Color | Content |
|-------|-------|---------|
| New bet placed | Green | Match, selection, odds, stake, model, factor scores |
| Bet won | Green | Match, selection, odds, profit, CLV |
| Bet lost | Red | Match, selection, odds, loss amount, CLV |
| Bet void | Gray | Match, selection, reason |
| Match goes in-play | Blue | Match, selection, current odds |

**CLV tracking in alerts:** Since v2.61, Discord alerts include closing odds and CLV percentage when available, showing whether the placement odds were better than the closing line.

### 11.2 Discord Bot Commands

The Discord bot runs in the local monitor (`local_monitor.py`) and provides interactive commands:

| Command | Description | Data Source |
|---------|-------------|-------------|
| `!inplay` | Currently live bets | Supabase `bets` where `is_live=True` |
| `!pending` | All pending bets | Supabase `bets` where `result IS NULL` |
| `!stats` | Overall statistics (P/L, ROI, W/L by model) | Supabase `bets` aggregate |
| `!refresh` | Force check all pending bets against Betfair + settle finished | Betfair API + local DB |
| `!alert` | Manual alert trigger | Local DB |
| `!resend` | Re-send most recent result alert | Local DB + Discord webhook |

### 11.3 Local Monitor Loop

The local monitor (`local_monitor.py`) runs a continuous loop:

1. Every 30 seconds:
   - Fetch pending bets from Supabase
   - For each bet, check Betfair market status
   - Detect transitions: not-live to in-play (send LIVE alert)
   - Detect settled markets: determine winner from Betfair runner status
   - Send WIN/LOSS alerts
   - Update Supabase and local DB

### 11.4 Logging

| Log Type | Location | Content |
|----------|----------|---------|
| **Validation failures** | `logs/data_validation.csv` | All rejected/warned match data with rule violated, severity, full match details |
| **Match analyses** | `match_analyses` table | Every analyzed match: probabilities, factor scores, edge, model qualification, bet outcome |
| **Console output** | stdout | Real-time capture progress, low liquidity warnings, Pinnacle comparisons, name match failures |
| **Application logs** | Python logging (Tennis Ratio) | HTTP errors, parse failures, TTL skip decisions |

### 11.5 Data Quality Monitoring

The system surfaces data quality issues through:

1. **Capture summary:** After each Betfair capture, a summary is printed:
   ```
   --- CAPTURE SUMMARY ---
   Total markets found: 156
   Captured: 142
   Skipped - In-play: 8
   Skipped - No odds: 4
   Skipped - Other (doubles, filter, etc.): 2
   -----------------------
   ```

2. **Name match failure reporting:** During Tennis Explorer imports, the first 10-20 unmatched names are reported for manual review.

3. **Tennis Ratio failure logging:** Players without Tennis Ratio profiles are logged at INFO level with a summary count.

4. **Bet placement data quality gate:** The `check_data_quality_for_stake()` function blocks or reduces bets when data quality is insufficient, with detailed warning messages explaining why.

5. **Match analysis logging:** Every analyzed match is stored in `match_analyses` with full factor breakdown, enabling post-hoc analysis of model accuracy and data completeness.

### 11.6 Database Statistics (Current)

| Table | Approximate Count | Notes |
|-------|-------------------|-------|
| `players` | ~3,100 | Ranked ATP/WTA/Challenger/ITF players |
| `matches` | ~65,000 | Historical match records |
| `upcoming_matches` | Variable (50-200) | Active pre-match markets |
| `bets` | Growing | All tracked bets with P/L |
| `player_serve_stats` | Growing | One row per player with Tennis Ratio data |
| `match_analyses` | Growing | One row per analyzed match |
| Total tables | 16 | Full schema in `database.py` |

---

## Appendix A: Database Schema Summary

### Core Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `players` | Player master data | `id`, `name`, `country`, `hand`, `height`, `dob`, `current_ranking`, `performance_elo`, `tour` |
| `matches` | Historical match results | `id`, `tournament`, `date`, `surface`, `winner_id`, `loser_id`, `score`, 18 match stat columns |
| `tournaments` | Tournament reference data | `id`, `name`, `surface`, `category` |
| `upcoming_matches` | Active Betfair markets | `tournament`, `date`, `surface`, `player1/2_id/name/odds/liquidity` |
| `bets` | Bet tracking | `match_date`, `tournament`, `selection`, `stake`, `odds`, `our_probability`, `result`, `profit_loss`, `odds_at_close`, `clv`, `model` |

### Supporting Tables

| Table | Purpose |
|-------|---------|
| `rankings_history` | Historical ranking snapshots |
| `player_surface_stats` | Aggregated surface win/loss records |
| `head_to_head` | H2H records between player pairs |
| `injuries` | Player injury tracking |
| `player_aliases` | Maps alternate IDs to canonical IDs |
| `player_serve_stats` | Tennis Ratio serve/return metrics (13 columns) |
| `match_analyses` | Full analysis log for every match analyzed |
| `betfair_matches` | Raw Betfair capture data |
| `app_settings` | Key-value store for app metadata |

---

## Appendix B: Configuration Constants

### Betfair Constants (betfair_capture.py)

```python
BETFAIR_LOGIN_URL = "https://identitysso.betfair.com/api/login"
BETFAIR_API_URL = "https://api.betfair.com/exchange/betting/rest/v1.0/"
BETFAIR_KEEP_ALIVE_URL = "https://identitysso.betfair.com/api/keepAlive"
TENNIS_EVENT_TYPE_ID = "2"
MATCH_ODDS_MARKET = "MATCH_ODDS"
MIN_LIQUIDITY_GBP = 0          # Capture all matches regardless of liquidity
MAX_ODDS_DISCREPANCY = 1.0     # Effectively disabled (100%)
```

### Scraper Settings (config.py)

```python
SCRAPER_SETTINGS = {
    "atp_rankings_pages": 15,   # 100 players per page = 1500 ATP players
    "wta_rankings_pages": 15,   # 100 players per page = 1500 WTA players
    "match_history_months": 12, # Months of match history to scrape per player
}
```

### Tennis Ratio Constants (tennis_ratio_scraper.py)

```python
BASE_URL = "https://www.tennisratio.com/players/"
REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
```

### Kelly Staking (config.py)

```python
KELLY_STAKING = {
    "exchange_commission": 0.02,  # 2% Betfair commission
    "kelly_fraction": 0.375,      # 37.5% Kelly
    "m1_boost": 1.50,             # M1 (Triple Confirmation) gets 1.5x stake
    "no_data_multiplier": 0.50,   # 50% stake when missing serve/activity data
    "min_odds": 1.70,             # Minimum odds floor
    "min_units": 0.25,            # Minimum bet size
    "max_units": 3.0,             # Maximum bet size
}

PROBABILITY_CALIBRATION = {
    "enabled": True,              # Calibration is now ENABLED
    "shrinkage_factor": 0.60,     # Pulls probabilities toward 50%
    "mode": "asymmetric",         # Only applies to favorites
}

MARKET_BLEND = {
    "enabled": True,              # Market blend is now ENABLED
    "weight": 0.35,               # 35% market, 65% calibrated model
}
```

---

*End of DATA_SOURCES.md -- Tennis Betting System v3.1*
