"""
Live Scores - Fetch real-time tennis scores from Flashscore.

This module provides live score data for in-play tennis matches.
Uses Flashscore's internal API which provides comprehensive tennis scores.
"""

import json
import urllib.request
import urllib.error
import ssl
from typing import Dict, List, Optional
from datetime import datetime


class FlashscoreTennis:
    """Fetch live tennis scores from Flashscore."""

    # Flashscore API endpoints
    BASE_URL = "https://www.flashscore.com"
    LIVE_URL = "https://d.flashscore.co.uk/x/feed/f_2_-2_1_en-uk_1"  # Tennis live

    def __init__(self):
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-GB,en;q=0.9',
            'Referer': 'https://www.flashscore.com/',
            'X-Fsign': 'SW9D1eZo',
        }

    def _make_request(self, url: str) -> Optional[str]:
        """Make HTTP request and return response text."""
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=10, context=self.ssl_context) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            print(f"Flashscore request error: {e}")
            return None

    def get_live_matches(self) -> List[Dict]:
        """Get all live tennis matches with scores."""
        data = self._make_request(self.LIVE_URL)
        if not data:
            return []

        return self._parse_flashscore_data(data)

    def _parse_flashscore_data(self, data: str) -> List[Dict]:
        """Parse Flashscore's custom data format."""
        matches = []

        try:
            # Flashscore uses a custom delimited format
            # Split by the match delimiter
            lines = data.split('~')

            current_match = {}

            for line in lines:
                if not line.strip():
                    continue

                # Parse key-value pairs
                if line.startswith('AA÷'):
                    # New match - event ID
                    if current_match and 'player1' in current_match:
                        matches.append(current_match)
                    current_match = {'event_id': line[3:]}

                elif line.startswith('AE÷'):
                    # Player 1 name
                    current_match['player1'] = line[3:]

                elif line.startswith('AF÷'):
                    # Player 2 name
                    current_match['player2'] = line[3:]

                elif line.startswith('AB÷'):
                    # Match status (1 = not started, 2 = live, 3 = finished)
                    status_code = line[3:]
                    if status_code == '2':
                        current_match['status'] = 'live'
                    elif status_code == '3':
                        current_match['status'] = 'finished'
                    else:
                        current_match['status'] = 'scheduled'

                elif line.startswith('AG÷'):
                    # Score player 1 (sets won)
                    current_match['sets_p1'] = line[3:]

                elif line.startswith('AH÷'):
                    # Score player 2 (sets won)
                    current_match['sets_p2'] = line[3:]

                elif line.startswith('BA÷'):
                    # Current game score P1
                    current_match['games_p1'] = line[3:]

                elif line.startswith('BB÷'):
                    # Current game score P2
                    current_match['games_p2'] = line[3:]

                elif line.startswith('AO÷'):
                    # Tournament name
                    current_match['tournament'] = line[3:]

            # Don't forget the last match
            if current_match and 'player1' in current_match:
                matches.append(current_match)

        except Exception as e:
            print(f"Error parsing Flashscore data: {e}")

        # Filter to only live matches
        live_matches = [m for m in matches if m.get('status') == 'live']

        return live_matches

    def format_score(self, match: Dict) -> str:
        """Format a match score for display."""
        sets_p1 = match.get('sets_p1', '0')
        sets_p2 = match.get('sets_p2', '0')
        games_p1 = match.get('games_p1', '')
        games_p2 = match.get('games_p2', '')

        if games_p1 and games_p2:
            return f"{sets_p1}-{sets_p2} ({games_p1}-{games_p2})"
        else:
            return f"{sets_p1}-{sets_p2}"

    def find_match_score(self, player1: str, player2: str) -> Optional[str]:
        """Find the score for a specific match by player names."""
        live_matches = self.get_live_matches()

        p1_lower = player1.lower()
        p2_lower = player2.lower()
        p1_last = p1_lower.split()[-1] if p1_lower else ''
        p2_last = p2_lower.split()[-1] if p2_lower else ''

        for match in live_matches:
            m_p1 = match.get('player1', '').lower()
            m_p2 = match.get('player2', '').lower()
            m_p1_last = m_p1.split()[-1] if m_p1 else ''
            m_p2_last = m_p2.split()[-1] if m_p2 else ''

            # Match by last name (either order)
            if (p1_last == m_p1_last and p2_last == m_p2_last) or \
               (p1_last == m_p2_last and p2_last == m_p1_last):
                return self.format_score(match)

        return None


