# Tennis Betting System - Product Specification

## Executive Summary

This document defines the requirements and design for a professional tennis betting system. The primary goal is **positive ROI** through systematic identification of market inefficiencies. The system will evolve from manual operation to full automation while maintaining human oversight.

---

## 1. Core Philosophy

### 1.1 Results First
- Profitability is the #1 priority above all else
- Every feature must justify its existence through contribution to edge
- UI polish is secondary to model accuracy

### 1.2 Edge Sources
The system targets market inefficiencies through:
- **Data processing speed**: Faster integration of form/injury updates than bookmakers
- **Niche market exploitation**: Lower-ranked matches with less market efficiency
- **Multi-factor combination**: Combining signals that individual bettors miss

### 1.3 Volume Strategy
- Prefer **high volume with smaller edge** over low volume with high edge
- Example: 100 bets @ 3% edge preferred over 20 bets @ 10% edge
- Take all positive EV bets regardless of confidence level

---

## 2. Staking Framework

### 2.1 Kelly Criterion Implementation
```
Final Stake = Kelly Stake × Kelly Fraction × Disagreement Penalty
```

**Parameters:**
| Setting | Value | Rationale |
|---------|-------|-----------|
| Kelly Fraction | 0.40 | Balanced between conservative (0.25) and aggressive (0.50) |
| Minimum Odds | 1.70 | Heavy favorites offer poor value |
| Minimum Bet | 0.5 units | Below this threshold, don't bet |
| Maximum Bet | 3.0 units | Safety cap |
| Unit Size | 2% of bankroll | Standard unit definition |

### 2.2 Market Disagreement Penalty
When our probability exceeds market implied probability:

| Disagreement Level | Probability Ratio | Stake Multiplier |
|-------------------|-------------------|------------------|
| Minor | Up to 1.5× | 100% |
| Moderate | 1.5× - 2.0× | 75% |
| Major | 2.0× - 3.0× | 50% |
| Extreme | 3.0×+ | 25% |

### 2.3 Bankroll Management
- **Starting bankroll**: 50-100 units
- **Stop-loss**: -50 units (triggers system pause and review)
- **Platform**: Betfair Exchange only
- **Commission**: 2% (Basic package) applied to winnings only

---

## 3. Betting Rules

### 3.1 Market Selection
- **Pre-match only**: No in-play/live betting
- **Match winner only**: No correlated bets (e.g., correct score alongside match winner)
- **One bet per match**: Avoid correlated exposure
- **All +EV bets**: Take every positive expected value opportunity

### 3.2 Tournament Coverage
- ATP and WTA tours (WTA noted for higher variance/shocks)
- Grand Slams (Best of 5) and regular tour (Best of 3) use same model
- Fatigue factor is key differentiator for Bo5 matches

### 3.3 Volume Expectations
- Current: 5-10 bets per day
- Target with automation: Up to 100 bets per day if edge exists

---

## 4. Model Architecture

### 4.1 Current Factors and Weights
```python
DEFAULT_ANALYSIS_WEIGHTS = {
    "form": 0.20,           # Recent match results
    "ranking": 0.20,        # Current ATP/WTA ranking
    "surface": 0.15,        # Surface-specific performance
    "h2h": 0.10,            # Head-to-head record
    "opponent_quality": 0.10, # Quality of recent opponents
    "recency": 0.08,        # How recent the form data is
    "fatigue": 0.05,        # Rest days and match load
    "injury": 0.05,         # Injury status
    "recent_loss": 0.05,    # Penalty for coming off loss
    "momentum": 0.02,       # Tournament/surface momentum
}
```

### 4.2 Weight Optimization Approach
1. **Historical optimization**: Find weights that would have maximized ROI
2. **Rolling calibration**: Continuous adjustment based on recent accuracy (30-90 days)
3. **Surface-specific profiles**: Different weights for hard/clay/grass

**Critical Requirement**: Weight changes require:
- Detailed documentation explaining rationale
- 1000+ bet sample for statistical validation
- Human review and approval (never automatic)

### 4.3 Factor Conflict Handling
- Use simple weighted average when factors disagree
- No special handling for conflicting signals
- No automatic confidence reduction

### 4.4 Unknown/New Players
- All players expected to have match data (data procedures exist)
- Flag immediately if data gaps found
- Manual intervention to add data or import player

---

## 5. Model Improvement System

### 5.1 Loss Diagnosis
For every losing bet, automatically capture:
- **Pre-match factors**: What the model saw (form, H2H, surface stats, fatigue scores)
- **Match statistics**: Actual performance (aces, break points, etc.)
- **Context notes**: Free-text for factors model couldn't know (weather, injury, crowd)

### 5.2 Pattern Detection
When systematic losing patterns identified (e.g., "model overvalues grass specialists on slow hard courts"):
- System should **suggest new factors** to add
- Never auto-implement - requires human review
- Document thoroughly before any change

### 5.3 Backtesting
- **Theoretical approach acceptable**: Calculate edge against closing odds
- Assume we could have gotten the odds shown
- No need for complex line movement simulation

---

## 6. Automation Roadmap

