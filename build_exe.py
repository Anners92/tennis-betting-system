"""
Build script for Tennis Betting System
Creates a standalone executable using PyInstaller
Uses temp directory to avoid OneDrive file locking issues
"""

import subprocess
import sys
import os
import shutil
import time
import tempfile
from pathlib import Path


def robust_remove(path: Path, max_retries=5, delay=1):
    """Remove directory with retry logic for OneDrive locked files."""
    for attempt in range(max_retries):
        try:
            if path.exists():
                shutil.rmtree(path)
            return True
        except PermissionError as e:
            if attempt < max_retries - 1:
                print(f"  Retry {attempt + 1}/{max_retries} - waiting for file locks...")
                time.sleep(delay)
            else:
                print(f"  Warning: Could not remove {path}: {e}")
                return False
    return True


def copy_source_files(src_dir: Path, dist_dir: Path):
    """Copy Python source files to dist folder."""
    print("\nCopying source files...")

    py_files = [
        'config.py',
        'database.py',
        'data_loader.py',
        'data_validation.py',
        'github_data_loader.py',
        'match_analyzer.py',
        'match_assignment.py',
        'bet_suggester.py',
        'bet_tracker.py',
        'player_lookup.py',
        'odds_scraper.py',
        'betfair_capture.py',
        'betfair_tennis.py',
        'tennis_abstract_scraper.py',
        'tennis_explorer_scraper.py',
        'name_matcher.py',
        'rankings_ui.py',
        'rankings_scraper.py',
        'rankings_downloader.py',
        'rankings_manager.py',
        'te_import_dialog.py',
        'detailed_analysis.py',
        'database_ui.py',
        'model_analysis.py',
        'discord_notifier.py',
        'performance_elo.py',
        'cleanup_duplicates.py',
        'delete_duplicates.py',
        'create_seed_database.py',
        '__init__.py',
    ]

    for filename in py_files:
        src_file = src_dir / filename
        if src_file.exists():
            shutil.copy2(src_file, dist_dir / filename)
            print(f"  Copied: {filename}")


def create_readme(dist_dir: Path):
    """Create README file for distribution."""
    readme_content = """=====================================================
    TENNIS BETTING SYSTEM - Quick Start Guide
=====================================================

This installer comes pre-loaded with player data and match
history, so you can start analyzing matches immediately!

QUICK START (3 Steps):
----------------------
1. Run TennisBettingSystem.exe
2. Click "Betfair Tennis" -> Enter credentials -> Capture matches
3. Click "Bet Suggester" -> Find value betting opportunities

That's it! The database is already loaded with ATP/WTA/ITF
players and historical match data.

KEEPING DATA FRESH:
-------------------
- "Quick Refresh" - Updates last 7 days of matches (~2-3 min)
  Use this daily to get recent match results

- "Full Refresh" - Updates 6 months of data (~15-20 min)
  Use this weekly or after a long break

The "Last:" indicator next to the buttons shows when data
was last refreshed.

MAIN FEATURES:
--------------
1. BETFAIR TENNIS
   - Captures live matches and odds from Betfair Exchange
   - Requires Betfair API credentials (free to obtain)
   - Fetches matches for the next 48 hours

2. BET SUGGESTER
   - Shows all upcoming matches with odds
   - Analyzes each match for expected value (EV)
   - Highlights value bets where your edge > 5%
   - Double-click any match for detailed analysis

3. BET TRACKER
   - Records all your placed bets
   - Track Win/Loss results
   - Monitor ROI and performance over time

4. RANKINGS
   - View current ATP and WTA rankings
   - Search for specific players

5. DATABASE
   - Manage player records and aliases
   - Fix duplicate players or name mismatches

BETFAIR API SETUP:
------------------
To capture live odds, you need Betfair API credentials:
1. Log into Betfair -> My Account -> API Access
2. Create an Application Key
3. Enter credentials in Betfair Tennis dialog

DATA LOCATION:
--------------
User data is stored in:
  C:\\Users\\Public\\Documents\\Tennis Betting System\\

This includes your database, bets, and settings.
Multiple Windows users can share the same data.

TROUBLESHOOTING:
----------------
- "Unknown players" during refresh = Lower-ranked ITF players
  not in database. This is normal - only top ~3000 players
  are tracked.

- Matches not showing = Run "Betfair Tennis" to capture
  upcoming matches first.

- Stale data warning = Click "Quick Refresh" to update
  recent match results.

Enjoy and bet responsibly!
"""
    readme_path = dist_dir / "README.txt"
    readme_path.write_text(readme_content)
    print("  Created: README.txt")