# Alternative: Sofascore API (more reliable structure)
class SofascoreTennis:
    """Fetch live tennis scores from Sofascore."""

    LIVE_URL = "https://api.sofascore.com/api/v1/sport/tennis/events/live"

    def __init__(self):
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }

    def _make_request(self, url: str) -> Optional[Dict]:
        """Make HTTP request and return JSON response."""
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=10, context=self.ssl_context) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"Sofascore request error: {e}")
            return None

    def get_live_matches(self) -> List[Dict]:
        """Get all live tennis matches with scores."""
        data = self._make_request(self.LIVE_URL)
        if not data:
            return []

        matches = []
        events = data.get('events', [])

        for event in events:
            home = event.get('homeTeam', {})
            away = event.get('awayTeam', {})
            home_score = event.get('homeScore', {})
            away_score = event.get('awayScore', {})

            match = {
                'player1': home.get('name', ''),
                'player2': away.get('name', ''),
                'sets_p1': home_score.get('current', 0),
                'sets_p2': away_score.get('current', 0),
                'games_p1': home_score.get('period1', 0),  # Current set games
                'games_p2': away_score.get('period1', 0),
                'status': 'live' if event.get('status', {}).get('type') == 'inprogress' else 'other',
                'tournament': event.get('tournament', {}).get('name', ''),
            }

            if match['status'] == 'live':
                matches.append(match)

        return matches

    def format_score(self, match: Dict) -> str:
        """Format a match score for display."""
        sets_p1 = match.get('sets_p1', 0)
        sets_p2 = match.get('sets_p2', 0)
        games_p1 = match.get('games_p1', 0)
        games_p2 = match.get('games_p2', 0)

        if games_p1 or games_p2:
            return f"{sets_p1}-{sets_p2} ({games_p1}-{games_p2})"
        else:
            return f"{sets_p1}-{sets_p2}"

    def find_match_score(self, player1: str, player2: str) -> Optional[str]:
        """Find the score for a specific match by player names."""
        live_matches = self.get_live_matches()

        p1_lower = player1.lower()
        p2_lower = player2.lower()
        p1_last = p1_lower.split()[-1] if p1_lower else ''
        p2_last = p2_lower.split()[-1] if p2_lower else ''

        for match in live_matches:
            m_p1 = match.get('player1', '').lower()
            m_p2 = match.get('player2', '').lower()
            m_p1_last = m_p1.split()[-1] if m_p1 else ''
            m_p2_last = m_p2.split()[-1] if m_p2 else ''

            # Match by last name (either order)
            if (p1_last == m_p1_last and p2_last == m_p2_last) or \
               (p1_last == m_p2_last and p2_last == m_p1_last):
                return self.format_score(match)

        return None


def get_live_score(player1: str, player2: str) -> Optional[str]:
    """Get live score for a match, trying multiple sources."""
    # Try Sofascore first (more reliable API)
    try:
        sofascore = SofascoreTennis()
        score = sofascore.find_match_score(player1, player2)
        if score:
            return score
    except Exception as e:
        print(f"Sofascore error: {e}")

    # Fallback to Flashscore
    try:
        flashscore = FlashscoreTennis()
        score = flashscore.find_match_score(player1, player2)
        if score:
            return score
    except Exception as e:
        print(f"Flashscore error: {e}")

    return None


if __name__ == "__main__":
    # Test the live scores
    print("Testing Sofascore...")
    sofascore = SofascoreTennis()
    matches = sofascore.get_live_matches()
    print(f"Found {len(matches)} live matches on Sofascore:")
    for m in matches[:5]:
        print(f"  {m['player1']} vs {m['player2']}: {sofascore.format_score(m)}")

    print("\nTesting Flashscore...")
    flashscore = FlashscoreTennis()
    matches = flashscore.get_live_matches()
    print(f"Found {len(matches)} live matches on Flashscore:")
    for m in matches[:5]:
        print(f"  {m.get('player1', '?')} vs {m.get('player2', '?')}: {flashscore.format_score(m)}")
