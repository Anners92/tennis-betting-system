"""
The Odds API Integration - Compare odds across bookmakers including Pinnacle.

Free tier: 500 requests/month
Sign up at: https://the-odds-api.com/

Usage:
    1. Get your API key from https://the-odds-api.com/
    2. Add to credentials.json: "odds_api_key": "YOUR_KEY"
    3. Use compare_odds() to validate Betfair prices
"""

import requests
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher

# API Configuration
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# Tennis sport keys on The Odds API
TENNIS_SPORTS = [
    "tennis_atp_australian_open",
    "tennis_atp_french_open",
    "tennis_atp_us_open",
    "tennis_atp_wimbledon",
    "tennis_wta_australian_open",
    "tennis_wta_french_open",
    "tennis_wta_us_open",
    "tennis_wta_wimbledon",
]

# Bookmakers to compare (Pinnacle is the sharp book)
SHARP_BOOKMAKERS = ["pinnacle", "betfair_ex_eu"]
ALL_BOOKMAKERS = ["pinnacle", "bet365", "unibet_eu", "betfair_ex_eu", "williamhill"]


def get_app_directory() -> str:
    """Get the directory where the app is running from."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        src_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.dirname(src_dir)


def load_api_key() -> Optional[str]:
    """Load The Odds API key from credentials.json."""
    app_dir = get_app_directory()
    creds_path = os.path.join(app_dir, 'credentials.json')

    if os.path.exists(creds_path):
        try:
            with open(creds_path, 'r') as f:
                creds = json.load(f)
                return creds.get('odds_api_key', '')
        except (json.JSONDecodeError, IOError):
            pass

    return os.environ.get('ODDS_API_KEY', '')


class OddsAPIClient:
    """Client for The Odds API."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or load_api_key()
        self.requests_used = 0
        self.requests_remaining = None
        self._cache = {}
        self._cache_time = {}
        self.cache_duration = timedelta(minutes=15)

    def _make_request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        """Make API request and track usage."""
        if not self.api_key:
            print("ERROR: No Odds API key configured")
            print("Get your free key at: https://the-odds-api.com/")
            return None

        params = params or {}
        params['apiKey'] = self.api_key

        url = f"{ODDS_API_BASE}/{endpoint}"

        try:
            response = requests.get(url, params=params, timeout=30)

            # Track API usage from headers
            self.requests_used = response.headers.get('x-requests-used', self.requests_used)
            self.requests_remaining = response.headers.get('x-requests-remaining')

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                print("ERROR: Invalid Odds API key")
                return None
            elif response.status_code == 429:
                print("ERROR: Odds API rate limit exceeded")
                return None
            else:
                print(f"Odds API error {response.status_code}: {response.text}")
                return None

        except Exception as e:
            print(f"Odds API request error: {e}")
            return None

    def get_sports(self) -> List[Dict]:
        """Get list of available sports."""
        return self._make_request("sports") or []

    def get_tennis_sports(self) -> List[Dict]:
        """Get list of tennis sports/tournaments with active markets."""
        sports = self.get_sports()
        return [s for s in sports if 'tennis' in s.get('key', '').lower() and s.get('active')]

    def get_tennis_odds(self, regions: str = "eu,uk", bookmakers: List[str] = None) -> List[Dict]:
        """
        Get odds for all tennis matches from multiple bookmakers.

        Args:
            regions: Comma-separated regions (us, uk, eu, au)
            bookmakers: List of specific bookmakers to include

        Returns:
            List of matches with odds from each bookmaker
        """
        # Check cache first
        cache_key = f"tennis_odds_{regions}"
        if cache_key in self._cache:
            cache_age = datetime.now() - self._cache_time.get(cache_key, datetime.min)
            if cache_age < self.cache_duration:
                print(f"Using cached odds (age: {cache_age.seconds}s)")
                return self._cache[cache_key]

        all_matches = []
        tennis_sports = self.get_tennis_sports()

        if not tennis_sports:
            print("No active tennis markets found")
            return []

        print(f"Found {len(tennis_sports)} active tennis competitions")

        for sport in tennis_sports:
            sport_key = sport['key']
            print(f"  Fetching odds for: {sport.get('title', sport_key)}")

            params = {
                'regions': regions,
                'markets': 'h2h',  # Head-to-head (match winner)
                'oddsFormat': 'decimal'
            }

            if bookmakers:
                params['bookmakers'] = ','.join(bookmakers)

            matches = self._make_request(f"sports/{sport_key}/odds", params)

            if matches:
                for match in matches:
                    match['sport_key'] = sport_key
                    match['sport_title'] = sport.get('title', '')
                all_matches.extend(matches)

        # Update cache
        self._cache[cache_key] = all_matches
        self._cache_time[cache_key] = datetime.now()

        print(f"Total matches with odds: {len(all_matches)}")
        if self.requests_remaining:
            print(f"API requests remaining this month: {self.requests_remaining}")

        return all_matches

    def find_match(self, player1: str, player2: str, matches: List[Dict] = None) -> Optional[Dict]:
        """
        Find a specific match by player names.

        Uses fuzzy matching to handle name variations between Betfair and bookmakers.
        """
        if matches is None:
            matches = self.get_tennis_odds()

        player1_lower = player1.lower().strip()
        player2_lower = player2.lower().strip()

        best_match = None
        best_score = 0

        for match in matches:
            outcomes = match.get('bookmakers', [{}])[0].get('markets', [{}])[0].get('outcomes', [])
            if len(outcomes) < 2:
                continue

            # Get player names from the match
            match_p1 = outcomes[0].get('name', '').lower()
            match_p2 = outcomes[1].get('name', '').lower()

            # Calculate similarity scores
            score1 = max(
                self._name_similarity(player1_lower, match_p1),
                self._name_similarity(player1_lower, match_p2)
            )
            score2 = max(
                self._name_similarity(player2_lower, match_p1),
                self._name_similarity(player2_lower, match_p2)
            )

            # Both players must match reasonably well
            combined_score = min(score1, score2)

            if combined_score > best_score and combined_score > 0.6:
                best_score = combined_score
                best_match = match

        return best_match

    def _name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two player names."""
        # Direct match
        if name1 == name2:
            return 1.0

        # Check if last names match (most reliable)
        parts1 = name1.split()
        parts2 = name2.split()

        if parts1 and parts2:
            last1 = parts1[-1]
            last2 = parts2[-1]
            if last1 == last2:
                return 0.9

        # Fuzzy match
        return SequenceMatcher(None, name1, name2).ratio()

    def get_pinnacle_odds(self, player1: str, player2: str) -> Optional[Tuple[float, float]]:
        """
        Get Pinnacle odds for a specific match.

        Returns:
            Tuple of (player1_odds, player2_odds) or None if not found
        """
        match = self.find_match(player1, player2)

        if not match:
            return None

        # Find Pinnacle in bookmakers
        for bookmaker in match.get('bookmakers', []):
            if bookmaker.get('key') == 'pinnacle':
                markets = bookmaker.get('markets', [])
                for market in markets:
                    if market.get('key') == 'h2h':
                        outcomes = market.get('outcomes', [])
                        if len(outcomes) >= 2:
                            # Match player names to get correct odds
                            p1_lower = player1.lower()

                            for outcome in outcomes:
                                if self._name_similarity(p1_lower, outcome['name'].lower()) > 0.6:
                                    p1_odds = outcome['price']
                                    p2_odds = [o['price'] for o in outcomes if o != outcome][0]
                                    return (p1_odds, p2_odds)

        return None

    def compare_odds(self, player1: str, player2: str,
                     betfair_p1_odds: float, betfair_p2_odds: float,
                     threshold: float = 0.15) -> Dict:
        """
        Compare Betfair odds against Pinnacle and other bookmakers.

        Args:
            player1: First player name
            player2: Second player name
            betfair_p1_odds: Betfair odds for player 1
            betfair_p2_odds: Betfair odds for player 2
            threshold: Maximum acceptable odds difference (0.15 = 15%)

        Returns:
            Dict with comparison results and warnings
        """
        result = {
            'match_found': False,
            'pinnacle_odds': None,
            'all_bookmaker_odds': {},
            'betfair_odds': (betfair_p1_odds, betfair_p2_odds),
            'discrepancy': None,
            'warning': None,
            'recommendation': 'OK'
        }

        match = self.find_match(player1, player2)

        if not match:
            result['warning'] = "Match not found in Odds API"
            return result

        result['match_found'] = True
        result['match_name'] = f"{match.get('home_team')} vs {match.get('away_team')}"

        # Collect odds from all bookmakers
        for bookmaker in match.get('bookmakers', []):
            bookie_key = bookmaker.get('key')
            markets = bookmaker.get('markets', [])

            for market in markets:
                if market.get('key') == 'h2h':
                    outcomes = market.get('outcomes', [])
                    if len(outcomes) >= 2:
                        # Map odds to correct players
                        p1_lower = player1.lower()
                        bookie_odds = {}

                        for outcome in outcomes:
                            if self._name_similarity(p1_lower, outcome['name'].lower()) > 0.6:
                                bookie_odds['p1'] = outcome['price']
                            else:
                                bookie_odds['p2'] = outcome['price']

                        if 'p1' in bookie_odds and 'p2' in bookie_odds:
                            result['all_bookmaker_odds'][bookie_key] = (bookie_odds['p1'], bookie_odds['p2'])

                            if bookie_key == 'pinnacle':
                                result['pinnacle_odds'] = (bookie_odds['p1'], bookie_odds['p2'])

        # Calculate discrepancy against Pinnacle
        # Logic: Skip if Betfair odds are LOWER than Pinnacle (bad value)
        #        Keep if Betfair odds are HIGHER than Pinnacle (good value)
        if result['pinnacle_odds']:
            pin_p1, pin_p2 = result['pinnacle_odds']

            # Calculate directional difference (negative = Betfair lower = bad value)
            # Positive = Betfair higher = good value
            p1_diff_pct = ((betfair_p1_odds - pin_p1) / pin_p1) * 100
            p2_diff_pct = ((betfair_p2_odds - pin_p2) / pin_p2) * 100

            result['discrepancy'] = {
                'p1_diff_pct': round(p1_diff_pct, 1),
                'p2_diff_pct': round(p2_diff_pct, 1),
            }

            # Check if EITHER player has Betfair odds significantly LOWER than Pinnacle
            # This indicates bad value / suspicious odds
            worst_diff = min(p1_diff_pct, p2_diff_pct)  # Most negative = worst value

            if worst_diff < -threshold * 100:  # e.g., -15% or worse
                result['warning'] = f"Betfair odds lower than Pinnacle by {abs(round(worst_diff, 1))}% (bad value)"
                result['recommendation'] = 'SKIP'
            elif worst_diff < -threshold * 50:  # e.g., -7.5% or worse
                result['warning'] = f"Betfair odds slightly lower than Pinnacle ({abs(round(worst_diff, 1))}%)"
                result['recommendation'] = 'CAUTION'
            elif max(p1_diff_pct, p2_diff_pct) > threshold * 100:
                # Betfair offering BETTER odds than Pinnacle - good value!
                result['note'] = f"Betfair odds higher than Pinnacle by {round(max(p1_diff_pct, p2_diff_pct), 1)}% (good value)"
                result['recommendation'] = 'OK'

        return result


# Convenience functions
_client = None

def get_client() -> OddsAPIClient:
    """Get singleton client instance."""
    global _client
    if _client is None:
        _client = OddsAPIClient()
    return _client


def compare_betfair_odds(player1: str, player2: str,
                         betfair_p1_odds: float, betfair_p2_odds: float) -> Dict:
    """Quick comparison of Betfair odds against Pinnacle."""
    return get_client().compare_odds(player1, player2, betfair_p1_odds, betfair_p2_odds)


def check_api_status() -> Dict:
    """Check API key and usage status."""
    client = get_client()

    if not client.api_key:
        return {
            'configured': False,
            'message': "No API key. Get one at https://the-odds-api.com/"
        }

    # Make a simple request to check status
    sports = client.get_sports()

    if sports is None:
        return {
            'configured': True,
            'valid': False,
            'message': "API key invalid or request failed"
        }

    return {
        'configured': True,
        'valid': True,
        'requests_remaining': client.requests_remaining,
        'tennis_sports_available': len([s for s in sports if 'tennis' in s.get('key', '')])
    }


if __name__ == "__main__":
    # Test the API
    print("=" * 60)
    print("THE ODDS API - TEST")
    print("=" * 60)

    status = check_api_status()
    print(f"\nAPI Status: {status}")

    if status.get('valid'):
        client = get_client()

        print("\nFetching tennis odds...")
        matches = client.get_tennis_odds()

        print(f"\nFound {len(matches)} matches")

        # Show first few matches
        for match in matches[:5]:
            home = match.get('home_team', 'Unknown')
            away = match.get('away_team', 'Unknown')
            print(f"\n{home} vs {away}")

            for bookie in match.get('bookmakers', [])[:3]:
                bookie_name = bookie.get('title', bookie.get('key'))
                markets = bookie.get('markets', [])
                if markets:
                    outcomes = markets[0].get('outcomes', [])
                    if len(outcomes) >= 2:
                        print(f"  {bookie_name}: {outcomes[0]['name']} @ {outcomes[0]['price']}, {outcomes[1]['name']} @ {outcomes[1]['price']}")
