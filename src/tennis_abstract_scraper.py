"""
Tennis Betting System - Tennis Abstract Scraper
Fetches recent match data from tennisabstract.com for individual players
"""

import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from database import db, TennisDatabase


class TennisAbstractScraper:
    """Scrape recent match data from Tennis Abstract."""

    BASE_URL = "https://www.tennisabstract.com/cgi-bin/player.cgi?p="

    def __init__(self, database: TennisDatabase = None, headless: bool = True):
        self.db = database or db
        self.headless = headless
        self.driver = None

    def _init_driver(self):
        """Initialize Chrome WebDriver."""
        if self.driver:
            return

        options = Options()
        if self.headless:
            options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--log-level=3")  # Suppress logs

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)

    def _close_driver(self):
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def _format_player_name_for_url(self, player_name: str) -> str:
        """Convert player name to Tennis Abstract URL format (e.g., 'Mariano Navone' -> 'MarianoNavone')."""
        # Remove special characters and spaces
        formatted = re.sub(r'[^a-zA-Z]', '', player_name.title().replace(' ', ''))
        return formatted

    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string to YYYY-MM-DD format."""
        try:
            # Tennis Abstract uses formats like "Jan 12" or "2025-01-12"
            # Try common formats
            for fmt in ["%Y-%m-%d", "%b %d", "%d %b", "%b %d, %Y", "%d %b %Y"]:
                try:
                    dt = datetime.strptime(date_str.strip(), fmt)
                    # If no year, assume current year
                    if dt.year == 1900:
                        dt = dt.replace(year=datetime.now().year)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue
            return None
        except:
            return None

    def _parse_score(self, score_str: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        """Parse score string to extract sets won/lost and total games."""
        try:
            sets = re.findall(r'(\d+)-(\d+)', score_str)
            if not sets:
                return None, None, None

            sets_won = 0
            sets_lost = 0
            games_won = 0
            games_lost = 0

            for s in sets:
                g1, g2 = int(s[0]), int(s[1])
                games_won += g1
                games_lost += g2
                if g1 > g2:
                    sets_won += 1
                else:
                    sets_lost += 1

            return sets_won, sets_lost, games_won + games_lost
        except:
            return None, None, None

    def fetch_recent_matches(self, player_name: str, limit: int = 20) -> List[Dict]:
        """
        Fetch recent matches for a player from Tennis Abstract.

        Returns list of match dicts with: date, tournament, surface, round,
        opponent, won (bool), score, sets_won, sets_lost, minutes
        """
        matches = []
        formatted_name = self._format_player_name_for_url(player_name)
        url = f"{self.BASE_URL}{formatted_name}"

        try:
            self._init_driver()
            self.driver.get(url)

            # Wait for the recent results table to load
            wait = WebDriverWait(self.driver, 15)
            try:
                wait.until(EC.presence_of_element_located((By.ID, "recent-results")))
                time.sleep(2)  # Extra time for JS to populate
            except TimeoutException:
                print(f"Timeout waiting for page to load for {player_name}")
                return matches

            # Find the recent results table
            try:
                recent_table = self.driver.find_element(By.ID, "recent-results")
            except NoSuchElementException:
                print(f"Could not find recent-results table for {player_name}")
                return matches

            rows = recent_table.find_elements(By.TAG_NAME, "tr")

            for row in rows[1:]:  # Skip header row
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) < 7:
                        continue

                    row_text = [cell.text.strip() for cell in cells]

                    # Parse date (format: "19-Jan-2026")
                    date_str = row_text[0] if row_text else None
                    date = self._parse_ta_date(date_str)
                    if not date:
                        continue

                    # Parse other columns
                    tournament = row_text[1] if len(row_text) > 1 else None
                    surface = row_text[2] if len(row_text) > 2 else None
                    round_name = row_text[3] if len(row_text) > 3 else None

                    # Column 6: match-up info (e.g., "(6)Alex Michelsen [USA] d. Navone")
                    # Column 7: score (e.g., "2-6 6-2 7-5")
                    matchup_cell = row_text[6] if len(row_text) > 6 else ""
                    score_cell = row_text[7] if len(row_text) > 7 else ""

                    # Parse the matchup cell
                    match_info = self._parse_score_cell(matchup_cell, player_name, score_cell)
                    if not match_info:
                        continue

                    # Parse duration (last column, format: "2:25")
                    minutes = None
                    time_str = row_text[-1] if row_text else None
                    if time_str and ':' in time_str:
                        try:
                            parts = time_str.split(':')
                            minutes = int(parts[0]) * 60 + int(parts[1])
                        except:
                            pass

                    match = {
                        'date': date,
                        'tournament': tournament,
                        'surface': surface,
                        'round': round_name,
                        'opponent': match_info['opponent'],
                        'won': match_info['won'],
                        'score': match_info['score'],
                        'sets_won': match_info['sets_won'],
                        'sets_lost': match_info['sets_lost'],
                        'minutes': minutes,
                    }
                    matches.append(match)

                    if len(matches) >= limit:
                        break

                except Exception as e:
                    continue

        except Exception as e:
            print(f"Error fetching data for {player_name}: {e}")
        finally:
            self._close_driver()

        return matches

    def _parse_ta_date(self, date_str: str) -> Optional[str]:
        """Parse Tennis Abstract date format (e.g., '19-Jan-2026')."""
        if not date_str:
            return None
        try:
            dt = datetime.strptime(date_str.strip(), "%d-%b-%Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None

    def _parse_score_cell(self, matchup_text: str, player_name: str, score_text: str = "") -> Optional[Dict]:
        """
        Parse the matchup and score cells from Tennis Abstract.

        Matchup formats:
        - "Navone vs Hamad Medjedovic [SRB]" (upcoming/walkover)
        - "(6)Alex Michelsen [USA] d. Navone" (opponent won)
        - "(2)Navone d. Marco Cecchinato [ITA]" (player won)

        Score is separate: "2-6 6-2 7-5"
        """
        if not matchup_text:
            return None

        result = {
            'opponent': None,
            'won': None,
            'score': None,
            'sets_won': None,
            'sets_lost': None,
        }

        # Parse score from separate column
        if score_text:
            score_match = re.findall(r'\d+-\d+(?:\(\d+\))?', score_text)
            if score_match:
                result['score'] = ' '.join(score_match)

        # Determine winner and opponent
        # Get player's last name for matching
        player_last = player_name.split()[-1].lower() if player_name else ""

        if ' d. ' in matchup_text:
            # Someone won - format: "Winner d. Loser"
            parts = matchup_text.split(' d. ')
            winner_part = parts[0].strip()
            loser_part = parts[1].strip() if len(parts) > 1 else ""

            # Check if player is the winner
            if player_last and player_last in winner_part.lower():
                result['won'] = True
                result['opponent'] = self._clean_opponent_name(loser_part)
            else:
                result['won'] = False
                result['opponent'] = self._clean_opponent_name(winner_part)

        elif ' vs ' in matchup_text:
            # Upcoming or walkover - format: "Player vs Opponent"
            parts = matchup_text.split(' vs ')
            if len(parts) == 2:
                if player_last and player_last in parts[0].lower():
                    result['opponent'] = self._clean_opponent_name(parts[1])
                else:
                    result['opponent'] = self._clean_opponent_name(parts[0])
            result['won'] = None  # Unknown/upcoming

        if not result['opponent']:
            return None

        # Now parse sets won/lost based on who won
        if result['score'] and result['won'] is not None:
            sets_won, sets_lost, _ = self._parse_score(result['score'])
            if result['won']:
                result['sets_won'] = sets_won
                result['sets_lost'] = sets_lost
            else:
                # Player lost, so swap
                result['sets_won'] = sets_lost
                result['sets_lost'] = sets_won

        return result

    def _clean_opponent_name(self, name_str: str) -> str:
        """Clean opponent name by removing seed, country code, etc."""
        if not name_str:
            return ""
        # Remove seed like "(6)" or "(WC)"
        name = re.sub(r'^\([^)]+\)', '', name_str).strip()
        # Remove country code like "[USA]"
        name = re.sub(r'\[[A-Z]{3}\]', '', name).strip()
        # Remove any trailing score parts
        name = re.sub(r'\s+\d+-\d+.*$', '', name).strip()
        return name

    def fetch_and_update_player(self, player_id: int, player_name: str = None) -> Dict:
        """
        Fetch recent matches for a player and update the database.

        Returns dict with: success, matches_found, matches_added, message
        """
        result = {
            'success': False,
            'matches_found': 0,
            'matches_added': 0,
            'message': ''
        }

        # Get player name if not provided
        if not player_name:
            player = self.db.get_player(player_id)
            if not player:
                result['message'] = "Player not found in database"
                return result
            player_name = player['name']

        print(f"Fetching recent matches for {player_name}...")
        matches = self.fetch_recent_matches(player_name)
        result['matches_found'] = len(matches)

        if not matches:
            result['message'] = f"No matches found on Tennis Abstract for {player_name}"
            return result

        # Get existing matches to avoid duplicates
        existing_matches = self.db.get_player_matches(player_id, limit=50)
        existing_dates = set(m.get('date', '')[:10] for m in existing_matches)

        added = 0
        for match in matches:
            if match['date'] in existing_dates:
                continue

            # Find opponent in database
            opponent_name = match.get('opponent')
            opponent_id = None
            if opponent_name:
                # Search for opponent
                opponents = self.db.search_players(opponent_name, limit=1)
                if opponents:
                    opponent_id = opponents[0]['id']

            if not opponent_id:
                # Can't add match without knowing opponent
                continue

            # Skip matches without a result (upcoming or no score)
            if match.get('won') is None:
                continue

            # Get sets with default to 0 if None
            sets_won = match.get('sets_won') or 0
            sets_lost = match.get('sets_lost') or 0

            # Create match record
            match_data = {
                'date': match['date'],
                'winner_id': player_id if match.get('won') else opponent_id,
                'loser_id': opponent_id if match.get('won') else player_id,
                'score': match.get('score') or '',
                'surface': match.get('surface'),
                'round': match.get('round'),
                'sets_won_w': sets_won if match.get('won') else sets_lost,
                'sets_won_l': sets_lost if match.get('won') else sets_won,
                'tourney_name': match.get('tournament') or 'Unknown',
                'best_of': 5 if (sets_won + sets_lost) > 3 else 3,
                'minutes': match.get('minutes'),
            }

            try:
                result = self.db.insert_match(match_data, source="tennis_abstract")
                if result:  # Only count if validation passed
                    added += 1
            except Exception as e:
                print(f"Error inserting match: {e}")

        result['matches_added'] = added
        result['success'] = True
        result['message'] = f"Found {len(matches)} matches, added {added} new matches"

        # Update the timestamp to track when this player was last updated
        self.db.update_player_ta_timestamp(player_id)

        return result


# Standalone test
if __name__ == "__main__":
    scraper = TennisAbstractScraper(headless=False)  # Set False to see browser
    matches = scraper.fetch_recent_matches("Mariano Navone", limit=10)

    print(f"\nFound {len(matches)} matches:")
    for m in matches:
        print(f"  {m['date']} - vs {m['opponent']} - {m['score']} ({'W' if m['won'] else 'L'})")
