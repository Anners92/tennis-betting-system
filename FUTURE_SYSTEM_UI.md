# Future System UI - Tennis Betting Pro

This document captures the vision for rebuilding the Tennis Betting System with a professional, modern UI using C# and WinUI 3.

---

## Overview

**Current System:** Python + Tkinter (functional but dated styling)
**Future System:** C# + WinUI 3 (professional trading platform look)

**Proof of Concept Location:** `winui-poc/`

---

## Why WinUI 3?

| Factor | Benefit |
|--------|---------|
| **Industry Standard** | Bloomberg, trading desks, fintech apps use WPF/WinUI |
| **Styling Control** | CSS-like stylesheets, gradients, rounded corners, animations |
| **Performance** | Native Windows rendering, fast data updates |
| **Professional Look** | Modern glassmorphism, dark themes, data-dense layouts |

---

## Design Inspiration

Based on research into professional trading/betting UIs:

- [VisualHFT](https://github.com/visualHFT/VisualHFT) - Open source WPF trading platform
- [Dribbble Fintech Designs](https://dribbble.com/tags/dark-fintech) - Dark theme dashboards
- [ComponentOne FinTech Controls](https://developer.mescius.com/componentone/fintech-finance-industry-ui-controls)
- 2025 Fintech UX trends - glassmorphism, data density, real-time indicators

---

## Color Palette

```
BACKGROUNDS
-----------
BgDark:       #0d0f1a    (Main background - deep navy)
BgNavy:       #141829    (Sidebar background)
BgCard:       #1e2235    (Card backgrounds)
BgGlass:      #2a2f4a    (Glass overlay elements)

ACCENTS
-------
AccentPink:   #ec4899    (Gradient start, alerts)
AccentPurple: #a855f7    (Gradient middle)
AccentCyan:   #06b6d4    (Gradient end, highlights)
AccentBlue:   #3b82f6    (Links, secondary accent)

STATUS
------
SuccessGreen: #10b981    (Profit, wins)
SuccessCyan:  #22d3ee    (Positive trends)
WarningYellow:#f59e0b    (Pending, caution)
DangerRed:    #ef4444    (Loss, errors)

TEXT
----
TextPrimary:  #ffffff    (Main text)
TextSecondary:#94a3b8    (Labels, secondary info)
TextMuted:    #64748b    (Hints, disabled)
```

---

## Key UI Components

### 1. Gradient Header Card
Large P/L display with sparkline trend chart
```
+------------------------------------------+
|  Total Profit/Loss                       |
|  +12.45 units            [sparkline]     |
|  [+2.31u today] [5.8% ROI]               |
+------------------------------------------+
```

### 2. Stat Cards
Compact stats with trend indicators
```
+------------------+
| Win Rate    +2.1%|
| 38.2%            |
| 94W / 153L       |
+------------------+
```

### 3. Data Tables
Compact rows with status badges
```
| TIME     | MATCH              | ODDS | STAKE | P/L     |
|----------|--------------------| -----|-------|---------|
| 09:30    | Keys vs Pegula     | 2.48 | 1.5u  | PENDING |
| Yesterday| Shelton vs Sonego  | 1.42 | 2.0u  | +0.84u  |
```

### 4. Model Performance Bars
Visual ROI comparison
```
M2  ████████████████████  +8.2%
M4  ██████████████        +5.4%
M1  ██████████            +3.1%
M5  ████                  -2.3%
```

### 5. Sidebar Navigation
With quick stats and connection status
```
+----------------------+
| TENNIS BETTING       |
| PRO SYSTEM           |
+----------------------+
| +12.45u  | +5.8%     |
| Total P/L| ROI       |
| 247      | 38.2%     |
| Bets     | Win Rate  |
+----------------------+
| Dashboard      [23]  |
| Value Bets           |
| Bet History          |
| Analytics            |
| Players DB           |
| Settings             |
+----------------------+
| ● LIVE    09:42:15   |
| Betfair: MAnley92    |
| API: 176 calls left  |
+----------------------+
```

---

## Professional Features to Include

### Data Visualization
- [ ] Sparkline charts for P/L trends
- [ ] Bar charts for model comparison
- [ ] Donut charts for win/loss ratio
- [ ] Candlestick-style profit charts

### Real-Time Indicators
- [ ] LIVE badge with pulsing animation
- [ ] Last updated timestamps
- [ ] Connection status (green dot)
- [ ] API calls remaining counter

### Data Density
- [ ] Compact table rows
- [ ] Collapsible sections
- [ ] Quick filters (dropdowns)
- [ ] Search functionality

### Power User Features
- [ ] Keyboard shortcuts
- [ ] Export to CSV/Excel
- [ ] Customizable dashboard layout
- [ ] Multiple view modes (compact/detailed)

### Trust Indicators
- [ ] Data source attribution
- [ ] Sync status
- [ ] Error notifications (snackbar)

---

## Technology Stack

```
Language:     C# (.NET 8)
UI Framework: WinUI 3 (Windows App SDK 1.6+)
Database:     SQLite (same as current)
IDE:          Visual Studio 2022/2026
```

### Required Packages
```xml
<PackageReference Include="Microsoft.WindowsAppSDK" Version="1.6.x" />
<PackageReference Include="CommunityToolkit.WinUI" Version="8.x" />  <!-- For charts -->
<PackageReference Include="Microsoft.Data.Sqlite" Version="8.x" />
```

---

## Migration Path

### Phase 1: POC (DONE)
- [x] Set up WinUI 3 project
- [x] Create color palette and styles
- [x] Build dashboard mockup with sample data
- [x] Test in Visual Studio

### Phase 2: Core Structure
- [ ] Set up MVVM architecture (ViewModels, Models, Services)
- [ ] Create navigation system
- [ ] Implement SQLite database connection
- [ ] Port data models from Python

### Phase 3: Feature Parity
- [ ] Bet Tracker page (full functionality)
- [ ] Value Bets / Bet Suggester page
- [ ] Statistics / Analytics page
- [ ] Settings page
- [ ] Betfair API integration (C# HTTP client)
- [ ] The Odds API integration

### Phase 4: Enhancements
- [ ] Real-time odds updates
- [ ] Charts and visualizations
- [ ] Keyboard shortcuts
- [ ] Export functionality
- [ ] Auto-update system

---

## File Structure (Planned)

```
TennisBettingPro/
├── App.xaml                    # App entry, theme
├── MainWindow.xaml             # Shell with navigation
├── Views/
│   ├── DashboardPage.xaml      # Main dashboard
│   ├── ValueBetsPage.xaml      # Bet suggester
│   ├── BetHistoryPage.xaml     # All bets table
│   ├── AnalyticsPage.xaml      # Statistics
│   ├── PlayersPage.xaml        # Player database
│   └── SettingsPage.xaml       # Configuration
├── ViewModels/
│   ├── DashboardViewModel.cs
│   ├── ValueBetsViewModel.cs
│   └── ...
├── Models/
│   ├── Bet.cs
│   ├── Match.cs
│   ├── Player.cs
│   └── ...
├── Services/
│   ├── DatabaseService.cs      # SQLite operations
│   ├── BetfairService.cs       # Betfair API
│   ├── OddsApiService.cs       # The Odds API
│   └── AnalyticsService.cs     # Calculations
├── Styles/
│   └── AppStyles.xaml          # Global styles
└── Assets/
    └── ...
```

---

## Running the POC

1. Open Visual Studio 2022/2026
2. Open `tennis betting/winui-poc/TennisBettingWinUI.csproj`
3. Ensure Windows App SDK 1.6 runtime is installed
4. Press F5 to build and run

---

## Screenshots / Reference

The POC demonstrates:
- Dark navy/purple glassmorphism theme
- Pink-purple-cyan gradient accents
- Professional data-dense layout
- Sidebar navigation with quick stats
- Real-time connection indicators

See `screenshots/concept.png` for the design inspiration.

---

## Decision Log

| Date | Decision |
|------|----------|
| 25 Jan 2026 | Chose WinUI 3 over Electron/Tauri for native Windows performance |
| 25 Jan 2026 | Adopted glassmorphism dark theme based on fintech research |
| 25 Jan 2026 | Created POC with professional trading platform features |

---

## Notes

- The current Python system remains fully functional
- This is a long-term improvement project
- Can migrate gradually, feature by feature
- Database (SQLite) can be shared between systems during transition