def build():
    """Build the Tennis Betting System executable."""
    print("=" * 60)
    print("  TENNIS BETTING SYSTEM - Build Script")
    print("=" * 60)

    # Get paths
    base_dir = Path(__file__).parent
    src_dir = base_dir / "src"
    final_dist_dir = base_dir / "dist" / "TennisBettingSystem"
    installer_output = base_dir / "installer_output"

    # Use temp directory for build to avoid OneDrive locking
    temp_base = Path(tempfile.gettempdir()) / "tennis_betting_build"
    temp_dist = temp_base / "dist"
    temp_build = temp_base / "build"

    # Ensure installer_output directory exists
    installer_output.mkdir(exist_ok=True)

    # Clean temp directory
    print("\n[1/5] Cleaning temporary build directory...")
    robust_remove(temp_base)
    temp_base.mkdir(exist_ok=True)
    temp_dist.mkdir(exist_ok=True)
    temp_build.mkdir(exist_ok=True)

    # Run PyInstaller in temp directory
    print("\n[2/5] Running PyInstaller...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "TennisBettingSystem",
        "--onedir",
        "--windowed",
        "--noconfirm",
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.filedialog",
        "--hidden-import", "tkinter.messagebox",
        "--hidden-import", "tkinter.ttk",
        "--hidden-import", "tkinter.font",
        "--hidden-import", "sqlite3",
        "--hidden-import", "requests",
        "--hidden-import", "certifi",
        "--hidden-import", "platform",
        "--hidden-import", "subprocess",
        "--hidden-import", "json",
        "--hidden-import", "base64",
        "--hidden-import", "hashlib",
        "--hidden-import", "urllib.request",
        "--hidden-import", "http.client",
        "--hidden-import", "socket",
        "--hidden-import", "bs4",
        "--hidden-import", "soupsieve",
        # Collect all selenium and webdriver_manager files
        "--collect-all", "selenium",
        "--collect-all", "webdriver_manager",
        "--collect-all", "trio",
        "--collect-all", "sniffio",
        "--collect-all", "outcome",
        "--collect-all", "attrs",
        "--distpath", str(temp_dist),
        "--workpath", str(temp_build),
        str(src_dir / "main.py")
    ]

    result = subprocess.run(cmd, cwd=str(base_dir))

    if result.returncode != 0:
        print("\nPyInstaller failed!")
        return result.returncode

    temp_app_dir = temp_dist / "TennisBettingSystem"

    # Copy source files to temp dist
    print("\n[3/5] Copying application files...")
    copy_source_files(src_dir, temp_app_dir)
    create_readme(temp_app_dir)

    # Create data and output directories
    (temp_app_dir / "data").mkdir(exist_ok=True)
    (temp_app_dir / "output").mkdir(exist_ok=True)
    print("  Created: data/")
    print("  Created: output/")

    # Copy seed data files (CRITICAL - these are copied to Public Documents on first run)
    # Use the CURRENT database from data/ folder (not the old dist copy)
    # This ensures installers always ship with the latest player data and match history
    current_db = base_dir / "data" / "tennis_betting.db"
    name_mappings = base_dir / "data" / "name_mappings.json"

    if current_db.exists():
        shutil.copy2(current_db, temp_app_dir / "data" / "tennis_betting.db")
        # Show database stats
        import sqlite3
        conn = sqlite3.connect(current_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM players")
        players = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM matches")
        matches = cursor.fetchone()[0]
        conn.close()
        print(f"  Copied: data/tennis_betting.db ({players} players, {matches} matches)")
    else:
        print("  WARNING: Database not found at data/tennis_betting.db!")

    if name_mappings.exists():
        shutil.copy2(name_mappings, temp_app_dir / "data" / "name_mappings.json")
        print("  Copied: data/name_mappings.json (player name mappings)")

    rankings_cache = base_dir / "data" / "rankings_cache.json"
    if rankings_cache.exists():
        shutil.copy2(rankings_cache, temp_app_dir / "data" / "rankings_cache.json")
        print("  Copied: data/rankings_cache.json (ATP/WTA rankings)")

    # Copy credentials.json if it exists
    creds_file = base_dir / "credentials.json"
    if creds_file.exists():
        shutil.copy2(creds_file, temp_app_dir / "credentials.json")
        print("  Copied: credentials.json")

    # Copy Assets folder (contains app icon)
    assets_dir = base_dir / "Assets"
    if assets_dir.exists():
        (temp_app_dir / "Assets").mkdir(exist_ok=True)
        for asset_file in assets_dir.iterdir():
            if asset_file.is_file():
                shutil.copy2(asset_file, temp_app_dir / "Assets" / asset_file.name)
                print(f"  Copied: Assets/{asset_file.name}")

    # Copy from temp to final location
    print("\n[4/5] Copying to final location...")
    robust_remove(final_dist_dir)
    final_dist_dir.parent.mkdir(exist_ok=True)
    shutil.copytree(temp_app_dir, final_dist_dir)
    print(f"  Copied to: {final_dist_dir}")

    # Cleanup temp
    print("\n[5/5] Cleaning up...")
    robust_remove(temp_base)

    # Done
    print("\n" + "=" * 60)
    print("  BUILD SUCCESSFUL!")
    print("=" * 60)
    print(f"\nExecutable location: {final_dist_dir}")
    print(f"Installer output:    {installer_output}")
    print("\n" + "-" * 60)
    print("  NEXT STEPS - Create Installer:")
    print("-" * 60)
    print("  1. Run Inno Setup Compiler on installer.iss")
    print("  2. Find installer in installer_output/")
    print("\n" + "-" * 60)
    print("  WHAT'S INCLUDED:")
    print("-" * 60)
    print("  The installer ships with:")
    print("  - Pre-loaded database (players + match history)")
    print("  - Name mappings for Betfair player matching")
    print("  - Rankings cache (current ATP/WTA rankings)")
    print("  - Users can start analyzing matches immediately!")
    print("\n" + "-" * 60)
    print("  BEFORE BUILDING A NEW RELEASE:")
    print("-" * 60)
    print("  1. Run 'Quick Refresh' or 'Full Refresh' in the app")
    print("     to ensure match data is up to date")
    print("  2. The build script automatically uses data/tennis_betting.db")
    print("  3. Check the player/match counts above are correct")
    print("\n" + "-" * 60)
    print("  USER DATA LOCATION (after install):")
    print("-" * 60)
    print("  C:\\Users\\Public\\Documents\\Tennis Betting System\\data\\")
    print("  - tennis_betting.db    : Database (copied from installer on first run)")
    print("  - name_mappings.json   : Betfair name mappings")
    print("  - rankings_cache.json  : ATP/WTA rankings")
    print("-" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(build())
