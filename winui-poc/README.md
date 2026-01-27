# Tennis Betting System - WinUI 3 Proof of Concept

This is a proof of concept showing what the Tennis Betting System would look like rebuilt in C# + WinUI 3.

## What's Included

- **Dark theme** matching the current Python app
- **Transparent stat cards** with slate borders (like Darts Manager)
- **Navigation sidebar** with Betfair connection status
- **Sample bets table** with styled rows
- **Quick stats panels** for today's performance and model stats

## How to Run

### Prerequisites

1. **Visual Studio 2022** (Community edition is free)
   - Download: https://visualstudio.microsoft.com/

2. **Windows App SDK workload**
   - In Visual Studio Installer, select ".NET Desktop Development"
   - Check "Windows App SDK C# Templates" in the optional components

3. **.NET 8 SDK**
   - Usually included with Visual Studio 2022

### Steps to Run

1. Open Visual Studio 2022
2. File → Open → Project/Solution
3. Navigate to this folder and open `TennisBettingWinUI.csproj`
4. Wait for NuGet packages to restore
5. Press F5 or click the green "Start" button

## Project Structure

```
winui-poc/
├── App.xaml              # App entry point, theme settings
├── App.xaml.cs           # App startup code
├── MainWindow.xaml       # Main UI layout (this is where the magic is)
├── MainWindow.xaml.cs    # Main window logic
├── Styles/
│   └── AppStyles.xaml    # Colors, brushes, reusable styles
├── app.manifest          # Windows app manifest
└── TennisBettingWinUI.csproj  # Project file
```

## Key Styling Concepts

### Colors (in AppStyles.xaml)
```xml
<Color x:Key="BgDark">#0f172a</Color>
<Color x:Key="BorderSlate">#475569</Color>
<Color x:Key="AccentGreen">#22c55e</Color>
```

### Stat Card Style (transparent with border)
```xml
<Style x:Key="StatCardBorder" TargetType="Border">
    <Setter Property="Background" Value="Transparent"/>
    <Setter Property="BorderBrush" Value="{StaticResource BorderSlateBrush}"/>
    <Setter Property="BorderThickness" Value="2"/>
    <Setter Property="CornerRadius" Value="8"/>
</Style>
```

### Using a Style
```xml
<Border Style="{StaticResource StatCardBorder}">
    <TextBlock Text="247" Style="{StaticResource StatValueText}"/>
</Border>
```

## Next Steps (if you decide to go this route)

1. **Add data binding** - Connect to real data instead of hardcoded values
2. **Create ViewModels** - MVVM pattern for clean separation
3. **Add navigation** - Switch between Bet Tracker, Value Bets, Statistics pages
4. **Port the backend** - Either rewrite in C# or call Python via interop
5. **Add Betfair API integration** - C# has great HTTP client support
6. **Add SQLite** - Microsoft.Data.Sqlite package works great

## Comparison: Python/Tkinter vs C#/WinUI

| Aspect | Python/Tkinter | C#/WinUI 3 |
|--------|----------------|------------|
| Styling | Limited, hacky borders | Full CSS-like control |
| Rounded corners | Not really possible | Native support |
| Animations | Complex | Built-in |
| Performance | Slower | Native, fast |
| Packaging | PyInstaller (large) | MSIX or single exe |
| Learning curve | You know it | New language |
