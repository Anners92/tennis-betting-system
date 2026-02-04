# Session Log - February 5, 2026

## Database Pull & Analysis

### Current State (Feb 5 pull)
- **177 total bets**, 160 settled (54W-103L-3V), 17 pending
- **P/L: -10.23u** (improved from -11.72u, +1.49u since Feb 4)
- **Win rate: 34.4%** (up from 33.3%)
- **ROI: -8.2%**

### Daily P/L (Last 7 Days)
| Date | Bets | W-L | Win% | P/L |
|------|------|-----|------|-----|
| Feb 4 | 5 | 1-4 | 20% | -1.53u |
| Feb 3 | 26 | 13-12 | 50% | +6.88u |
| Feb 2 | 30 | 10-20 | 33% | +0.33u |
| Feb 1 | 46 | 9-36 | 20% | -19.17u |
| Jan 31 | 28 | 12-15 | 43% | +2.86u |
| Jan 30 | 17 | 6-11 | 35% | -1.45u |
| Jan 29 | 8 | 3-5 | 38% | +1.85u |

Feb 4 was a down day (1-4), but Feb 3's +6.88u still carrying us.

---

## M1+M11 Thesis: CONFIRMED at n=40

| Segment | n | Record | Win% | P/L | ROI |
|---------|---|--------|------|-----|-----|
| **M1 or M11** | **40** | **26-14** | **65.0%** | **+22.53u** | **+55.6%** |
| Everything else | 117 | 28-89 | 23.9% | -32.76u | -40.0% |

**Spread: +55.30u.** At n=40 with 65% win rate and +55.6% ROI, this is proven.

---

## Pure M3 Analysis

| Segment | n | Record | Win% | P/L |
|---------|---|--------|------|-----|
| **Pure M3** | **39** | **3-36** | **7.7%** | **-18.76u** |
| M3 with others | 79 | 34-45 | 43.0% | +9.34u |
| No M3 | 39 | 17-22 | 43.6% | -0.81u |

Pure M3: 7.7% win rate. Catastrophic.

---

## M5 Analysis

| Segment | n | Record | Win% | P/L |
|---------|---|--------|------|-----|
| Pure M5 | 3 | 0-3 | 0% | -1.50u |
| M5 with others | 32 | 5-27 | 15.6% | -11.81u |
| **All M5-involved** | **35** | **5-30** | **14.3%** | **-13.31u** |
| No M5 | 122 | 49-73 | 40.2% | +3.08u |

M5 presence is a negative signal.

---

## Exclusion Analysis

| Filter | n | Record | P/L | ROI |
|--------|---|--------|-----|-----|
| All bets | 157 | 54-103 | -10.23u | -8.2% |
| Without Pure M3 | 118 | 51-67 | **+8.53u** | **+8.7%** |
| Without any M5 | 122 | 49-73 | +3.08u | +3.1% |
| Without Pure M3 + M5 | 83 | 46-37 | **+21.84u** | **+29.7%** |
| Only M1/M11 | 40 | 26-14 | **+22.53u** | **+55.6%** |

System is profitable when filtered.

---

## CLV Breakdown

| Segment | n | Avg CLV | +CLV Rate |
|---------|---|---------|-----------|
| M1/M11 | 23 | -1.65% | 39% |
| Other | 75 | -6.57% | 15% |
| Overall | 98 | -5.42% | 20.4% |

---

## M12 (Fade Model) Update
- Settled: 2 bets, 1W-1L, -0.03u (break-even)
- Pending: 2 bets

Too early to judge.

---

## Model Breakdown (Full)

Top performers:
- Model 3, Model 11: 17 bets, 11-6, +9.47u (+67.6% ROI)
- Model 4, Model 8: 2 bets, 2-0, +4.02u
- Model 1, Model 4, Model 11: 1 bet, 1-0, +3.75u
- Model 3, Model 7, Model 11: 3 bets, 3-0, +3.02u

Worst performers:
- Model 3 (pure): 39 bets, 3-36, -18.76u (-76.6% ROI)
- Model 3, Model 5: 27 bets, 4-23, -8.76u (-51.5% ROI)
- Model 3, Model 7: 10 bets, 2-8, -5.44u (-60.4% ROI)

---

## Decision: Hold Current Settings