### 6.1 Phase 1: Manual (Current)
- Human triggers analysis
- Human places bets
- Human tracks results

### 6.2 Phase 2: Semi-Automated
- Automatic data updates (same-day)
- Automatic analysis runs
- Push notifications for value bets
- Human reviews and places bets

### 6.3 Phase 3: Full Automation
- Betfair API integration for bet placement
- Automatic bet execution within parameters
- Daily human review of all automated activity

### 6.4 Automation Concerns
- **Model errors**: Require human oversight
- **Technical failures**: Need monitoring and alerts
- **Market anomalies**: System should flag unusual situations

### 6.5 Kill Switch
- Ability to immediately halt all automated betting
- Triggered by stop-loss or manual intervention

---

## 7. Notifications

### 7.1 Requirements
- Push notifications to phone
- Trigger on ANY value bet found (no filtering)
- No quiet hours - always notify
- Include: Match, Selection, Odds, EV, Recommended Units

### 7.2 Future Consideration
- In-app notifications
- Telegram/Discord integration
- Email summaries

---

## 8. Analytics and Tracking

### 8.1 Key Metrics
| Metric | Description | Target |
|--------|-------------|--------|
| ROI | Return on Investment | 5-10% (accept 2-3% with high volume) |
| Win Rate | Wins / (Wins + Losses) | Track but don't optimize |
| Units P/L | Profit/Loss in units | Positive |
| CLV | Closing Line Value | Nice to have, not critical |

### 8.2 Calibration Analysis
- Compare predicted probabilities to actual win rates
- By probability bucket (50-55%, 55-60%, etc.)
- By surface, tournament level, bet type

### 8.3 Performance Breakdown
- By surface (Hard/Clay/Grass)
- By tournament category
- By odds range
- By model confidence level

---

## 9. User Interface

### 9.1 Design Philosophy
- **Sports betting native**: Look like Bet365/DraftKings
- **Dark theme**: Refined colors (current implementation)
- **Prominent odds**: Large, clear odds display
- **Quick actions**: Fast bet placement buttons

### 9.2 Default View
- **Today's value bets** on app open
- Sorted by recommended units
- Quick-add to tracker

### 9.3 Priority Improvements
1. **Visual design** (highest priority)
2. Information density
3. Speed/responsiveness
4. Mobile consideration (future)

### 9.4 Current State
- Match analysis screen: "Almost perfect"
- Bet tracker: Functional, needs polish
- Dashboard: Acceptable, not great

---

## 10. Data Management

### 10.1 Data Sources
- Tennis Explorer (via GitHub scraper)
- Betfair API (free tier) for live odds
- Manual entry for injuries/context

### 10.2 Update Frequency
- Same-day updates for match data
- Real-time odds from Betfair API
- Manual injury updates as needed

### 10.3 Data Quality
- Flag missing data immediately
- Established procedures to fix gaps
- All players should have match history

---

## 11. Success Criteria

### 11.1 12-Month Goal
**Primary**: Positive ROI (any profit proves system works)

### 11.2 Stretch Goals
- Achieve 5-10% ROI consistently
- Full automation operational
- Proven scalable edge

### 11.3 Current Pain Point
**Model accuracy** - predictions don't match actual results well enough

---

## 12. Technical Requirements

### 12.1 Platform
- Windows desktop application (current)
- Python/Tkinter stack
- SQLite database

### 12.2 Future Considerations
- Web interface for remote access
- Mobile app or responsive web
- Cloud deployment for automation

### 12.3 Betfair Integration
- Exchange API for odds retrieval
- Bet placement API (Phase 3)
- 2% commission rate (Basic package)

---

## 13. Risk Management

### 13.1 Financial Risks
- 50-unit stop-loss triggers review
- Maximum 3 units per bet
- Kelly fraction limits exposure

### 13.2 Technical Risks
- Daily review of automated bets
- Exception alerts for unusual patterns
- Manual override capability

### 13.3 Model Risks
- 1000+ bet validation requirement
- Human approval for all weight changes
- Full audit trail for diagnosis

---

## Appendix A: Configuration Reference

```python
KELLY_STAKING = {
    "unit_size_percent": 2.0,
    "kelly_fraction": 0.40,
    "exchange_commission": 0.02,
    "min_odds": 1.70,
    "min_units": 0.5,
    "max_units": 3.0,
    "disagreement_penalty": {
        "minor": {"max_ratio": 1.5, "penalty": 1.0},
        "moderate": {"max_ratio": 2.0, "penalty": 0.75},
        "major": {"max_ratio": 3.0, "penalty": 0.50},
        "extreme": {"max_ratio": 999, "penalty": 0.25},
    },
    "min_model_confidence": 0.50,
}
```

---

## Appendix B: Interview Summary

This specification was compiled from a detailed product interview covering:
- Edge sources and betting philosophy
- Staking and bankroll management
- Model architecture and improvement
- Automation and notification requirements
- UI/UX priorities
- Success criteria and risk management

**Key Insight**: The biggest current frustration is **model accuracy** - improving prediction quality is the highest-impact work.

---

*Document Version: 1.0*
*Created: January 2026*
*Status: Initial Specification*
