# Factor Breakdown Popup Specifications

This document defines what each factor breakdown popup shows when clicked in the Match Analysis view. Edit the `[SELECTED]` markers to change what's displayed.

---

## General Structure

Each breakdown popup follows this pattern:
1. **Title** - Factor name
2. **Description** - What this factor measures (tooltip text)
3. **Raw Data** - The underlying metrics for each player
4. **Calculation** - How scores are derived (optional)
5. **Final Score** - The resulting advantage

---

## Factor 1: Ranking

**Description (tooltip):**
> Compares player rankings using Elo conversion. Higher-ranked players have exponentially more skill than lower-ranked players.

**Available Data:**
- Current ATP/WTA rank
- Elo rating (converted via logarithmic scale)
- Whether rank was estimated from odds
- Rank trajectory (improving/declining)
- Peak ranking
- Elo win probability

### Section 1: Core Data Display
- [ ] **A) Minimal** - Just current rank + Elo
- [x] **B) Standard** - Rank + Elo + trajectory
- [ ] **C) Full** - All of above + peak ranking + history

`[SELECTED]: B`

### Section 2: Show Elo Calculation Formula?
- [x] **A) Yes** - Show: `Elo = 2500 - 150 * log2(rank)`
- [ ] **B) No** - Just show the converted Elo value

`[SELECTED]: A`

### Section 3: Show Win Probability Calculation?
- [x] **A) Yes** - Show how Elo difference converts to win %
- [ ] **B) No** - Just show final advantage score

`[SELECTED]: A`

### Section 4: Estimated Ranks (from odds)?
- [ ] **A) Explain** - Show odds-to-rank mapping used
- [x] **B) Simple** - Just flag with "~" prefix

`[SELECTED]: B`

---

## Factor 2: Form

**Description (tooltip):**
> Recent match results with recency decay. More recent matches weighted higher. Opponent strength affects score.

**Available Data:**
- Recent matches (default 10)
- Win/Loss record
- Score per match (based on opponent rank)
- Recency decay weight per match
- Overall form score (0-100)

### Section 1: Match List Display
- [ ] **A) Summary only** - Just W-L record and score
- [x] **B) Match list** - Show each match with date, opponent, result
- [ ] **C) Detailed** - Match list + opponent rank + weight applied

`[SELECTED]: B`

### Section 2: Show Decay Formula?
- [x] **A) Yes** - Show recency decay: `weight = 0.9^match_index`
- [ ] **B) No** - Just show weighted results

`[SELECTED]: A`

### Section 3: Show Opponent Impact?
- [x] **A) Yes** - Show how opponent rank affects match score
- [ ] **B) No** - Just show final form score

`[SELECTED]: A`

---

## Factor 3: Surface

**Description (tooltip):**
> Win rate on the current surface. Combines career stats (40%) with recent 2-year stats (60%).

**Available Data:**
- Career surface win rate
- Career surface matches played
- Recent (2yr) surface win rate
- Recent surface matches played
- Combined weighted win rate

### Section 1: Data Display
- [x] **A) Combined only** - Just show final combined win rate
- [ ] **B) Split view** - Show career vs recent separately
- [ ] **C) Full breakdown** - Career + recent + weighting explanation

`[SELECTED]: A`

### Section 2: Show Match Counts?
- [x] **A) Yes** - Show number of matches (reliability indicator)
- [ ] **B) No** - Just show percentages

`[SELECTED]: A`

### Section 3: Flag Low Sample Size?
- [x] **A) Yes** - Warn if < 20 matches on surface
- [ ] **B) No** - Show data regardless

`[SELECTED]: A`

---

## Factor 4: Head-to-Head

**Description (tooltip):**
> Historical record between these two players. Surface-specific H2H weighted more heavily.

**Available Data:**
- Overall H2H record (P1 wins vs P2 wins)
- Surface-specific H2H record
- Individual match history between them
- Recency of H2H matches

### Section 1: Record Display
- [ ] **A) Summary** - Just overall W-L record
- [ ] **B) With surface** - Overall + surface-specific record
- [x] **C) Full history** - List all previous matches between them

`[SELECTED]: C`

### Section 2: Show Match Details?
- [x] **A) Yes** - Date, tournament, score for each H2H match
- [ ] **B) No** - Just the win counts

`[SELECTED]: A`

### Section 3: No H2H Data?
- [x] **A) Explain** - "No previous meetings" message
- [ ] **B) Neutral** - Show 0-0 silently

`[SELECTED]: A`

---

## Factor 5: Fatigue