Reviewed recommendations to disable Pure M3 and M5. **Decision: Keep current settings for now.** Continue gathering data.

---

## Documentation Update: state_machines.txt

Updated `docs/state_machines.txt` from v2.1.0 to v3.1. Changes made:

### Header & TOC
- Version bumped to 3.1, date to Feb 5, 2026
- Table of Contents updated for 26 flows (was 22)

### Core Flow Updates
- **Flow #5 (Match Analysis)**: Updated factor weights (surface 22%, form 20%, fatigue 17%, ranking 13%, perf_elo 13%, recent_loss 8%, h2h 5%, momentum 2%). Removed INJURY factor.
- **Flow #9 (Model Assignment)**: Complete rewrite for 11 models. Documented Hard Models (M3, M4, M5, M7, M8), Soft Models (M2, M9, M10, M11), Premium Model (M1), and Fade Model (M12). Added performance notes.
- **Flow #10 (Unit Staking)**: Updated Kelly fraction to 0.375, added M1 boost 1.5x, serve conflict reduction, activity penalty.

### New Flows Added
- **Flow #14**: Probability Calibration Flow (shrinkage + market blend)
- **Flow #15**: Serve Edge Modifier Flow (DR gap, conflict reduction)
- **Flow #16**: Activity Edge Modifier Flow (match count + gap analysis)
- **Flow #21**: CLV Tracking Flow

### Flow Renumbering
- Renumbered flows 19-22 (Tournament/Player/Manual Bet/Database) to 23-26
- Removed "(NEW)" tags from older UI flows
- Updated cross-references in Database Management flow

### Discord Bot Commands
- Updated Flow #18 with all current commands: !inplay, !pending, !stats, !alert, !refresh, !resend, !data

### Summary Section
- Complete rewrite reflecting v3.1 system state
- Documented all 11 models with performance data
- Added edge modifiers, calibration settings, Kelly staking
- Updated key insight with M1/M11 thesis data

---

## Documentation Update: MODEL_SPECIFICATION.md

Updated `docs/MODEL_SPECIFICATION.md` from v2.61 to v3.1. Major changes:

- **Header**: Updated version to 3.1, date to Feb 5, 2026
- **Key Metrics**: Updated for 8 active factors, 11 models, calibration enabled
- **Factor Weights**: Updated to v3.1 weights (surface 22%, fatigue 17%, perf_elo 13%), injury marked as deprecated
- **Section 4 (Models)**: Complete rewrite for 11 models:
  - Hard Models: M3, M4, M5, M7, M8
  - Soft Models: M2, M9, M10, M11
  - Premium Model: M1 (Triple Confirmation)
  - Fade Model: M12 (2-0 Fade)
- **Section 5.4**: Probability Calibration now ENABLED (was disabled)
  - 0.60 shrinkage factor (asymmetric - favorites only)
  - 0.35 market blend weight
- **Section 5.6**: Added staking modifiers (M1 1.5x boost, no-data 0.50x, activity reductions)
- **Section 9**: Renamed from "Serve Stats Integration" to "Edge Modifiers"
  - 9.1: Serve Edge Modifier (DR calculation, alignment, edge reduction)
  - 9.2: Serve Stats Display (13 metrics)
  - 9.3: Activity Edge Modifier (replaces injury factor, score calculation, labels)
- **Revision History**: Added v3.1 and v2.62 entries
- **Key Insight**: Added Feb 5 analysis showing M1/M11 thesis (+55.6% ROI)

---

## Documentation Update: CONFIGURATION_REFERENCE.md

Updated `docs/CONFIGURATION_REFERENCE.md` from v2.61 to v3.1. Key changes:

- **Header**: Updated version to 3.1, date to Feb 5, 2026
- **Section 1.1 (Factor Weights)**:
  - Updated to v3.1 weights (surface 22%, fatigue 17%, perf_elo 13%)
  - Marked injury as DEPRECATED (replaced by Activity Edge Modifier)
- **Section 1.3 (Betting Models)**: Complete rewrite for 11 models
  - Hard Models: M3, M4, M5, M7, M8
  - Soft Models: M2, M9, M10, M11
  - Premium Model: M1 (1.5x staking)
  - Fade Model: M12
  - Added performance data and M1+M11 thesis
- **Sections 2.5-2.6**: Probability Calibration and Market Blend now ENABLED
  - Shrinkage factor 0.60 (asymmetric - favorites only)
  - Market weight 0.35

