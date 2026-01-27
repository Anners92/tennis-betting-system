# Tennis Betting System - Product Specification

## Overview

A desktop application for analyzing ATP/WTA tennis matches and generating betting recommendations based on historical data, player statistics, and multi-factor analysis.

**Primary User**: Individual bettor seeking data-driven insights to inform betting decisions.

**Current Status**: Functional prototype with core features implemented. Not yet validated enough for real-money betting.

---

## Core Use Case

The user wants to:
1. Select two players for an upcoming match
2. Get a detailed analysis of factors affecting the outcome
3. Receive betting recommendations with expected value calculations
4. Make informed betting decisions based on data rather than intuition

---

## Current State Assessment

### What's Working
- Basic match analysis with 10 weighted factors
- Player database with historical match data
- Tennis Explorer data import
- Factor breakdown with clickable details
- Set betting predictions
- Unit-based staking recommendations

### Critical Pain Points

#### 1. Manual Work Overload (HIGH PRIORITY)
The system requires too much manual intervention:
- TE Import must be run manually for each player
- Rankings require separate manual update
- Data quality issues require manual investigation
- No automated daily refresh

**Impact**: User spends more time on data management than analysis.

#### 2. Model Accuracy Concerns (HIGH PRIORITY)
- **Longshot Bias**: System frequently shows underdogs as "good value" when they likely aren't
- Suspected cause: Linear ranking scaling doesn't reflect true skill gaps
- Example: Gap between #2 and #200 is massive; gap between #200 and #400 is minimal
- User has not validated model against actual betting outcomes

**Impact**: Cannot trust recommendations for real bets.

#### 3. Data Quality Issues (MEDIUM PRIORITY)
- Duplicate player detection sometimes fails
- Import issues (wrong player loaded for common names like "Osaka")
- Missing or incomplete match data
- Alias system helps but isn't comprehensive

**Impact**: Analysis quality depends on data quality.

---

## Requirements

### P0 - Must Have (Before Real Use)

#### Model Validation System
- [ ] Track record feature: Log predictions vs actual outcomes
- [ ] Calculate historical accuracy by confidence tier
- [ ] Identify which factors are predictive vs noise
- [ ] Surface-specific accuracy tracking
- [ ] Confidence calibration (does 70% confidence = 70% win rate?)

#### Non-Linear Ranking Scaling
- [ ] Implement logarithmic or tiered ranking impact
- [ ] Top 10 vs Top 50: Large gap
- [ ] Top 50 vs Top 100: Moderate gap
- [ ] Top 100 vs Top 200: Small gap
- [ ] Beyond 200: Minimal differentiation
- [ ] Configurable curve parameters

#### Reduce Longshot Bias
- [ ] Audit EV calculations for systematic bias
- [ ] Add sanity checks (flag when underdog EV seems too high)
- [ ] Consider separate models for favorites vs underdogs
- [ ] Surface any data quality issues affecting the prediction

### P1 - Should Have (Quality of Life)

#### Automation
- [ ] Scheduled daily data refresh (background task)
- [ ] Auto-import rankings on startup or daily
- [ ] Auto-import recent match data for tracked players
- [ ] Scheduled reports (upcoming matches, recommendations)

#### Bet Tracking / Portfolio
- [ ] Bet slip: Record recommended bets taken
- [ ] Track actual outcomes when matches complete
- [ ] P&L tracking by time period
- [ ] ROI calculation
- [ ] Filter history by surface, confidence, tournament level

#### Player Notes & Tags
- [ ] Add custom notes to players
- [ ] Tag players (e.g., "clutch performer", "poor on clay", "injury prone")
- [ ] Surface notes in analysis when relevant

### P2 - Nice to Have (Polish)

#### UI/UX Improvements
- [ ] Visual consistency across all screens
- [ ] Better navigation flow
- [ ] Data visualization (charts, trends)
- [ ] Mobile-friendly or web version
- [ ] Dark mode refinements

#### Advanced Analysis
- [ ] Tournament-specific analysis (some players excel at specific events)
- [ ] Weather/conditions factor (outdoor vs indoor)
- [ ] Retirement/walkover risk assessment
- [ ] Live odds integration