**Description (tooltip):**
> Rest days and recent workload. Optimal rest is 3 days. Too little = tired, too much = rusty.

**Available Data:**
- Days since last match
- Rust penalty (if applicable)
- Rest component score (0-40)
- Matches in last 7/14/30 days
- Match difficulty points
- Workload component score (0-40)
- Base fitness (20)
- Total score (0-100)
- Status label (Fresh/Rested/Active/Heavy/Exhausted)

### CURRENT IMPLEMENTATION: Full breakdown with all components
*This factor already has a detailed popup - keep as reference for others*

`[STATUS]: Already implemented`

---

## Factor 6: Injury

**Description (tooltip):**
> Known injury status. Currently limited to active/injured flags.

**Available Data:**
- Injury status (Active/Injured/Unknown)
- Injury score (100 = healthy, lower = injured)

### Section 1: Display
- [ ] **A) Simple** - Just show status (Active/Injured)
- [x] **B) With score** - Status + injury score
- [ ] **C) With note** - Allow adding injury notes/context

`[SELECTED]: B`

### Section 2: Data Limitation Notice?
- [x] **A) Yes** - Note that injury data is limited/manual
- [ ] **B) No** - Show what we have without caveat

`[SELECTED]: A`

---

## Factor 7: Opponent Quality

**Description (tooltip):**
> Average strength of recent opponents. Playing tough opponents = better preparation.

**Available Data:**
- Recent opponents list (last 6 matches)
- Each opponent's ranking
- Average opponent ranking
- Quality score (-1 to 1 scale)

### Section 1: Display
- [ ] **A) Summary** - Just average opponent ranking
- [ ] **B) List** - Show each recent opponent with their rank
- [x] **C) Detailed** - List + how it converts to score

`[SELECTED]: C`

### Section 2: Show Calculation?
- [x] **A) Yes** - Show how avg rank becomes quality score
- [ ] **B) No** - Just show final score

`[SELECTED]: A`

---

## Factor 8: Recency

**Description (tooltip):**
> How recent the form data is. Recent matches weighted higher than old matches.

**Available Data:**
- Days since each recent match
- Recency weight per match (1.0 for 7d, 0.7 for 30d, 0.4 for 90d, 0.2 for older)
- Overall recency score

### Section 1: Display
- [ ] **A) Summary** - Just overall recency score
- [ ] **B) Match dates** - Show when each recent match was played
- [x] **C) With weights** - Match dates + weight applied to each

`[SELECTED]: C`

### Section 2: Show Weight Tiers?
- [x] **A) Yes** - Explain the 7d/30d/90d/older tiers
- [ ] **B) No** - Just show the data

`[SELECTED]: A`

---

## Factor 9: Recent Loss

**Description (tooltip):**
> Penalty for coming off a loss. Bigger penalty for very recent losses or exhausting 5-set losses.

**Available Data:**
- Last loss date (if any recent)
- Days since loss
- Was it a 5-setter?
- Penalty amount (0 to -0.15)

### Section 1: Display
- [ ] **A) Simple** - Just show penalty amount
- [x] **B) With context** - Show last loss details + penalty
- [ ] **C) Full** - Loss details + penalty breakdown by type

`[SELECTED]: B`

### Section 2: Show Penalty Tiers?
- [x] **A) Yes** - Explain 3-day vs 7-day vs 5-set penalties
- [ ] **B) No** - Just show calculated penalty

`[SELECTED]: A`

---

## Factor 10: Momentum

**Description (tooltip):**
> Bonus for recent wins on the same surface. Hot streaks matter.

**Available Data:**
- Recent wins on current surface (last 14 days)
- Bonus per win (0.03)
- Total bonus (capped at 0.10)

### Section 1: Display
- [ ] **A) Simple** - Just show bonus amount
- [x] **B) With wins** - Show win count + bonus
- [ ] **C) Match list** - List the momentum-building wins

`[SELECTED]: B`

### Section 2: Show Cap?
- [x] **A) Yes** - Note the 0.10 maximum bonus
- [ ] **B) No** - Just show current bonus

`[SELECTED]: A`

---

## Implementation Notes

### Tooltip Implementation
Each factor row should have a hover tooltip showing the description text.

### Click Behavior
Clicking the factor row (or the ">" indicator) opens the breakdown popup.

### Visual Consistency
All popups should follow the Fatigue breakdown style:
- Dark background
- Card-style content area
- Table with player columns
- Section headers in bold
- Metrics in muted color
- Calculated scores in accent color
- Total/summary in green

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-20 | Initial spec created |