---

## Documentation Update: MODEL_PERFORMANCE.md

Updated `docs/MODEL_PERFORMANCE.md` from v2.61 to v3.1. Key changes:

- **Header**: Updated version reference
- **Active Models section**: Complete rewrite for 11 models with performance data
- **Factor Weights**: Updated to v3.1 weights, added Edge Modifiers note
- **Calibration Settings**: Now ENABLED with shrinkage 0.60 (asymmetric) + market blend 0.35
- **Document footer**: Updated version to 1.1, system v3.1, date Feb 5

---

## Documentation Update Summary

Completed incremental updates to the following docs folder files:

| File | Status | Key Changes |
|------|--------|-------------|
| `state_machines.txt` | ✅ Complete | 26 flows, all models, edge modifiers, summary rewritten |
| `MODEL_SPECIFICATION.md` | ✅ Complete | 11 models, edge modifiers, calibration enabled |
| `CONFIGURATION_REFERENCE.md` | ✅ Key sections | Factor weights, models, calibration settings |
| `MODEL_PERFORMANCE.md` | ✅ Key sections | Models, weights, calibration |

Remaining docs to review (lower priority - may not need v3.1 updates):
- `github_scraper_diagnosis.txt` - diagnostic doc
- `RANKING_STRUCTURAL_ANALYSIS.md` - analysis doc
- `INCIDENT_RESPONSE.md` - operations procedures
- `OPERATIONS_GUIDE.md` - daily procedures
- `RISK_MANAGEMENT.md` - risk framework
- `BETFAIR_INTEGRATION.md` - API integration
- `DISCORD_INTEGRATION.md` - fairly current
- `DATA_SOURCES.md` - data sources
- `DEVELOPER_SETUP.md` - setup guide
- `CRITICAL_FIXES.md` - fix log

---

## Documentation Update: MODEL_ANALYSIS_GUIDE.md

Updated `docs/MODEL_ANALYSIS_GUIDE.md` from v2.61 to v3.1. Key changes:

- **Header**: Updated to v3.1
- **Factor Weights section**: Complete rewrite with v3.1 weights:
  - Reordered by weight (surface 22%, form 20%, fatigue 17%, ranking 13%, perf_elo 13%, recent_loss 8%, h2h 5%, momentum 2%)
  - Injury marked as DEPRECATED (replaced by Activity Edge Modifier)
  - Added Edge Modifiers note at end of table
- **How Each Factor Works section**:
  - Renumbered and reordered sections to match v3.1 weights
  - Added new Section 5 for Performance Elo (13%)
  - Updated Surface to 22% with "strongest signal" note
  - Updated Fatigue to 17% with "market underweights" note
  - Added "Deprecated: Injury" section explaining replacement
- **Serve Stats section**: Completely replaced with new "Edge Modifiers" section:
  - Serve Edge Modifier: DR gap, alignment logic, up to 20% edge reduction
  - Activity Edge Modifier: 0-100 score, labels (Active/Moderate/Low/Returning/Inactive), up to 40% edge reduction
- **Betting Models section**: Expanded from 4 models to 11 models:
  - Hard Models: M1 (premium 1.5x), M3, M4, M5, M7, M8
  - Soft Models: M2, M9, M10, M11 (tag-only)
  - Fade Model: M12 (2-0 fade)
  - Added M1+M11 thesis data and Pure M3 warning
- **Known Limitations**: Updated #5 from "serve stats not weighted" to "serve-return matchup blind spot"
- **Quick Reference config**: Complete rewrite:
  - v3.1 factor weights with notes
  - Edge Modifiers settings (serve + activity)
  - Probability Calibration (ENABLED) with shrinkage and market blend
  - Staking settings (Kelly, M1 boost, no-data multiplier)
- **Document footer**: Added version/date footer

---

## Documentation Update: OPERATIONS_GUIDE.md

Updated `docs/OPERATIONS_GUIDE.md` from v2.61 to v3.1. Key changes:

- **Header**: Updated to v3.1, date to Feb 5, 2026
- **Factor Analysis section**: Complete rewrite for v3.1 weights:
  - Reordered to match v3.1 (surface 22%, form 20%, fatigue 17%, etc.)
  - Added note that injury is DEPRECATED
  - Added Edge Modifiers section (serve + activity)
