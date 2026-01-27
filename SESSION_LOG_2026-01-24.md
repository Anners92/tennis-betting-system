# Session Log - 2026-01-24

## Session Status: ACTIVE

---

## Latest: Model Tracking Feature (Night Session #4)

### Overview
Added ability to track bets under two different models to compare performance:
- **Model 1**: All bets (baseline - current behavior)
- **Model 2**: Tiered strategy (extremes + filtered middle)

### Key Analysis Findings

**Performance by Probability Band (62 settled bets):**
| Band | Record | ROI |
|------|--------|-----|
| 30-40% | 2W-1L | +185% |
| 40-50% | 6W-16L | -18% |
| 50-55% | 2W-9L | -52% |
| 55-60% | 3W-9L | -38% |
| 60-65% | 2W-5L | -25% |
| 65-70% | 2W-2L | -4% |
| 70%+ | 3W-0L | +120% |

**Key Insight**: Model has edge at EXTREMES:
- 30-40% (longshot value): +185% ROI
- 70%+ (high confidence): +120% ROI
- Middle range (40-65%): Losing money

**Model 2 (Tiered Strategy) Rules:**
1. Tier 1 (Always bet): 30-40% OR 70%+ probability
2. Tier 2 (Filtered middle): 40-65% with:
   - NOT Challenger (they're efficient markets)
   - Edge < 15% (high disagreement = market is right)
3. Skip: 65-70% range (historically break-even)

**Results:**
| Strategy | Bets | P/L | ROI |
|----------|------|-----|-----|
| Model 1 (all bets) | 62 | -8.16u | -8.5% |
| Model 2 (tiered) | 26 | +6.26u | +16.7% |

### Files Modified

**src/config.py:**
- Added `calculate_bet_model(our_probability, implied_probability, tournament)` function
- Returns "Model 1" or "Model 1, Model 2" based on tiered rules

**src/database.py:**
- Added `model` column migration to bets table
- Updated `add_bet()` to include model field

**src/bet_tracker.py:**
- Added `calculate_bet_model` import
- Updated `add_bet()` to auto-calculate model
- Added `get_stats_by_model()` method
- Added "Performance by Model" section in Statistics tab
- Added "Model" column to All Bets table
- Updated `_refresh_bets_table()` to calculate model for existing bets

### UI Changes
- Statistics tab now shows Model 1 vs Model 2 comparison
- All Bets table has new "Model" column showing which model(s) each bet qualifies for
- **Model filter dropdown** in All Bets filter bar:
  - "All" - Shows all bets
  - "Model 1 Only" - Shows bets excluded from Model 2
  - "Model 2" - Shows only bets qualifying for Model 2 (tiered strategy)

### How It Works
When a bet is added:
1. System calculates `our_probability - implied_probability` = edge
2. Checks tournament type (Challenger or not)
3. Applies tiered rules to determine model qualification
4. Stores "Model 1" or "Model 1, Model 2" in database

All bets are Model 1 (baseline). Only qualifying bets are also Model 2.

### To Test
```bash
cd "tennis betting"
python src/main.py
```
Go to Bet Tracker > Statistics tab to see Model 1 vs Model 2 performance.

---

## Previous: Unified Installer for Sports Betting Hub (Night Session #3)

### Overview
Created a unified installer that packages all three components together:
1. Sports Betting Hub (Launcher)
2. Tennis Betting System (compiled .exe)
3. Football Betting Tool (Python source)

### Files Created

**installer_unified.iss:**
- Inno Setup script for unified installer
- Includes all three apps in one package
- Creates optional shortcuts for Tennis and Football directly
- Checks for Python (required for Football tool)
- Installs to `Program Files\Sports Betting Hub\`

**build_unified.py:**
- Build script that:
  - Builds the launcher with PyInstaller
  - Checks if Tennis is built
  - Checks if Football source exists
  - Runs Inno Setup to create installer

### Install Structure
```
Program Files\Sports Betting Hub\
├── SportsBettingHub.exe          # Main launcher
├── Tennis Betting System\        # Compiled Tennis app
│   └── TennisBettingSystem.exe
└── Football Betting Tool\        # Football source
    └── src\
        └── main.py
```

### Updated launcher.py
- Path resolution now checks unified install location first
- Handles both .exe files (Tennis) and .py files (Football)
- Falls back to development paths and standalone installs

### To Build
```bash
cd sports-betting-launcher
python build_unified.py
```

### Requirements
- Tennis must be built first (`tennis betting/dist/TennisBettingSystem/`)
- Inno Setup installed for creating installer
- Python required on user's machine for Football tool

---

## Football Betting Tool UI Complete Redesign (Night Session #2)

### Overview
Completely redesigned the Football Betting Tool to **exactly match** the Tennis Betting System's UI style, not just colors.

### User Requirement
"The Football model needs to look exactly like the Tennis one. Yellow buttons, buttons on the bottom being minimal etc."

### Key Changes to main.py

**1. New ModernButton Class (Ghost/Outline Style)**
- Replaced filled rounded buttons with outline-style buttons
- Text shows in color, fills on hover
- Matching Tennis system exactly

**2. Feature Cards Redesigned**
- **Removed** colored accent bars at top of each card
- **Changed** all "Open" buttons to **yellow** (`#eab308`)
- Added subtle border (`#334155`) that glows on hover
- Cards are now clickable anywhere

**3. Stats Section Updated**
- Letter-spaced uppercase labels (matching Tennis)
- Consistent card height with borders
- ROI color-coded (green positive, red negative)

**4. Quick Actions (Bottom Buttons)**
- All buttons now use outline/ghost style
- Muted gray for utility buttons (`#64748b`)
- Warning amber for "Update Data"
- Primary blue for "Scheduler"

**5. Footer Updated**
- League pills with colored backgrounds (like Tennis surface pills)
- Season and data source info on right

### Files Modified

**main.py** - Complete rewrite:
- New `ModernButton` class (tk.Frame based, outline style)
- `_create_feature_card()` - no accent bars, yellow buttons
- `_create_stats_section()` - letter-spaced labels, borders
- `_create_quick_actions()` - outline style buttons
- `_create_footer()` - colored league pills

**config.py:**
- Added `UI_COLORS` dictionary

**bet_suggester.py, bet_tracker.py, dashboard.py, player_database.py, quick_entry.py:**
- Updated to use `UI_COLORS` from config

### Visual Changes Summary
| Element | Before | After |
|---------|--------|-------|
| Feature buttons | Filled, multi-color | Yellow outline |
| Card accents | Colored bar at top | None |
| Bottom buttons | Filled colored | Outline style |
| Stats labels | Simple uppercase | Letter-spaced |
| League pills | Gray backgrounds | Colored (like Tennis surfaces) |

### Testing
All modules compile and import successfully.

---

## Volume-First Strategy & Shrinkage Calibration (Evening Session)

### User Requirement
"Bet on ALL levels of tennis. We need 1000 bets to decide things like 'don't bet challengers'. We want as many bets per day as possible."

### Problem Re-Analysis
With 60 settled bets:
- Model predicted 53.5% average win probability
- Actual win rate: 31.7%
- Model is ~1.7x overconfident

The previous polynomial calibration was **mathematically broken**:
- 40% input → 46% output (wrong direction!)
- 50% input → 50% output (no change)

### Solution: Shrinkage Calibration

Replaced broken polynomial with simple shrinkage toward 50%:

```python
# In match_analyzer.py find_value()
shrinkage_factor = 0.5
our_prob = 0.5 + (raw_model_prob - 0.5) * shrinkage_factor
```

**Results:**
| Raw Model | Calibrated |
|-----------|------------|
| 40% | 45% |
| 50% | 50% |
| 60% | 55% |
| 70% | 60% |
| 80% | 65% |

### Filters Removed for Volume

| Setting | Before | After | Why |
|---------|--------|-------|-----|
| min_ev_threshold | 10% | 2% | More bets |
| min_odds | 1.70 | 1.30 | Bet on more favorites |
| min_units | 0.5 | 0.25 | Smaller bets allowed |
| challenger_settings | Enabled | Disabled | No tour restrictions |
| odds_range_weighting | 0.5x penalty | 1.0x (no penalty) | All odds equal |
| disagreement.major | Block (0.0) | 50% stake | Still bet |

### Files Modified
- `src/config.py` - All filter settings relaxed
- `src/match_analyzer.py` - Shrinkage calibration added
- `CLAUDE.md` - Added "Betting Philosophy Rules" section
- `dist/TennisBettingSystem/` - Both files synced

### Expected Impact
- **More bets per day** - All restrictive filters removed
- **More accurate EV** - Shrinkage reduces false positives
- **Better data** - 1000+ bets will allow proper statistical analysis

---

---

## Latest: Weight Profile Backtesting (Night Session #5)

### Overview
Added ability to test different factor weight configurations against historical bets. Users can now compare how different strategies would have performed.

### Weight Profiles Added
| Profile | Form | Surface | Ranking | H2H | Other |
|---------|------|---------|---------|-----|-------|
| Current (Balanced) | 20% | 15% | 20% | 10% | 35% |
| Form Heavy | 35% | 10% | 15% | 10% | 30% |
| Ranking Heavy | 15% | 10% | 35% | 10% | 30% |
| Surface Specialist | 15% | 30% | 15% | 10% | 30% |
| H2H Focus | 15% | 10% | 15% | 30% | 30% |
| Recent Form Only | 40% | 10% | 10% | 5% | 35% |

### Files Modified

**src/config.py:**
- Added `MODEL_WEIGHT_PROFILES` dictionary with 6 different weight configurations

**src/database.py:**
- Added `factor_scores` column migration to bets table (stores JSON)
- Updated `add_bet()` to include factor_scores field
- Added `get_settled_bets_for_backtest()` method

**src/bet_tracker.py:**
- Added import for `MODEL_WEIGHT_PROFILES` and `json`
- Added Backtest tab to notebook
- Added `_build_backtest_tab()` method with:
  - Weight profiles display table
  - Run Backtest button
  - Results table showing performance per profile
- Added `_run_backtest()` method to simulate all profiles
- Added `_calculate_probability_from_factors()` to recalculate probabilities

### How It Works
1. Go to Bet Tracker > Backtest tab
2. Click "Run Backtest" to analyze all settled bets
3. See how each weight profile would have performed
4. Best performer is highlighted in green/bold

**Note:** Existing bets don't have stored factor scores, so they're approximated.
New bets going forward will store factor scores for accurate backtesting.

### Factor Score Storage (Now Enabled)
Updated bet_suggester.py to store factor scores when adding bets:
- Extracts factor advantages from analysis
- Converts to 0-1 scale (0.5 = neutral, >0.5 = favors our selection)
- Stores as JSON in `factor_scores` column
- New bets will have full backtest support

**src/bet_suggester.py changes:**
- Added `analysis` to bet_data dictionary when building current_value_bets
- Updated `_add_all_to_tracker` to extract and store factor scores
- Factor scores are perspective-adjusted (flipped for P2 bets)

### Edit Bet Dialog Enhancement
Added factor information panel to the edit bet dialog (double-click a bet):
- Dialog now 900px wide (was 500px)
- Left side: existing edit form
- Right side: new "Bet Analysis" panel showing:
  - Our Probability, Market Implied, Edge, EV
  - Factor Breakdown with visual progress bars
  - Model designation (Model 1/2)

**src/bet_tracker.py changes:**
- Added `_build_factor_panel()` method
- Updated `_edit_bet_dialog()` to include right panel

---

---

## Latest: Model 3 + Model Display in Analysis (Night Session #6)

### Overview
- Added **Model 3 (Sharp)** - a new betting model with different factor weightings
- Added **model qualification display** during match analysis so you can see which models each bet qualifies for BEFORE adding it to tracker

### Model 3 Definition
| Factor | Current (Balanced) | Model 3 (Sharp) |
|--------|-------------------|-----------------|
| Form | 20% | 25% |
| Surface | 15% | 10% |
| Ranking | 20% | 10% (de-emphasized) |
| H2H | 10% | 10% |
| Fatigue | 5% | 5% |
| Injury | 5% | 5% |
| Opponent Quality | 10% | 15% (emphasized) |
| Recency | 8% | 10% (emphasized) |
| Recent Loss | 5% | 5% |
| Momentum | 2% | 5% |

**Model 3 criteria:** Edge between 5-15% (moderate disagreement zone where sharp analysis matters)

Rationale: De-emphasize ranking (market already prices this) and emphasize opponent quality + recent form (market may not fully account for these).

### Files Modified

**src/config.py:**
- Added "Model 3 (Sharp)" to `MODEL_WEIGHT_PROFILES`
- Updated `calculate_bet_model()` to include Model 3 criteria (5-15% edge)

**src/bet_tracker.py:**
- Updated `get_stats_by_model()` to track Model 3 separately
- Updated model filter dropdown: ["All", "Model 1 Only", "Model 2", "Model 3"]
- Updated filter logic to handle Model 3

**src/bet_suggester.py:**
- Added `calculate_bet_model` import
- Added "Models" column to value bets table showing which models (1, 2, 3) each bet qualifies for
- Added model display to value bet cards with color coding (green if Model 2/3, gray otherwise)
- Added `tournament` and `implied_prob` fields to bet_data for model calculation

### How It Works in Analysis
When you run "Find Value Bets":
1. **Table view:** New "Models" column shows "1", "1, 2", "1, 3", or "1, 2, 3"
2. **Card view:** Shows "Models: Model 1, Model 2, Model 3" with color coding

This lets you see at a glance which bets meet the stricter Model 2/3 criteria before adding them.

### To Test
1. Open app and go to Match Analysis
2. Run "Find Value Bets" on any match set
3. Look for the new "Models" column in the table
4. Click on a bet card to see full model qualification in the details

---

## Next Steps

1. **Gather more data** - Need 200+ bets to validate Model 2/3 performance
2. **Consider form confirmation filter** - Only bet middle range when selection has clearly better form
3. **Monitor Challenger performance** - User wants to keep betting them to find edge
4. **Rebuild exe** - If deploying compiled version with model tracking

---

## Repository
- **Local:** `C:\Users\marca\OneDrive\Documents\claude-playground\tennis betting`
- **Run:** `python src/main.py`