---

## Factor Analysis System

### Current Factors (10 total)

| Factor | Weight | Description |
|--------|--------|-------------|
| Form | 20% | Recent match results with recency decay |
| Surface | 15% | Career and recent surface-specific win rates |
| Ranking | 20% | Current ATP/WTA ranking comparison |
| H2H | 10% | Head-to-head record between players |
| Fatigue | 5% | Rest days, recent workload, rust penalty |
| Injury | 5% | Known injury status |
| Opponent Quality | 10% | Quality of recent opponents faced |
| Recency | 8% | How recent the form data is |
| Recent Loss | 5% | Penalty for coming off a loss |
| Momentum | 2% | Recent wins on same surface |

### Proposed Changes

#### Ranking Factor Overhaul
Current: Linear comparison of rankings
Proposed: Non-linear scaling

```
Skill Gap Formula (proposed):
if rank <= 10: skill = 100 - (rank * 2)      # Top 10: 80-100
elif rank <= 50: skill = 80 - (rank-10) * 0.5  # 11-50: 60-80
elif rank <= 100: skill = 60 - (rank-50) * 0.3 # 51-100: 45-60
elif rank <= 200: skill = 45 - (rank-100) * 0.1 # 101-200: 35-45
else: skill = 35 - min((rank-200) * 0.02, 15)  # 200+: 20-35
```

#### WTA-Specific Adjustments
- WTA tour is more volatile than ATP
- Consider higher variance in predictions
- Possibly different weighting for WTA matches

---

## Technical Architecture

### Data Sources
- **Primary**: Tennis Explorer (via GitHub scraper)
- **Rankings**: Manual import or future API integration
- **Odds**: Manual entry (future: API integration)

### Database
- SQLite database (`tennis_betting.db`)
- Tables: players, matches, rankings, aliases
- Location: `%LOCALAPPDATA%/TennisBettingSystem/data/` (frozen) or project `data/` folder

### Key Files
- `config.py` - All configurable parameters
- `match_analyzer.py` - Core analysis logic
- `bet_suggester.py` - UI and recommendations
- `data_fetcher.py` - Tennis Explorer import
- `db_manager.py` - Database operations

---

## Success Metrics

### Model Performance
- [ ] Prediction accuracy > 55% (long-term)
- [ ] Positive ROI over 100+ tracked bets
- [ ] Calibrated confidence (predicted probability ≈ actual win rate)

### User Experience
- [ ] < 5 minutes from app launch to analysis
- [ ] < 1 manual action required for routine use
- [ ] Clear explanation for every recommendation

### Data Quality
- [ ] < 5% duplicate player rate
- [ ] > 95% of matches have complete data
- [ ] Rankings updated within 7 days

---

## Implementation Priorities

### Phase 1: Validation Foundation
1. Implement bet tracking (log predictions)
2. Add non-linear ranking scaling
3. Build historical accuracy report

### Phase 2: Automation
1. Scheduled data refresh
2. Auto-import rankings
3. Background player updates

### Phase 3: Polish
1. UI consistency pass
2. Player notes/tags
3. Advanced visualizations

---

## Open Questions

1. **Odds Source**: Should we integrate a live odds API? Which bookmaker?
2. **Scope**: Focus on ATP only, or equal WTA support?
3. **Deployment**: Keep as desktop app or move to web?
4. **Historical Data**: How far back should we analyze? (Currently: 2000+)

---

## Appendix: Interview Insights

### Key Quotes (Paraphrased)
- "Too much manual work - TE Import, rankings, data quality issues"
- "Shows longshots as good value when they probably aren't"
- "Not confident enough to use for real bets yet"
- "Gap between #2 and #200 is huge; #200 to #400 is much smaller"
- "WTA is more volatile than ATP"
- "Want to track record of predictions before trusting it"

### User Priorities (Ranked)
1. Reduce manual work
2. Improve model accuracy
3. UI/UX polish
4. Advanced features

### Concerns
- Losing money on bad predictions
- Data quality affecting analysis
- Time spent on maintenance vs actual betting