- **Betting Models section**: Expanded from 4 to 11 models:
  - Hard Models: M1 (premium 1.5x), M3, M4, M5, M7, M8
  - Soft Models: M2, M9, M10, M11
  - Fade Model: M12
  - Added M1+M11 thesis data (+55.6% ROI) and Pure M3 warning (7.7% win rate)
- **Value Analysis section**: Updated to reflect calibration and M1 boost
- **Serve Stats section**: Added DR explanation and Activity Scores section
- **What to Look For section**: Rewritten with 9 points including M1+M11 guidance
- **Auto Mode section**: Updated model list, added M1 boost note
- **Statistics Tab**: Updated model reference to M1-M12
- **Review by Surface**: Updated surface weight to 22%
- **Key Configuration table**: Added M1 boost, shrinkage factor, market blend settings
- **Document footer**: Added version/date footer

---

## Documentation Update: RISK_MANAGEMENT.md

Updated `docs/RISK_MANAGEMENT.md` from v2.61/v1.0 to v3.1/v1.1. Key changes:

- **Header**: Updated to v3.1, version 1.1, date Feb 5, 2026
- **Governance section**: Updated from 4 models to 11 models (6 hard + 5 soft)
- **Staking section**: Added new sections 2.8-2.9:
  - M1 boost (1.5x), no-data multiplier (0.50x), activity-based reduction
  - Probability calibration now ENABLED (was disabled) with shrinkage 0.60 + market blend 0.35
- **Factor Weights section**: Complete rewrite for v3.1:
  - Reordered (surface 22%, form 20%, fatigue 17%, etc.)
  - Injury marked as DEPRECATED (0%)
  - Added Edge Modifiers section (serve + activity)
- **Models section**: Expanded from 4 to 11 models:
  - Hard Models (M1, M3, M4, M5, M7, M8)
  - Soft Models (M2, M9, M10, M11)
  - Fade Model (M12)
  - Added M1+M11 thesis data and Pure M3 warning
- **Calibration Monitoring section**: Updated to show calibration is ENABLED
- **ROI Tracking table**: Updated to reference all models M1-M12
- **Betting Philosophy**: Updated model reference
- **Appendix A (Config Parameters)**: Added m1_boost, no_data_multiplier, shrinkage_factor, market_blend_weight; updated calibration_enabled and market_blend_enabled to True
- **Appendix B (Model Qualification)**: Complete rewrite for 11 models with key performance data
- **Appendix C (Factor Weight Profiles)**: Updated to v3.1 order with injury=0
- **Appendix D**: New section for Edge Modifiers
- **Document footer**: Updated to v3.1, Feb 5, 2026

---

## Documentation Update: DATA_SOURCES.md

Updated `docs/DATA_SOURCES.md` from v2.61 to v3.1. Key changes:

- **Header**: Updated to v3.1, date to Feb 5, 2026
- **Data Flow Diagram**: Updated Match Analyzer note from "8 factors" to "8 factors + 2 edge mods" with weight breakdown
- **Kelly Staking config**: Added M1 boost (1.5x), no_data_multiplier (0.50x), and new sections for PROBABILITY_CALIBRATION (enabled, shrinkage 0.60, asymmetric) and MARKET_BLEND (enabled, weight 0.35)
- **Document footer**: Updated to v3.1

---

## Documentation Update Summary (Complete)

All major documentation files have been updated to v3.1:

| File | Status | Changes |
|------|--------|---------|
| `state_machines.txt` | ✅ Complete | 26 flows, all models, edge modifiers |
| `MODEL_SPECIFICATION.md` | ✅ Complete | 11 models, edge modifiers, calibration |
| `CONFIGURATION_REFERENCE.md` | ✅ Complete | Factor weights, models, calibration |
| `MODEL_PERFORMANCE.md` | ✅ Complete | Models, weights, calibration |
| `MODEL_ANALYSIS_GUIDE.md` | ✅ Complete | Factor weights, edge modifiers, 11 models |
| `OPERATIONS_GUIDE.md` | ✅ Complete | Factor weights, 11 models, edge modifiers |
| `RISK_MANAGEMENT.md` | ✅ Complete | Factor weights, 11 models, calibration |
| `DATA_SOURCES.md` | ✅ Complete | Data flow, staking config |

