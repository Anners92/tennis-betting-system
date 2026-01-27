"""
Betfair Exchange Tennis Capture - Captures match odds from Betfair for tennis.

This script connects to Betfair Exchange API and captures odds for tennis match winner markets.

Usage:
    1. Edit credentials.json in the app folder with your Betfair details
       OR set environment variables:
       - BETFAIR_APP_KEY=your-app-key
       - BETFAIR_USERNAME=your-username
       - BETFAIR_PASSWORD=your-password

    2. Run: python betfair_capture.py

    3. Or use the batch file: run_betfair_tennis.bat
"""

import requests
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import db
from name_matcher import name_matcher
from config import normalize_tournament_name

# Optional: Odds API for Pinnacle comparison
try:
    from odds_api import OddsAPIClient, load_api_key
    ODDS_API_AVAILABLE = bool(load_api_key())
except ImportError:
    ODDS_API_AVAILABLE = False


def get_app_directory() -> str:
    """Get the directory where the app is running from.

    Handles both:
    - Running as a PyInstaller exe (looks next to the .exe)
    - Running as a Python script (looks in project root)
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled exe - use exe location
        return os.path.dirname(sys.executable)
    else:
        # Running as script - use project root (one level up from src)
        src_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.dirname(src_dir)


def load_credentials_from_file() -> Dict[str, str]:
    """Load Betfair credentials from credentials.json file."""
    app_dir = get_app_directory()
    creds_path = os.path.join(app_dir, 'credentials.json')

    if os.path.exists(creds_path):
        try:
            with open(creds_path, 'r') as f:
                creds = json.load(f)
                # Only return if values are actually filled in (not placeholders)
                app_key = creds.get('betfair_app_key', '')
                username = creds.get('betfair_username', '')
                password = creds.get('betfair_password', '')

                if app_key and 'YOUR_' not in app_key:
                    return {
                        'app_key': app_key,
                        'username': username,
                        'password': password
                    }
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read credentials.json: {e}")

    return {}

# Betfair API endpoints
BETFAIR_LOGIN_URL = "https://identitysso.betfair.com/api/login"
BETFAIR_API_URL = "https://api.betfair.com/exchange/betting/rest/v1.0/"
BETFAIR_KEEP_ALIVE_URL = "https://identitysso.betfair.com/api/keepAlive"

# Tennis event type ID
TENNIS_EVENT_TYPE_ID = "2"

# Market type for match winner
MATCH_ODDS_MARKET = "MATCH_ODDS"

# Minimum liquidity (GBP) required to capture odds
# Set to 0 to capture all matches regardless of liquidity
MIN_LIQUIDITY_GBP = 0

# Maximum acceptable odds discrepancy vs Pinnacle (15% = 0.15)
# Set to 1.0 (100%) to effectively disable skipping
MAX_ODDS_DISCREPANCY = 1.0


class BetfairTennisCapture:
    """Capture tennis odds from Betfair Exchange."""

    def __init__(self, app_key: str = None, username: str = None, password: str = None):
        """Initialize with credentials.

        Priority order:
        1. Passed arguments
        2. credentials.json file
        3. Environment variables
        """
        # Try loading from credentials.json first
        file_creds = load_credentials_from_file()

        self.app_key = app_key or file_creds.get('app_key') or os.environ.get('BETFAIR_APP_KEY', '')
        self.username = username or file_creds.get('username') or os.environ.get('BETFAIR_USERNAME', '')
        self.password = password or file_creds.get('password') or os.environ.get('BETFAIR_PASSWORD', '')

        self.session_token = None
        self.session = requests.Session()

        if not all([self.app_key, self.username, self.password]):
            print("WARNING: Missing Betfair credentials!")
            print("Edit credentials.json in the app folder, or set environment variables.")

    def login(self) -> bool:
        """Login to Betfair and get session token."""
        if not all([self.app_key, self.username, self.password]):
            print("Cannot login: Missing credentials")
            return False

        headers = {
            'X-Application': self.app_key,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }

        data = {
            'username': self.username,
            'password': self.password
        }

        try:
            print(f"Attempting login for {self.username}...")
            response = self.session.post(BETFAIR_LOGIN_URL, headers=headers, data=data)

            content_type = response.headers.get('Content-Type', '')
            if 'json' not in content_type.lower():
                print(f"Unexpected content type: {content_type}")
                return False

            result = response.json()

            if result.get('status') == 'SUCCESS':
                self.session_token = result.get('token')
                print(f"Logged in successfully!")
                return True
            else:
                print(f"Login failed: {result.get('error', result)}")
                return False

        except Exception as e:
            print(f"Login error: {e}")
            return False

    def _api_request(self, endpoint: str, params: dict) -> Optional[dict]:
        """Make an API request to Betfair."""
        if not self.session_token:
            print("Not logged in!")
            return None

        headers = {
            'X-Application': self.app_key,
            'X-Authentication': self.session_token,
            'Content-Type': 'application/json'
        }

        url = BETFAIR_API_URL + endpoint + "/"

        try:
            response = self.session.post(url, headers=headers, json=params)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"API error {response.status_code}: {response.text}")
                return None

        except Exception as e:
            print(f"API request error: {e}")
            return None

    def get_tennis_events(self, hours_ahead: int = 48) -> List[Dict]:
        """Get upcoming tennis events."""
        now = datetime.utcnow()
        from_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        to_time = (now + timedelta(hours=hours_ahead)).strftime("%Y-%m-%dT%H:%M:%SZ")

        params = {
            "filter": {
                "eventTypeIds": [TENNIS_EVENT_TYPE_ID],
                "marketStartTime": {
                    "from": from_time,
                    "to": to_time
                }
            }
        }

        result = self._api_request("listEvents", params)

        if result:
            events = []
            for item in result:
                event = item.get('event', {})
                events.append({
                    'id': event.get('id'),
                    'name': event.get('name'),
                    'country_code': event.get('countryCode'),
                    'timezone': event.get('timezone'),
                    'open_date': event.get('openDate'),
                    'market_count': item.get('marketCount', 0)
                })
            return events

        return []

    def get_tennis_competitions(self) -> List[Dict]:
        """Get all tennis competitions (tournaments)."""
        params = {
            "filter": {
                "eventTypeIds": [TENNIS_EVENT_TYPE_ID]
            }
        }

        result = self._api_request("listCompetitions", params)

        if result:
            competitions = []
            for item in result:
                comp = item.get('competition', {})
                competitions.append({
                    'id': comp.get('id'),
                    'name': comp.get('name'),
                    'region': comp.get('region'),
                    'market_count': item.get('marketCount', 0)
                })
            return sorted(competitions, key=lambda x: -x['market_count'])

        return []

    def get_match_odds_markets(self, event_id: str = None, competition_id: str = None,
                                hours_ahead: int = 48) -> List[Dict]:
        """Get match odds markets for tennis matches."""
        now = datetime.utcnow()
        from_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        to_time = (now + timedelta(hours=hours_ahead)).strftime("%Y-%m-%dT%H:%M:%SZ")

        filter_params = {
            "eventTypeIds": [TENNIS_EVENT_TYPE_ID],
            "marketTypeCodes": [MATCH_ODDS_MARKET],
            "marketStartTime": {
                "from": from_time,
                "to": to_time
            }
        }

        if event_id:
            filter_params["eventIds"] = [event_id]

        if competition_id:
            filter_params["competitionIds"] = [competition_id]

        params = {
            "filter": filter_params,
            "marketProjection": ["RUNNER_DESCRIPTION", "MARKET_START_TIME", "EVENT", "COMPETITION"],
            "maxResults": "1000",
            "sort": "FIRST_TO_START"
        }

        result = self._api_request("listMarketCatalogue", params)

        if result:
            markets = []
            for market in result:
                runners = []
                for runner in market.get('runners', []):
                    runners.append({
                        'selection_id': runner.get('selectionId'),
                        'name': runner.get('runnerName'),
                        'sort_priority': runner.get('sortPriority')
                    })

                # Only include markets with exactly 2 runners (tennis match)
                if len(runners) == 2:
                    event = market.get('event', {})
                    competition = market.get('competition', {})

                    markets.append({
                        'market_id': market.get('marketId'),
                        'market_name': market.get('marketName'),
                        'market_start_time': market.get('marketStartTime'),
                        'event_id': event.get('id'),
                        'event_name': event.get('name'),
                        'competition_id': competition.get('id'),
                        'competition_name': competition.get('name'),
                        'runners': runners
                    })
            return markets

        return []

    def get_market_odds(self, market_ids: List[str]) -> Dict[str, Dict]:
        """Get current odds for multiple markets."""
        if not market_ids:
            return {}

        # Betfair limits to 40 markets per request
        all_odds = {}

        for i in range(0, len(market_ids), 40):
            batch = market_ids[i:i+40]

            params = {
                "marketIds": batch,
                "priceProjection": {
                    "priceData": ["EX_BEST_OFFERS"],
                    "virtualise": True
                }
            }

            result = self._api_request("listMarketBook", params)

            if result:
                for market in result:
                    market_id = market.get('marketId')
                    runners_odds = {}

                    for runner in market.get('runners', []):
                        sel_id = runner.get('selectionId')
                        back_prices = runner.get('ex', {}).get('availableToBack', [])
                        lay_prices = runner.get('ex', {}).get('availableToLay', [])

                        best_back = back_prices[0] if back_prices else {}
                        best_lay = lay_prices[0] if lay_prices else {}

                        runners_odds[sel_id] = {
                            'back_odds': best_back.get('price'),
                            'back_size': best_back.get('size'),
                            'lay_odds': best_lay.get('price'),
                            'lay_size': best_lay.get('size'),
                            'status': runner.get('status'),
                            'total_matched': runner.get('totalMatched', 0)
                        }

                    all_odds[market_id] = {
                        'status': market.get('status'),
                        'inplay': market.get('inplay', False),
                        'total_matched': market.get('totalMatched', 0),
                        'runners': runners_odds
                    }

            time.sleep(0.2)  # Rate limiting

        return all_odds

    def capture_all_tennis_matches(self, hours_ahead: int = 48,
                                    competition_filter: str = None) -> List[Dict]:
        """Capture all tennis match odds."""
        if not self.login():
            return []

        print(f"\nFetching tennis matches in next {hours_ahead} hours...")

        # Get all match odds markets
        markets = self.get_match_odds_markets(hours_ahead=hours_ahead)
        print(f"Found {len(markets)} tennis matches")

        if not markets:
            return []

        # Get all market IDs
        market_ids = [m['market_id'] for m in markets]

        # Fetch odds for all markets
        print("Fetching odds...")
        all_odds = self.get_market_odds(market_ids)

        # Fetch Pinnacle odds for comparison (if API configured)
        pinnacle_matches = []
        odds_api_client = None
        if ODDS_API_AVAILABLE:
            print("Fetching Pinnacle odds for comparison...")
            try:
                odds_api_client = OddsAPIClient()
                pinnacle_matches = odds_api_client.get_tennis_odds()
                print(f"Pinnacle: {len(pinnacle_matches)} matches available for comparison")
            except Exception as e:
                print(f"Warning: Could not fetch Pinnacle odds: {e}")

        # Combine market info with odds
        captured = []
        skipped_inplay = 0
        skipped_no_odds = 0
        for market in markets:
            market_id = market['market_id']
            odds_data = all_odds.get(market_id, {})

            # Skip in-play matches
            if odds_data.get('inplay', False):
                skipped_inplay += 1
                continue

            # Apply competition filter if specified
            comp_name = market.get('competition_name', '')
            if competition_filter and competition_filter.lower() not in comp_name.lower():
                continue

            runners = market['runners']
            if len(runners) != 2:
                continue

            # Sort runners by sort_priority to ensure consistent player ordering
            # This prevents odds from being swapped between captures
            sorted_runners = sorted(runners, key=lambda r: r.get('sort_priority', 0))
            p1 = sorted_runners[0]
            p2 = sorted_runners[1]

            # Skip doubles matches (names contain "/")
            if '/' in p1['name'] or '/' in p2['name']:
                continue

            p1_odds_data = odds_data.get('runners', {}).get(p1['selection_id'], {})
            p2_odds_data = odds_data.get('runners', {}).get(p2['selection_id'], {})

            p1_odds = p1_odds_data.get('back_odds')
            p2_odds = p2_odds_data.get('back_odds')

            if not p1_odds or not p2_odds:
                skipped_no_odds += 1
                print(f"  SKIPPED (no odds): {p1['name']} vs {p2['name']} - P1 odds: {p1_odds}, P2 odds: {p2_odds}")
                continue

            # Check liquidity - skip thin markets with unreliable prices
            p1_liquidity = p1_odds_data.get('back_size', 0) or 0
            p2_liquidity = p2_odds_data.get('back_size', 0) or 0

            # Log low liquidity matches but don't skip them
            min_liq = min(p1_liquidity, p2_liquidity)
            if min_liq < 100:  # Still flag low liquidity for info
                print(f"  LOW LIQUIDITY: {p1['name']} ({p1_odds:.2f}, £{p1_liquidity:.0f}) vs {p2['name']} ({p2_odds:.2f}, £{p2_liquidity:.0f})")
            # Continue to capture regardless of liquidity

            # Compare against Pinnacle odds (if available)
            pinnacle_comparison = None
            if odds_api_client and pinnacle_matches:
                comparison = odds_api_client.compare_odds(
                    p1['name'], p2['name'],
                    p1_odds, p2_odds,
                    threshold=MAX_ODDS_DISCREPANCY
                )
                pinnacle_comparison = comparison

                # Show Pinnacle comparison info but don't skip any matches
                if comparison.get('recommendation') == 'SKIP':
                    pin_odds = comparison.get('pinnacle_odds')
                    if pin_odds:
                        print(f"  WARNING (BF < PIN): {p1['name']} BF:{p1_odds:.2f} vs PIN:{pin_odds[0]:.2f} | {p2['name']} BF:{p2_odds:.2f} vs PIN:{pin_odds[1]:.2f} - {comparison.get('warning')}")
                    # Don't skip - continue to capture
                elif comparison.get('recommendation') == 'CAUTION':
                    pin_odds = comparison.get('pinnacle_odds')
                    if pin_odds:
                        print(f"  CAUTION: {p1['name']} BF:{p1_odds:.2f} vs PIN:{pin_odds[0]:.2f} | {p2['name']} BF:{p2_odds:.2f} vs PIN:{pin_odds[1]:.2f} - {comparison.get('warning')}")
                elif comparison.get('note'):
                    # Betfair offering better odds than Pinnacle - highlight as good value
                    pin_odds = comparison.get('pinnacle_odds')
                    if pin_odds:
                        print(f"  GOOD VALUE: {p1['name']} BF:{p1_odds:.2f} vs PIN:{pin_odds[0]:.2f} | {p2['name']} BF:{p2_odds:.2f} vs PIN:{pin_odds[1]:.2f} - {comparison.get('note')}")

            match_data = {
                'market_id': market_id,
                'event_id': market.get('event_id'),
                'event_name': market.get('event_name'),
                'competition_name': comp_name,
                'market_start_time': market.get('market_start_time'),
                'player1_name': p1['name'],
                'player2_name': p2['name'],
                'player1_odds': p1_odds,
                'player2_odds': p2_odds,
                'player1_liquidity': p1_liquidity,
                'player2_liquidity': p2_liquidity,
                'total_matched': odds_data.get('total_matched', 0),
                'captured_at': datetime.utcnow().isoformat(),
                'surface': self._guess_surface(comp_name, market.get('market_start_time', '')[:10]),
                'pinnacle_p1_odds': (pinnacle_comparison.get('pinnacle_odds') or [None, None])[0] if pinnacle_comparison else None,
                'pinnacle_p2_odds': (pinnacle_comparison.get('pinnacle_odds') or [None, None])[1] if pinnacle_comparison else None,
            }

            captured.append(match_data)

            # Print match info
            print(f"  {p1['name']} ({p1_odds:.2f}) vs {p2['name']} ({p2_odds:.2f}) - {comp_name}")

        # Print summary
        print(f"\n--- CAPTURE SUMMARY ---")
        print(f"Total markets found: {len(markets)}")
        print(f"Captured: {len(captured)}")
        print(f"Skipped - In-play: {skipped_inplay}")
        print(f"Skipped - No odds: {skipped_no_odds}")
        print(f"Skipped - Other (doubles, filter, etc.): {len(markets) - len(captured) - skipped_inplay - skipped_no_odds}")
        print(f"-----------------------\n")

        return captured

    def _guess_surface(self, competition_name: str, date_str: str = None) -> str:
        """Guess surface from competition name using centralized detection."""
        from config import get_tournament_surface
        return get_tournament_surface(competition_name, date_str)

    def _create_missing_player(self, player_name: str) -> Optional[Dict]:
        """Create a new player entry for a player not in the database."""
        # Parse name into first/last
        parts = player_name.strip().split()
        if len(parts) >= 2:
            first_name = parts[0]
            last_name = ' '.join(parts[1:])
        else:
            first_name = player_name
            last_name = ''

        # Generate a unique ID using hash of name (negative to distinguish from ATP IDs)
        # This ensures same player always gets same ID, avoiding collisions
        import hashlib
        name_hash = int(hashlib.md5(player_name.lower().encode()).hexdigest()[:8], 16)
        player_id = -(name_hash % 900000 + 100000)  # Range: -100000 to -999999

        player_data = {
            'id': player_id,
            'name': player_name,
            'first_name': first_name,
            'last_name': last_name,
            'country': '',
            'hand': 'U',
            'height': None,
            'dob': None,
        }

        try:
            db.insert_player(player_data)
            print(f"  Added missing player: {player_name}")
            return player_data
        except Exception as e:
            print(f"  Could not add player {player_name}: {e}")
            return None

    def save_to_database(self, captured_matches: List[Dict]) -> int:
        """Save captured matches to database as upcoming matches."""
        imported = 0
        players_added = 0
        player_cache = {}  # Cache player lookups to avoid repeated DB queries

        for match in captured_matches:
            # Try to find player IDs using name_matcher first, then direct lookup
            p1_name = match['player1_name']
            p2_name = match['player2_name']

            # Check cache first for player 1
            if p1_name in player_cache:
                p1 = player_cache[p1_name]
            else:
                p1_mapped_id = name_matcher.get_db_id(p1_name)
                p1 = None
                if p1_mapped_id:
                    p1 = db.get_player(p1_mapped_id)
                if not p1:
                    p1 = db.get_player_by_name(p1_name)
                if not p1:
                    p1 = self._create_missing_player(p1_name)
                    if p1:
                        players_added += 1
                player_cache[p1_name] = p1

            # Check cache first for player 2
            if p2_name in player_cache:
                p2 = player_cache[p2_name]
            else:
                p2_mapped_id = name_matcher.get_db_id(p2_name)
                p2 = None
                if p2_mapped_id:
                    p2 = db.get_player(p2_mapped_id)
                if not p2:
                    p2 = db.get_player_by_name(p2_name)
                if not p2:
                    p2 = self._create_missing_player(p2_name)
                    if p2:
                        players_added += 1
                player_cache[p2_name] = p2

            # Parse date and time from market_start_time
            start_time = match.get('market_start_time', '')
            if start_time:
                try:
                    # Keep full datetime (e.g., "2026-01-19T10:30:00")
                    # Convert from ISO format to a cleaner format
                    match_date = start_time[:19].replace('T', ' ')  # "2026-01-19 10:30:00"
                except:
                    match_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            else:
                match_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            match_data = {
                'tournament': normalize_tournament_name(match.get('competition_name', '')),
                'date': match_date,
                'surface': match.get('surface', 'Hard'),
                'round': '',
                'player1_id': p1['id'] if p1 else None,
                'player2_id': p2['id'] if p2 else None,
                'player1_name': match['player1_name'],
                'player2_name': match['player2_name'],
                'player1_odds': match['player1_odds'],
                'player2_odds': match['player2_odds'],
                'player1_liquidity': match.get('player1_liquidity'),
                'player2_liquidity': match.get('player2_liquidity'),
                'total_matched': match.get('total_matched'),
            }

            try:
                db.add_upcoming_match(match_data)
                imported += 1
            except Exception as e:
                print(f"Error importing match: {e}")

        if players_added > 0:
            print(f"\nAdded {players_added} new players to database")
        print(f"Saved {imported} matches to database")

        return imported


def run_capture(interval_minutes: int = 0, hours_ahead: int = 48, competition: str = None):
    """Run tennis odds capture."""
    print("=" * 60)
    print("BETFAIR TENNIS ODDS CAPTURE")
    print("=" * 60)

    capturer = BetfairTennisCapture()

    if not capturer.app_key:
        print("\nERROR: No API key found!")
        print("\nSet environment variables:")
        print("  BETFAIR_APP_KEY=your-app-key")
        print("  BETFAIR_USERNAME=your-username")
        print("  BETFAIR_PASSWORD=your-password")
        return

    while True:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting capture...")

        try:
            matches = capturer.capture_all_tennis_matches(hours_ahead, competition)

            if matches:
                capturer.save_to_database(matches)
                print(f"Captured {len(matches)} tennis matches")
            else:
                print("No matches captured this run")

        except Exception as e:
            print(f"Error during capture: {e}")
            import traceback
            traceback.print_exc()

        if interval_minutes <= 0:
            print("\nSingle capture completed.")
            break

        print(f"\nSleeping for {interval_minutes} minutes...")
        time.sleep(interval_minutes * 60)


def list_competitions():
    """List all available tennis competitions."""
    print("=" * 60)
    print("BETFAIR TENNIS COMPETITIONS")
    print("=" * 60)

    capturer = BetfairTennisCapture()

    if not capturer.login():
        print("Failed to login!")
        return

    competitions = capturer.get_tennis_competitions()

    print(f"\nFound {len(competitions)} competitions:\n")
    for comp in competitions[:50]:
        print(f"  {comp['name']:40} ({comp['market_count']} markets)")


# ============================================================================
# BETFAIR UI
# ============================================================================

import tkinter as tk
from tkinter import ttk, messagebox
import threading

# Import colors from central config
from config import UI_COLORS


class BetfairCaptureUI:
    """Tkinter UI for Betfair Tennis Capture."""

    def __init__(self, parent: tk.Tk = None):
        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()

        self.root.title("Betfair Tennis - Live Odds Capture")
        self.root.state('zoomed')  # Launch maximized
        self.root.configure(bg=UI_COLORS["bg_dark"])

        self.capturer = None
        self.is_capturing = False

        self._setup_styles()
        self._build_ui()
        self._load_credentials()
        self._refresh_matches()

        # Auto-capture if credentials are already saved
        self.root.after(100, self._auto_capture_if_ready)

    def _setup_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure("Dark.TFrame", background=UI_COLORS["bg_dark"])
        style.configure("Card.TFrame", background=UI_COLORS["bg_medium"])
        style.configure("Dark.TLabel", background=UI_COLORS["bg_dark"],
                       foreground=UI_COLORS["text_primary"], font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=UI_COLORS["bg_dark"],
                       foreground=UI_COLORS["text_primary"], font=("Segoe UI", 16, "bold"))
        style.configure("Card.TLabel", background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["text_primary"], font=("Segoe UI", 10))
        style.configure("Status.TLabel", background=UI_COLORS["bg_dark"],
                       foreground=UI_COLORS["accent"], font=("Segoe UI", 10))

        # Treeview style
        style.configure("Treeview",
                       background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["text_primary"],
                       fieldbackground=UI_COLORS["bg_medium"],
                       font=("Segoe UI", 9))
        style.configure("Treeview.Heading",
                       background=UI_COLORS["bg_light"],
                       foreground=UI_COLORS["text_primary"],
                       font=("Segoe UI", 9, "bold"))

    def _build_ui(self):
        """Build the main UI."""
        main_frame = ttk.Frame(self.root, style="Dark.TFrame", padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        header_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(header_frame, text="Betfair Tennis Capture", style="Title.TLabel").pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="Not connected")
        status_label = ttk.Label(header_frame, textvariable=self.status_var, style="Status.TLabel")
        status_label.pack(side=tk.RIGHT)

        # Credentials frame
        cred_frame = ttk.Frame(main_frame, style="Card.TFrame", padding=15)
        cred_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(cred_frame, text="Betfair Credentials", style="Card.TLabel",
                  font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=6, sticky=tk.W, pady=(0, 10))

        # App Key
        ttk.Label(cred_frame, text="App Key:", style="Card.TLabel").grid(row=1, column=0, padx=5, pady=5, sticky=tk.E)
        self.app_key_var = tk.StringVar()
        self.app_key_entry = ttk.Entry(cred_frame, textvariable=self.app_key_var, width=25)
        self.app_key_entry.grid(row=1, column=1, padx=5, pady=5)

        # Username
        ttk.Label(cred_frame, text="Username:", style="Card.TLabel").grid(row=1, column=2, padx=5, pady=5, sticky=tk.E)
        self.username_var = tk.StringVar()
        self.username_entry = ttk.Entry(cred_frame, textvariable=self.username_var, width=20)
        self.username_entry.grid(row=1, column=3, padx=5, pady=5)

        # Password
        ttk.Label(cred_frame, text="Password:", style="Card.TLabel").grid(row=1, column=4, padx=5, pady=5, sticky=tk.E)
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(cred_frame, textvariable=self.password_var, width=20, show="*")
        self.password_entry.grid(row=1, column=5, padx=5, pady=5)

        # Help button
        help_btn = tk.Button(cred_frame, text="?", font=("Segoe UI", 9, "bold"),
                            fg="white", bg="#6366f1", width=2, relief=tk.FLAT,
                            cursor="hand2", command=self._show_credentials_help)
        help_btn.grid(row=1, column=6, padx=(10, 5), pady=5)

        # Capture options
        options_frame = ttk.Frame(main_frame, style="Card.TFrame", padding=15)
        options_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(options_frame, text="Hours ahead:", style="Card.TLabel").pack(side=tk.LEFT, padx=5)
        self.hours_var = tk.StringVar(value="48")
        hours_spin = ttk.Spinbox(options_frame, textvariable=self.hours_var, from_=1, to=168, width=5)
        hours_spin.pack(side=tk.LEFT, padx=5)

        ttk.Label(options_frame, text="Competition filter:", style="Card.TLabel").pack(side=tk.LEFT, padx=(20, 5))
        self.competition_var = tk.StringVar()
        comp_entry = ttk.Entry(options_frame, textvariable=self.competition_var, width=25)
        comp_entry.pack(side=tk.LEFT, padx=5)

        # Buttons
        btn_frame = ttk.Frame(options_frame, style="Card.TFrame")
        btn_frame.pack(side=tk.RIGHT)

        self.capture_btn = tk.Button(
            btn_frame,
            text="Capture Matches",
            font=("Segoe UI", 10, "bold"),
            fg="white",
            bg=UI_COLORS["success"],
            activebackground="#45a049",
            relief=tk.FLAT,
            cursor="hand2",
            command=self._start_capture,
            padx=15,
            pady=5
        )
        self.capture_btn.pack(side=tk.LEFT, padx=5)

        refresh_btn = tk.Button(
            btn_frame,
            text="Refresh List",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["accent"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._refresh_matches,
            padx=15,
            pady=5
        )
        refresh_btn.pack(side=tk.LEFT, padx=5)

        clear_btn = tk.Button(
            btn_frame,
            text="Clear All",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["danger"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._clear_matches,
            padx=15,
            pady=5
        )
        clear_btn.pack(side=tk.LEFT, padx=5)

        # Matches list
        list_frame = ttk.Frame(main_frame, style="Card.TFrame", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(list_frame, text="Captured Matches", style="Card.TLabel",
                  font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(0, 10))

        # Treeview
        columns = ("time", "tournament", "player1", "p1_odds", "player2", "p2_odds", "surface")
        self.matches_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=20)

        self.matches_tree.heading("time", text="Time")
        self.matches_tree.heading("tournament", text="Tournament")
        self.matches_tree.heading("player1", text="Player 1")
        self.matches_tree.heading("p1_odds", text="Odds")
        self.matches_tree.heading("player2", text="Player 2")
        self.matches_tree.heading("p2_odds", text="Odds")
        self.matches_tree.heading("surface", text="Surface")

        self.matches_tree.column("time", width=80)
        self.matches_tree.column("tournament", width=180)
        self.matches_tree.column("player1", width=150)
        self.matches_tree.column("p1_odds", width=60)
        self.matches_tree.column("player2", width=150)
        self.matches_tree.column("p2_odds", width=60)
        self.matches_tree.column("surface", width=70)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.matches_tree.yview)
        self.matches_tree.configure(yscrollcommand=scrollbar.set)

        self.matches_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Summary
        self.summary_var = tk.StringVar(value="Enter credentials and click 'Capture Matches' to fetch live odds from Betfair")
        summary_label = ttk.Label(main_frame, textvariable=self.summary_var, style="Dark.TLabel")
        summary_label.pack(anchor=tk.W, pady=(10, 0))

    def _load_credentials(self):
        """Load saved credentials from credentials.json file or environment variables."""
        # First try to load from credentials.json file
        file_creds = load_credentials_from_file()
        if file_creds:
            # load_credentials_from_file returns keys: 'app_key', 'username', 'password'
            self.app_key_var.set(file_creds.get('app_key', ''))
            self.username_var.set(file_creds.get('username', ''))
            self.password_var.set(file_creds.get('password', ''))
            return

        # Fall back to environment variables
        self.app_key_var.set(os.environ.get('BETFAIR_APP_KEY', ''))
        self.username_var.set(os.environ.get('BETFAIR_USERNAME', ''))
        self.password_var.set(os.environ.get('BETFAIR_PASSWORD', ''))

    def _show_credentials_help(self):
        """Show help dialog for getting Betfair API credentials."""
        help_dialog = tk.Toplevel(self.root)
        help_dialog.title("How to Get Betfair API Credentials")
        help_dialog.geometry("550x480")
        help_dialog.configure(bg=UI_COLORS["bg_dark"])
        help_dialog.transient(self.root)
        help_dialog.grab_set()

        frame = tk.Frame(help_dialog, bg=UI_COLORS["bg_dark"], padx=25, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Title
        tk.Label(frame, text="Getting Your Betfair App Key",
                font=("Segoe UI", 14, "bold"), bg=UI_COLORS["bg_dark"],
                fg=UI_COLORS["text_primary"]).pack(anchor=tk.W)

        tk.Label(frame, text="Follow these steps to get your API credentials:",
                font=("Segoe UI", 10), bg=UI_COLORS["bg_dark"],
                fg=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=(5, 15))

        # Steps
        steps = [
            ("1. Create a Betfair Account", "Go to betfair.com and create an account if you don't have one."),
            ("2. Go to Developer Portal", "Visit: https://developer.betfair.com"),
            ("3. Log In", "Sign in with your Betfair username and password."),
            ("4. Create Application", "Click 'My Account' > 'Manage Apps' > 'Create New App'"),
            ("5. Get Your App Key", "Give your app a name (e.g., 'Tennis Betting').\nYour App Key will be generated - copy it!"),
            ("6. Enter Credentials Here", "App Key: The key from step 5\nUsername: Your Betfair username\nPassword: Your Betfair password"),
        ]

        for title, desc in steps:
            step_frame = tk.Frame(frame, bg=UI_COLORS["bg_medium"], padx=10, pady=8)
            step_frame.pack(fill=tk.X, pady=3)

            tk.Label(step_frame, text=title, font=("Segoe UI", 10, "bold"),
                    bg=UI_COLORS["bg_medium"], fg=UI_COLORS["accent"]).pack(anchor=tk.W)
            tk.Label(step_frame, text=desc, font=("Segoe UI", 9),
                    bg=UI_COLORS["bg_medium"], fg=UI_COLORS["text_secondary"],
                    justify=tk.LEFT).pack(anchor=tk.W)

        # Note
        tk.Label(frame, text="Note: The API is free to use. You just need a funded Betfair account.",
                font=("Segoe UI", 9, "italic"), bg=UI_COLORS["bg_dark"],
                fg=UI_COLORS["text_muted"]).pack(anchor=tk.W, pady=(15, 10))

        # Close button
        close_btn = tk.Button(frame, text="Got It", font=("Segoe UI", 10, "bold"),
                             fg="white", bg=UI_COLORS["success"], relief=tk.FLAT,
                             cursor="hand2", command=help_dialog.destroy, padx=20, pady=5)
        close_btn.pack(pady=(5, 0))

    def _refresh_matches(self):
        """Refresh the matches list from database."""
        self.matches_tree.delete(*self.matches_tree.get_children())

        matches = db.get_upcoming_matches()
        for match in matches:
            start_time = match.get('date', '')
            if len(start_time) > 10:
                start_time = start_time[11:16]  # Extract time portion

            self.matches_tree.insert("", tk.END, values=(
                start_time,
                match.get('tournament', '')[:25],
                match.get('player1_name', ''),
                f"{match.get('player1_odds', 0):.2f}" if match.get('player1_odds') else '-',
                match.get('player2_name', ''),
                f"{match.get('player2_odds', 0):.2f}" if match.get('player2_odds') else '-',
                match.get('surface', 'Hard'),
            ))

        self.summary_var.set(f"Showing {len(matches)} matches in database")

    def _auto_capture_if_ready(self):
        """Auto-start capture if credentials are configured AND no recent matches exist."""
        app_key = self.app_key_var.get().strip()
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        if not all([app_key, username, password]):
            return

        # Check if we already have recent matches (from main app startup)
        matches = db.get_upcoming_matches()
        if matches and len(matches) > 10:
            # Already have matches from startup capture, don't duplicate
            self.status_var.set(f"Loaded {len(matches)} matches from database")
            return

        # No matches or very few - do a capture
        self._start_capture()

    def _start_capture(self):
        """Start capturing matches from Betfair."""
        if self.is_capturing:
            return

        app_key = self.app_key_var.get().strip()
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        if not all([app_key, username, password]):
            messagebox.showwarning("Missing Credentials", "Please enter App Key, Username, and Password")
            return

        self.is_capturing = True
        self.capture_btn.configure(state=tk.DISABLED, text="Capturing...")
        self.status_var.set("Connecting to Betfair...")

        # Run capture in background thread
        thread = threading.Thread(target=self._do_capture, args=(app_key, username, password))
        thread.daemon = True
        thread.start()

    def _do_capture(self, app_key: str, username: str, password: str):
        """Perform the capture in background thread."""
        try:
            hours = int(self.hours_var.get())
            competition = self.competition_var.get().strip() or None

            capturer = BetfairTennisCapture(app_key, username, password)

            if not capturer.login():
                self.root.after(0, lambda: self._capture_error("Login failed. Check your credentials."))
                return

            self.root.after(0, lambda: self.status_var.set("Fetching matches..."))

            matches = capturer.capture_all_tennis_matches(hours, competition)

            if matches:
                count = capturer.save_to_database(matches)
                self.root.after(0, lambda: self._capture_complete(len(matches), count))
            else:
                self.root.after(0, lambda: self._capture_complete(0, 0))

        except Exception as e:
            err_msg = str(e)
            self.root.after(0, lambda msg=err_msg: self._capture_error(msg))

    def _capture_complete(self, captured: int, saved: int):
        """Handle capture completion."""
        self.is_capturing = False
        self.capture_btn.configure(state=tk.NORMAL, text="Capture Matches")
        self.status_var.set(f"Connected - Last capture: {captured} matches")
        self.summary_var.set(f"Captured {captured} matches, saved {saved} to database")
        self._refresh_matches()

    def _capture_error(self, error: str):
        """Handle capture error."""
        self.is_capturing = False
        self.capture_btn.configure(state=tk.NORMAL, text="Capture Matches")
        self.status_var.set("Connection failed")
        messagebox.showerror("Capture Error", error)

    def _clear_matches(self):
        """Clear all upcoming matches."""
        if messagebox.askyesno("Confirm", "Clear all captured matches from database?"):
            db.clear_upcoming_matches()
            self._refresh_matches()
            self.summary_var.set("All matches cleared")

    def run(self):
        """Run the UI."""
        self.root.mainloop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Betfair Tennis Odds Capture')
    parser.add_argument('--key', help='Betfair App Key')
    parser.add_argument('--user', help='Betfair Username')
    parser.add_argument('--pass', dest='password', help='Betfair Password')
    parser.add_argument('--interval', type=int, default=0, help='Capture interval in minutes (0 for single run)')
    parser.add_argument('--hours', type=int, default=48, help='Hours ahead to look for matches')
    parser.add_argument('--competition', help='Filter by competition name (e.g., "Australian Open")')
    parser.add_argument('--list-competitions', action='store_true', help='List all tennis competitions')

    args = parser.parse_args()

    # Set environment variables if provided via command line
    if args.key:
        os.environ['BETFAIR_APP_KEY'] = args.key
    if args.user:
        os.environ['BETFAIR_USERNAME'] = args.user
    if args.password:
        os.environ['BETFAIR_PASSWORD'] = args.password

    if args.list_competitions:
        list_competitions()
    else:
        run_capture(args.interval, args.hours, args.competition)