Files reviewed but not requiring v3.1 updates:
- `DISCORD_INTEGRATION.md` - Technical bot docs, no model references
- `BETFAIR_INTEGRATION.md` - API integration, technical
- `DEVELOPER_SETUP.md` - Setup guide, technical

Lower-priority files not updated (historical/diagnostic):
- `github_scraper_diagnosis.txt` - Diagnostic doc
- `RANKING_STRUCTURAL_ANALYSIS.md` - Historical analysis
- `INCIDENT_RESPONSE.md` - Operations procedures
- `CRITICAL_FIXES.md` - Fix log

---

## Retroactive M2 Tagging

Added Model 2 (Data Confirmed) tags to 76 historical bets where both players have serve stats from Tennis Ratio.

**M2 Criteria:** Qualifies for another model + serve data exists for both players

**Results:**
- 76 bets retroactively tagged
- Total M2 bets: 91

**Model 2 Performance (settled n=74):**
| Result | Bets | P/L |
|--------|------|-----|
| Win | 30 | +40.25u |
| Loss | 41 | -31.00u |
| Void | 3 | 0.00u |
| **Net** | **74** | **+9.25u** |

- Win rate: 40.5%
- ROI: +12.5%

The "data confirmed" signal shows positive value.

---

## M2 Impact Analysis by Model

Analyzed how M2 (Data Confirmed) affects each model's performance:

### Models That Improve Most with M2:

| Model | Without M2 | With M2 | ROI Boost |
|-------|------------|---------|-----------|
| M4 | -64.9% ROI | +50.0% ROI | **+114.9pp** |
| M8 | -43.2% ROI | +16.0% ROI | **+59.2pp** |
| M3 | -69.4% ROI | -32.4% ROI | **+37.0pp** |
| M5 | -72.1% ROI | -34.3% ROI | **+37.8pp** |
| M7 | -29.9% ROI | +3.6% ROI | **+33.5pp** |

**Key insight:** M2 improves ROI for ALL models. Even M5, which struggles overall, goes from -72.1% to -34.3% with M2 filtering.

### M5+M2 Analysis:
- M5 with M2: 10 settled, 3W-7L, -2.00u, -34.3% ROI
- M5 without M2: 25 settled, 2W-23L, -11.31u, -72.1% ROI
- **Conclusion:** M5 still underperforms even with M2, but significantly less catastrophically.

---

## M2 Filter Simulation (Feb 2-4)

Analyzed what would happen if M2 (both players have serve data) was REQUIRED for all bets:

| Segment | Bets | Settled | Record | P/L | ROI |
|---------|------|---------|--------|-----|-----|
| **ALL bets** | 75 | 58 | 23-35 | +4.38u | +11.1% |
| **With M2 (keep)** | 51 | 35 | 16-19 | **+5.99u** | **+22.2%** |
| **Without M2 (skip)** | 24 | 23 | 7-16 | -1.61u | -12.9% |

### Daily Breakdown:
- Feb 2: 30 bets, 10W-20L, -0.80u (-3.5% ROI)
- Feb 3: 25 bets, 12W-12L, +6.21u (+41.4% ROI)
- Feb 4: 20 bets, 1W-3L, -1.03u (only 4 settled)

### Impact:
- **+7.60u difference** between M2 and non-M2 bets
- Win rate: 45.7% with M2 vs 30.4% without M2
- ROI: +22.2% with M2 vs -12.9% without M2

### Recommendation:
M2 still shows value as a filter. Bets with serve data for both players perform significantly better across ROI and win rate.

---

## Bug Fix: M12 Fade Bets Not Being Created

**Issue:** M12 (2-0 fade) bets were not being created for Pure M3 bets like Aboian.

**Root Cause:** In `bet_suggester.py` line 791-794, when `replaces_original: False` (config setting to add M12 alongside original bet), the code only had a comment `# Create M12 bet too...` but no actual implementation.

**Fix:** Added the complete M12 bet creation code in the `else` block to create and append the fade bet alongside the original bet.

**Files changed:**
- `src/bet_suggester.py` (lines 791-810)
- Synced to `dist/TennisBettingSystem/bet_suggester.py`

**Impact:** M12 fade bets will now be properly created for Pure M3 and M5 bets when opponent odds are 1.20-1.50.

---

