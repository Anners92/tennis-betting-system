"""
Tennis Explorer Scraper - For WTA and additional ATP player data
Scrapes player profiles and match history from tennisexplorer.com
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from database import db


class PlayerNameMatcher:
    """
    Robust player name matching system that handles various name formats:
    - "LastName F." (e.g., "Grubor A.")
    - "F. LastName" (e.g., "A. Grubor")
    - "FirstName LastName" (e.g., "Ana Grubor")
    - "LastName FirstName" (e.g., "Grubor Ana")
    - Compound names (e.g., "Del Potro J.", "Juan Martin Del Potro")
    """

    def __init__(self):
        self.players = {}  # id -> canonical name
        self.player_rankings = {}  # id -> current_ranking (or None)
        self.by_full_name = {}  # normalized full name -> id
        self.by_last_name = {}  # last name -> [(id, full_name, first_initial)]
        self.by_name_parts = {}  # each name part -> [(id, full_name)]
        self.by_last_initial = {}  # "lastname_x" -> [(id, full_name)] where x is first initial

    def _normalize(self, name: str) -> str:
        """Normalize a name for comparison."""
        if not name:
            return ""
        # Lowercase and strip
        name = name.lower().strip()
        # Remove periods and extra spaces
        name = name.replace('.', '')
        name = ' '.join(name.split())
        return name

    def _extract_components(self, name: str) -> dict:
        """
        Extract name components from various formats.
        Returns dict with: last_name, first_name, first_initial, all_parts
        """
        result = {
            'last_name': '',
            'first_name': '',
            'first_initial': '',
            'all_parts': []
        }

        if not name:
            return result

        normalized = self._normalize(name)
        parts = normalized.split()
        result['all_parts'] = parts

        if not parts:
            return result

        # Detect format based on pattern
        # Format 1: "lastname f" (initial at end) - e.g., "grubor a"
        # Format 2: "f lastname" (initial at start) - e.g., "a grubor"
        # Format 3: "firstname lastname" - e.g., "ana grubor"
        # Format 4: "lastname firstname" - e.g., "grubor ana"

        if len(parts) == 1:
            # Just one word - treat as last name
            result['last_name'] = parts[0]
            return result

        # Check if first or last part is a single letter (initial)
        first_is_initial = len(parts[0]) == 1
        last_is_initial = len(parts[-1]) == 1

        if last_is_initial:
            # Format: "LastName F" or "FirstName LastName F"
            result['first_initial'] = parts[-1]
            result['last_name'] = parts[0]  # Assume first word is last name
            if len(parts) > 2:
                result['first_name'] = ' '.join(parts[1:-1])
        elif first_is_initial:
            # Format: "F LastName" or "F FirstName LastName"
            result['first_initial'] = parts[0]
            result['last_name'] = parts[-1]  # Assume last word is last name
            if len(parts) > 2:
                result['first_name'] = ' '.join(parts[1:-1])
        else:
            # Full names - could be "FirstName LastName" or "LastName FirstName"
            # We'll index both possibilities
            result['first_name'] = parts[0]
            result['last_name'] = parts[-1]
            result['first_initial'] = parts[0][0] if parts[0] else ''

        return result

    def load_players(self, db_connection):
        """Load all players from database and build indexes."""
        cursor = db_connection.cursor()
        cursor.execute("SELECT id, name, current_ranking FROM players")

        for row in cursor.fetchall():
            player_id = row[0]
            full_name = row[1]
            current_ranking = row[2]
            self.add_player(player_id, full_name, current_ranking)

    def add_player(self, player_id: int, full_name: str, current_ranking: int = None):
        """Add a player to all indexes."""
        if not full_name:
            return

        self.players[player_id] = full_name
        self.player_rankings[player_id] = current_ranking
        normalized = self._normalize(full_name)
        components = self._extract_components(full_name)

        # Index by full normalized name
        self.by_full_name[normalized] = player_id

        # Also index without spaces for "A. Grubor" -> "agrubor" matching
        self.by_full_name[normalized.replace(' ', '')] = player_id

        # Index by each name part (for compound name matching)
        for part in components['all_parts']:
            if len(part) > 1:  # Skip initials
                if part not in self.by_name_parts:
                    self.by_name_parts[part] = []
                self.by_name_parts[part].append((player_id, full_name))

        # Index by last name
        last_name = components['last_name']
        if last_name and len(last_name) > 1:
            if last_name not in self.by_last_name:
                self.by_last_name[last_name] = []
            first_initial = components['first_initial'] or (components['first_name'][0] if components['first_name'] else '')
            self.by_last_name[last_name].append((player_id, full_name, first_initial))

            # Also index by last_name + initial
            if first_initial:
                key = f"{last_name}_{first_initial}"
                if key not in self.by_last_initial:
                    self.by_last_initial[key] = []
                self.by_last_initial[key].append((player_id, full_name))

        # For names like "A. Grubor", also index as if "Grubor" is the last name
        # and for "Grubor A.", also consider all parts as potential last names
        for part in components['all_parts']:
            if len(part) > 1:  # Skip initials
                if part not in self.by_last_name:
                    self.by_last_name[part] = []
                # Add with any available initial
                initial = ''
                for p in components['all_parts']:
                    if len(p) == 1:
                        initial = p
                        break
                    elif p != part and len(p) > 1:
                        initial = p[0]
                        break
                # Check if this combination already exists
                existing = [(pid, fn) for pid, fn, fi in self.by_last_name[part]]
                if (player_id, full_name) not in existing:
                    self.by_last_name[part].append((player_id, full_name, initial))

    def find_player_id(self, name: str) -> Optional[int]:
        """
        Find a player ID for the given name using multiple matching strategies.
        Returns the player ID if found, None otherwise.
        """
        if not name:
            return None

        normalized = self._normalize(name)
        components = self._extract_components(name)

        # Strategy 1: Exact match on normalized full name
        # But only accept if player has a ranking (to avoid duplicate/abbreviated entries)
        if normalized in self.by_full_name:
            exact_match_id = self.by_full_name[normalized]
            # If this player has a ranking, accept the match immediately
            if self.player_rankings.get(exact_match_id) is not None:
                return exact_match_id
            # Otherwise, continue to other strategies that may find a ranked player

        # Strategy 1b: Match without spaces (same ranking check)
        no_spaces = normalized.replace(' ', '')
        if no_spaces in self.by_full_name:
            exact_match_id = self.by_full_name[no_spaces]
            if self.player_rankings.get(exact_match_id) is not None:
                return exact_match_id

        # Get all significant parts (not initials) sorted by length (longest first)
        significant_parts = sorted(
            [p for p in components['all_parts'] if len(p) > 1],
            key=len, reverse=True
        )

        # Get the initial (single letter)
        initial = None
        for p in components['all_parts']:
            if len(p) == 1:
                initial = p
                break
        # If no explicit initial, use first letter of shortest significant part
        if not initial and len(significant_parts) >= 2:
            initial = min(significant_parts, key=len)[0]

        # Strategy 2: Match by longest name part (likely last name) + initial
        for part in significant_parts:
            if len(part) < 3:  # Skip very short parts that might be prefixes like "de", "da"
                continue

            if part in self.by_last_name:
                candidates = self.by_last_name[part]

                if initial:
                    # Filter by matching initial
                    matching = [(pid, fn) for pid, fn, fi in candidates
                               if fi and fi[0] == initial]
                    if matching:
                        # Use ranking-based selection for multiple candidates
                        return self._pick_best_candidate(matching)

                # No initial match - if only one candidate with this name part, use it
                if len(candidates) == 1:
                    return candidates[0][0]

        # Strategy 3: Try last_name + initial combination lookup
        last_name = components['last_name']
        first_initial = components['first_initial'] or initial

        # Allow 2-char last names for Asian surnames (Xu, Li, Wu, Ma, etc.)
        if last_name and len(last_name) >= 2 and first_initial:
            key = f"{last_name}_{first_initial}"
            if key in self.by_last_initial:
                candidates = self.by_last_initial[key]
                # Use ranking-based selection
                return self._pick_best_candidate(candidates)

        # Strategy 4: Fuzzy match - all significant parts must appear in player name
        if len(significant_parts) >= 2:
            # Only use parts with 3+ chars for fuzzy matching (avoid "de", "da", "van")
            long_parts = [p for p in significant_parts if len(p) >= 3]
            if len(long_parts) >= 2:
                matching_players = []

                for pid, full_name in self.players.items():
                    fn_normalized = self._normalize(full_name)
                    fn_parts = fn_normalized.split()

                    # Count how many significant parts match
                    matches = sum(1 for sp in long_parts
                                 if any(sp == fp or sp in fp or fp in sp for fp in fn_parts))

                    # Need all long parts to match
                    if matches == len(long_parts):
                        matching_players.append((pid, full_name))

                if matching_players:
                    # Use ranking-based selection
                    return self._pick_best_candidate(matching_players)

        # Strategy 5: Single significant part with initial (last resort for "Lastname X." format)
        if len(significant_parts) == 1 and initial:
            part = significant_parts[0]
            if len(part) >= 3 and part in self.by_last_name:
                candidates = self.by_last_name[part]
                matching = [(pid, fn) for pid, fn, fi in candidates
                           if fi and fi[0] == initial]
                if matching:
                    # Use ranking-based selection
                    return self._pick_best_candidate(matching)

        # Strategy 6: Try reversed name order (FirstName LastName vs LastName FirstName)
        # Handles "Jannik Sinner" vs "Sinner Jannik" format differences
        if len(significant_parts) >= 2:
            # Reverse all parts and try exact match
            reversed_name = ' '.join(significant_parts[::-1])
            if reversed_name in self.by_full_name:
                return self.by_full_name[reversed_name]

            # Also try with just first and last swapped
            swapped = f"{significant_parts[-1]} {' '.join(significant_parts[:-1])}"
            if swapped in self.by_full_name:
                return self.by_full_name[swapped]

        # Fallback: Return exact match even if unranked (better than no match)
        if normalized in self.by_full_name:
            return self.by_full_name[normalized]
        if no_spaces in self.by_full_name:
            return self.by_full_name[no_spaces]

        return None

    def get_player_name(self, player_id: int) -> Optional[str]:
        """Get the canonical name for a player ID."""
        return self.players.get(player_id)

    def _pick_best_candidate(self, candidates: list) -> Optional[int]:
        """Pick the best candidate from a list, preferring ranked players.

        Args:
            candidates: List of tuples containing player_id (and possibly other data)

        Returns:
            Best player_id or None
        """
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0][0]

        # Extract player IDs from candidates (first element of each tuple)
        player_ids = [c[0] for c in candidates]

        # Prefer players with rankings (non-None ranking)
        ranked_players = [(pid, self.player_rankings.get(pid)) for pid in player_ids
                         if self.player_rankings.get(pid) is not None]

        if ranked_players:
            # Sort by ranking (lower is better) and return best
            ranked_players.sort(key=lambda x: x[1])
            return ranked_players[0][0]

        # No ranked players - prefer positive IDs over negative
        positive_ids = [pid for pid in player_ids if pid > 0]
        if positive_ids:
            return positive_ids[0]

        # Last resort - return first candidate
        return player_ids[0]


class TennisExplorerScraper:
    """Scraper for Tennis Explorer player data."""

    BASE_URL = "https://www.tennisexplorer.com"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

    def search_player(self, player_name: str) -> Optional[str]:
        """Search for a player and return their profile URL slug."""
        # Clean up name for search
        search_name = player_name.lower().strip()
        name_parts = search_name.split()

        # Use last name for initial search (more reliable)
        last_name = name_parts[-1] if name_parts else search_name

        # Use the list-players endpoint which works better
        search_url = f"{self.BASE_URL}/list-players/?search-text-pl={last_name}"

        try:
            response = self.session.get(search_url, timeout=15)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'html.parser')

            # Look for player links in search results
            player_links = soup.select('a[href*="/player/"]')

            best_match = None
            best_score = 0

            for link in player_links:
                href = link.get('href', '')
                link_text = link.get_text().strip().lower()

                # Calculate match score
                score = 0
                for part in name_parts:
                    if part in link_text:
                        score += 1

                # Prefer exact matches
                if score == len(name_parts) and score > best_score:
                    best_score = score
                    match = re.search(r'/player/([^/]+)/?', href)
                    if match:
                        best_match = match.group(1)

            return best_match

        except Exception as e:
            print(f"Error searching for player: {e}")
            return None

    def fetch_player_profile(self, player_slug: str) -> Optional[Dict]:
        """Fetch player profile data from Tennis Explorer."""
        url = f"{self.BASE_URL}/player/{player_slug}/"

        try:
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'html.parser')
            page_text = soup.get_text()

            profile = {
                'name': '',
                'country': '',
                'dob': None,
                'height': None,
                'hand': 'U',
                'ranking': None,
                'matches': []
            }

            # Extract player name from h3
            name_elem = soup.select_one('h3')
            if name_elem:
                name_text = name_elem.get_text().strip()
                # Name is "Last First" format, convert to "First Last"
                parts = name_text.split()
                if len(parts) >= 2:
                    profile['name'] = f"{parts[-1]} {' '.join(parts[:-1])}"
                else:
                    profile['name'] = name_text

            # Extract profile info using regex on page text
            # Country
            country_match = re.search(r'Country[:\s]+([A-Z]{2,3})', page_text)
            if country_match:
                profile['country'] = country_match.group(1)

            # Height
            height_match = re.search(r'(\d{3})\s*cm', page_text)
            if height_match:
                profile['height'] = int(height_match.group(1))

            # DOB - format is "28. 9. 1999"
            dob_match = re.search(r'\((\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\)', page_text)
            if dob_match:
                try:
                    day = dob_match.group(1).zfill(2)
                    month = dob_match.group(2).zfill(2)
                    year = dob_match.group(3)
                    profile['dob'] = f"{year}-{month}-{day}"
                except:
                    pass

            # Hand - check "Plays: left" or "Plays: right"
            if re.search(r'Plays[:\s]+left', page_text, re.IGNORECASE):
                profile['hand'] = 'L'
            elif re.search(r'Plays[:\s]+right', page_text, re.IGNORECASE):
                profile['hand'] = 'R'

            # Ranking - "Current/Highest rank - singles: 256. / 84."
            rank_match = re.search(r'rank\s*-\s*singles[:\s]+(\d+)', page_text, re.IGNORECASE)
            if rank_match:
                profile['ranking'] = int(rank_match.group(1))

            # Extract recent matches
            profile['matches'] = self._extract_matches(soup)

            return profile

        except Exception as e:
            print(f"Error fetching player profile: {e}")
            return None

    def _extract_matches(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract match data from the player profile page."""
        matches = []
        current_year = datetime.now().year
        current_tournament = ""
        current_surface = "Hard"

        # Find all tables and look for match rows
        for table in soup.select('table'):
            rows = table.select('tr')

            for row in rows:
                cells = row.select('td')
                if len(cells) < 3:
                    continue

                row_text = row.get_text()

                # Check if this is a tournament header (contains ITF, ATP, WTA, Challenger, etc.)
                if re.search(r'(ITF|ATP|WTA|Challenger|Open|Masters)', row_text):
                    tournament_cell = cells[0] if cells else None
                    if tournament_cell:
                        current_tournament = tournament_cell.get_text().strip()
                        current_surface = self._guess_surface(current_tournament)
                    continue

                # Look for match pattern: "DD.MM. | | Player - Opponent | Round | Score"
                # Match rows have a date like "17.01." and a score like "6-1, 6-3"
                date_match = re.search(r'(\d{1,2})\.(\d{1,2})\.', row_text)
                score_match = re.search(r'\d-\d', row_text)

                if date_match and score_match:
                    try:
                        # Extract date
                        day = date_match.group(1).zfill(2)
                        month = date_match.group(2).zfill(2)
                        match_date = f"{current_year}-{month}-{day}"

                        # Find opponent from the match string
                        # Pattern: "Day K. - Opponent" or "Day K. - Opponent L."
                        match_str = None
                        for cell in cells:
                            cell_text = cell.get_text().strip()
                            if ' - ' in cell_text and 'Day' in cell_text:
                                match_str = cell_text
                                break

                        if not match_str:
                            continue

                        # Extract opponent (after the " - ")
                        parts = match_str.split(' - ')
                        if len(parts) >= 2:
                            opponent = parts[1].strip()
                            # Clean up opponent name (remove initials like "L.")
                            opponent = re.sub(r'\s+[A-Z]\.$', '', opponent)
                        else:
                            continue

                        # Extract score
                        score = ""
                        for cell in cells:
                            cell_text = cell.get_text().strip()
                            if re.match(r'^[\d\-,\s]+$', cell_text) and '-' in cell_text:
                                score = cell_text
                                break

                        # Extract round
                        round_name = ""
                        for cell in cells:
                            cell_text = cell.get_text().strip()
                            if cell_text in ['1R', '2R', '3R', '4R', 'R16', 'R32', 'R64', 'R128', 'QF', 'SF', 'F']:
                                round_name = cell_text
                                break

                        # Determine win - if player name is first in the match string
                        won = match_str.lower().startswith('day')

                        match_data = {
                            'opponent': opponent,
                            'tournament': current_tournament,
                            'surface': current_surface,
                            'date': match_date,
                            'round': round_name,
                            'score': score,
                            'won': won
                        }

                        matches.append(match_data)

                    except Exception as e:
                        continue

        return matches

    def fetch_player_year_matches(self, player_slug: str, player_name: str, year: int) -> List[Dict]:
        """
        Fetch matches for a player from their year-specific page.

        Tennis Explorer stores match history at URLs like:
        /player/marcondes/?annual=2025

        Args:
            player_slug: Player's URL slug (e.g., "marcondes")
            player_name: Player's display name for determining wins
            year: Year to fetch matches for

        Returns:
            List of match dictionaries
        """
        url = f"{self.BASE_URL}/player/{player_slug}/?annual={year}"
        matches = []

        try:
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                return matches

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract player's last name for matching (used to determine wins)
            name_parts = player_name.split()
            player_last_name = name_parts[-1].lower() if name_parts else ""
            # Also try first part (sometimes name is "LastName FirstName")
            player_first_part = name_parts[0].lower() if name_parts else ""

            current_tournament = ""
            current_surface = "Hard"

            # Find all tables
            for table in soup.select('table'):
                rows = table.select('tr')

                for row in rows:
                    cells = row.select('td')

                    # Skip rows with too few cells
                    if len(cells) < 1:
                        continue

                    # Get cell texts
                    cell_texts = [c.get_text(strip=True) for c in cells]

                    # Check for tournament header row - single cell with tournament name
                    # Format: row has 1 cell OR first cell has tournament-like text and no date
                    first_text = cell_texts[0] if cell_texts else ""

                    # Tournament header: looks like "Yokohama challenger" or "Kobe challenger"
                    if (len(cells) == 1 or
                        (first_text and
                         re.search(r'(challenger|open|cup|masters|futures|atp|wta|itf)', first_text, re.I) and
                         not re.match(r'^\d{1,2}\.\d{1,2}\.', first_text))):
                        if first_text and not first_text.startswith('No '):
                            current_tournament = first_text
                            current_surface = self._guess_surface(current_tournament)
                        continue

                    # Match rows have format: [date, '', 'Player1-Player2', round, score, odds1, odds2]
                    # Need at least 5 cells for a match row
                    if len(cells) < 5:
                        continue

                    # Check for date in first cell (DD.MM. format)
                    date_match = re.match(r'^(\d{1,2})\.(\d{1,2})\.$', first_text)
                    if not date_match:
                        continue

                    # Find match string (Player1-Player2) - usually in cell index 2
                    match_str = None
                    for i, text in enumerate(cell_texts):
                        # Match string has "-" between names (not score format)
                        # Format: "Uchida K.-Marcondes I." or "Marcondes I.-Oberleitner N."
                        if '-' in text and len(text) > 8:
                            # Skip if it's a score (only digits, dashes, commas)
                            if re.match(r'^[\d\-,\s]+$', text):
                                continue
                            # Skip doubles matches (contain " / " or "/ ")
                            if '/' in text:
                                continue
                            # This looks like a match string
                            match_str = text
                            break

                    if not match_str:
                        continue

                    # Parse the match string - players separated by "-" (no spaces)
                    # Split on "-" but be careful not to split on score parts
                    # Pattern: "LastName F.-LastName F."
                    players_match = re.match(r'^([A-Za-z\s\.]+)-([A-Za-z\s\.]+)$', match_str)
                    if not players_match:
                        # Try alternative: might have spaces around dash
                        players_match = re.match(r'^([A-Za-z\s\.]+)\s*-\s*([A-Za-z\s\.]+)$', match_str)

                    if not players_match:
                        continue

                    player1 = players_match.group(1).strip()
                    player2 = players_match.group(2).strip()

                    # Determine winner - player whose name appears FIRST won the match
                    player1_lower = player1.lower()
                    player2_lower = player2.lower()

                    won = False
                    opponent = ""

                    # Check if player1 is our player (our player won if they're first)
                    if (player_last_name in player1_lower or
                        player_first_part in player1_lower or
                        any(part.lower() in player1_lower for part in name_parts)):
                        won = True
                        opponent = player2
                    elif (player_last_name in player2_lower or
                          player_first_part in player2_lower or
                          any(part.lower() in player2_lower for part in name_parts)):
                        won = False
                        opponent = player1
                    else:
                        # Couldn't determine, skip
                        continue

                    # Extract round (usually cell 3)
                    round_name = ""
                    for text in cell_texts:
                        if text in ['1R', '2R', '3R', '4R', 'R16', 'R32', 'R64', 'R128',
                                   'QF', 'SF', 'F', 'RR', 'BR', 'Q-1R', 'Q-R16', 'Q1', 'Q2', 'Q3']:
                            round_name = text
                            break

                    # Extract score (usually cell 4) - format: "6-4, 6-2"
                    score = ""
                    for text in cell_texts:
                        if re.match(r'^\d+-\d+', text) and (',' in text or text.count('-') >= 2):
                            score = text
                            break

                    # Build date
                    day = date_match.group(1).zfill(2)
                    month = date_match.group(2).zfill(2)
                    match_date = f"{year}-{month}-{day}"

                    match_data = {
                        'opponent': opponent,
                        'tournament': current_tournament,
                        'surface': current_surface,
                        'date': match_date,
                        'round': round_name,
                        'score': score,
                        'won': won
                    }

                    matches.append(match_data)

            return matches

        except Exception as e:
            print(f"Error fetching year matches: {e}")
            return matches

    def _guess_surface(self, tournament_name: str, date_str: str = None) -> str:
        """Guess surface from tournament name using centralized detection."""
        from config import get_tournament_surface
        return get_tournament_surface(tournament_name, date_str)

    def fetch_and_update_player(self, player_id: int, player_name: str) -> Dict:
        """Fetch player data from Tennis Explorer and update database."""
        result = {
            'success': False,
            'message': '',
            'matches_added': 0
        }

        # Search for the player
        print(f"Searching Tennis Explorer for: {player_name}")
        player_slug = self.search_player(player_name)

        if not player_slug:
            result['message'] = "Player not found on Tennis Explorer"
            return result

        # Fetch profile
        profile = self.fetch_player_profile(player_slug)

        if not profile:
            result['message'] = "Could not fetch player profile"
            return result

        # Update player info in database
        try:
            # Update basic info if we have a negative ID (auto-added player)
            if player_id < 0:
                player_update = {
                    'country': profile.get('country', ''),
                    'hand': profile.get('hand', 'U'),
                    'height': profile.get('height'),
                    'dob': profile.get('dob'),
                }
                db.update_player_info(player_id, player_update)

            # Add matches to database
            matches_added = 0
            for match in profile.get('matches', []):
                try:
                    # Create a match record
                    # This is simplified - you might want to look up opponent ID too
                    matches_added += 1
                except Exception as e:
                    continue

            # Update ranking if available
            if profile.get('ranking'):
                db.update_player_ranking(player_id, profile['ranking'])
                result['ranking_updated'] = profile['ranking']

            result['success'] = True
            result['message'] = f"Found {len(profile.get('matches', []))} matches"
            if profile.get('ranking'):
                result['message'] += f", ranking updated to {profile['ranking']}"
            result['matches_added'] = matches_added

            # Mark player as updated
            db.update_player_ta_timestamp(player_id)

        except Exception as e:
            result['message'] = f"Error updating database: {e}"

        return result


    def update_player_ranking(self, player_id: int, player_name: str) -> Optional[int]:
        """
        Update a single player's ranking from Tennis Explorer.

        Returns the new ranking if found, None otherwise.
        """
        # Search for the player
        player_slug = self.search_player(player_name)

        if not player_slug:
            return None

        # Fetch profile (just for ranking)
        profile = self.fetch_player_profile(player_slug)

        if not profile or not profile.get('ranking'):
            return None

        # Update the ranking in database
        ranking = profile['ranking']
        db.update_player_ranking(player_id, ranking)

        return ranking

    def update_rankings_for_upcoming_matches(self, progress_callback=None) -> Dict:
        """
        Update rankings for all players in upcoming matches.

        Returns dict with: success, updated_count, failed_count, updates list
        """
        import time

        result = {
            'success': False,
            'updated_count': 0,
            'failed_count': 0,
            'updates': [],
            'message': ''
        }

        # Get all upcoming matches
        upcoming = db.get_upcoming_matches()

        if not upcoming:
            result['message'] = "No upcoming matches found"
            return result

        # Collect unique player IDs and names
        players_to_update = {}
        for match in upcoming:
            p1_id = match.get('player1_id')
            p2_id = match.get('player2_id')
            p1_name = match.get('player1_name')
            p2_name = match.get('player2_name')

            if p1_id and p1_name:
                players_to_update[p1_id] = p1_name
            if p2_id and p2_name:
                players_to_update[p2_id] = p2_name

        total = len(players_to_update)
        if progress_callback:
            progress_callback(f"Updating rankings for {total} players...")

        for i, (player_id, player_name) in enumerate(players_to_update.items()):
            if progress_callback:
                progress_callback(f"[{i+1}/{total}] Updating {player_name}...")

            try:
                new_ranking = self.update_player_ranking(player_id, player_name)

                if new_ranking:
                    result['updated_count'] += 1
                    result['updates'].append({
                        'player_id': player_id,
                        'player_name': player_name,
                        'new_ranking': new_ranking
                    })
                    if progress_callback:
                        progress_callback(f"  → {player_name}: Rank {new_ranking}")
                else:
                    result['failed_count'] += 1

                # Be respectful to the server
                time.sleep(0.5)

            except Exception as e:
                result['failed_count'] += 1
                print(f"Error updating {player_name}: {e}")

        result['success'] = True
        result['message'] = f"Updated {result['updated_count']} players, {result['failed_count']} failed"

        return result

    def fetch_results_day(self, year: int, month: int, day: int, tour_type: str = "atp-single") -> List[Dict]:
        """Fetch match results for a specific day from Tennis Explorer.

        Day-specific URLs contain ALL tournaments including ATP 250 events
        that are missing from month-only URLs.

        Args:
            year: Year (e.g., 2025, 2026)
            month: Month (1-12)
            day: Day (1-31)
            tour_type: 'atp-single', 'wta-single', etc.

        Returns:
            List of match dictionaries
        """
        url = f"{self.BASE_URL}/results/?type={tour_type}&year={year}&month={month:02d}&day={day:02d}"
        return self._parse_results_page(url, year, month, day)

    def fetch_results_page(self, year: int, month: int, tour_type: str = "atp-single",
                          use_day_by_day: bool = True) -> List[Dict]:
        """Fetch match results for a specific month from Tennis Explorer.

        Args:
            year: Year (e.g., 2025, 2026)
            month: Month (1-12)
            tour_type: 'atp-single', 'wta-single', etc.
            use_day_by_day: If True, fetches each day individually for complete data

        Returns:
            List of match dictionaries
        """
        if use_day_by_day:
            # Day-by-day fetching captures ALL tournaments including ATP 250
            import calendar
            import time

            all_matches = []
            days_in_month = calendar.monthrange(year, month)[1]

            # For current month, only fetch up to today
            today = datetime.now()
            if year == today.year and month == today.month:
                days_in_month = min(days_in_month, today.day)

            for day in range(1, days_in_month + 1):
                day_matches = self.fetch_results_day(year, month, day, tour_type)
                all_matches.extend(day_matches)
                time.sleep(0.3)  # Be respectful to the server

            return all_matches

        # Legacy month-only URL (missing some tournaments)
        url = f"{self.BASE_URL}/results/?type={tour_type}&year={year}&month={month:02d}"
        return self._parse_results_page(url, year, month)

    def _parse_results_page(self, url: str, year: int, month: int, day: int = None) -> List[Dict]:
        """Parse match results from a Tennis Explorer results page.

        Args:
            url: The URL to fetch
            year: Year for date construction
            month: Month for date construction
            day: Day (if known) for date construction

        Returns:
            List of match dictionaries
        """
        matches = []

        try:
            response = self.session.get(url, timeout=30)
            if response.status_code != 200:
                print(f"Failed to fetch results: {response.status_code}")
                return matches

            soup = BeautifulSoup(response.text, 'html.parser')

            current_tournament = ""
            current_surface = "Hard"
            # If day is provided (day-specific URL), use it as the default date
            if day:
                current_date = f"{year}-{month:02d}-{day:02d}"
            else:
                current_date = f"{year}-{month:02d}-01"

            # Find all tables with match data
            tables = soup.select('table')

            for table in tables:
                rows = table.select('tr')
                i = 0

                while i < len(rows):
                    row = rows[i]
                    row_class = row.get('class', [])

                    # Check for tournament header - has t-name but no player link
                    t_name = row.select_one('td.t-name, th.t-name')
                    player_link = row.select_one('a[href*="/player/"]')
                    if t_name and not player_link:
                        # This is likely a tournament header row
                        text = t_name.get_text(strip=True)
                        # Skip if it looks like a date
                        if not re.match(r'^\d', text):
                            current_tournament = text
                            current_surface = self._guess_surface(current_tournament)
                        i += 1
                        continue

                    # Check for date in row (format like "18.01." in first cell)
                    cells = row.select('td')
                    if cells:
                        first_cell = cells[0].get_text(strip=True)
                        date_match = re.match(r'^(\d{1,2})\.(\d{1,2})\.$', first_cell)
                        if date_match:
                            parsed_day, month_num = date_match.groups()
                            current_date = f"{year}-{month_num.zfill(2)}-{parsed_day.zfill(2)}"

                    # Match rows come in pairs - check if this is a first row of a match
                    # First row has class 'bott' and contains winner info
                    if 'bott' in row_class:
                        player1_link = row.select_one('a[href*="/player/"]')
                        if player1_link and i + 1 < len(rows):
                            next_row = rows[i + 1]
                            player2_link = next_row.select_one('a[href*="/player/"]')

                            if player2_link:
                                try:
                                    # Get player names (remove seeding numbers like "(20)")
                                    player1_name = re.sub(r'\(\d+\)$', '', player1_link.get_text(strip=True)).strip()
                                    player2_name = re.sub(r'\(\d+\)$', '', player2_link.get_text(strip=True)).strip()

                                    # Skip doubles
                                    if '/' in player1_name or '/' in player2_name:
                                        i += 2
                                        continue

                                    # Get set scores from both rows
                                    cells1 = row.select('td')
                                    cells2 = next_row.select('td')

                                    # Extract scores - look for the total sets won (usually 3rd cell)
                                    p1_sets = 0
                                    p2_sets = 0
                                    p1_scores = []
                                    p2_scores = []

                                    for cell in cells1:
                                        text = cell.get_text(strip=True)
                                        # Match set scores (single digit, or with tiebreak like "62")
                                        if re.match(r'^\d{1,2}$', text):
                                            p1_scores.append(text)

                                    for cell in cells2:
                                        text = cell.get_text(strip=True)
                                        if re.match(r'^\d{1,2}$', text):
                                            p2_scores.append(text)

                                    # First score is usually total sets won
                                    if p1_scores:
                                        p1_sets = int(p1_scores[0]) if p1_scores[0].isdigit() else 0
                                    if p2_scores:
                                        p2_sets = int(p2_scores[0]) if p2_scores[0].isdigit() else 0

                                    # Determine winner (more sets won)
                                    if p1_sets > p2_sets:
                                        winner_name = player1_name
                                        loser_name = player2_name
                                        winner_scores = p1_scores[1:]  # Skip total
                                        loser_scores = p2_scores[1:]
                                    else:
                                        winner_name = player2_name
                                        loser_name = player1_name
                                        winner_scores = p2_scores[1:]
                                        loser_scores = p1_scores[1:]

                                    # Build score string
                                    score_parts = []
                                    for j in range(min(len(winner_scores), len(loser_scores))):
                                        score_parts.append(f"{winner_scores[j]}-{loser_scores[j]}")
                                    score = " ".join(score_parts)

                                    match_data = {
                                        'winner_name': winner_name,
                                        'loser_name': loser_name,
                                        'tournament': current_tournament,
                                        'surface': current_surface,
                                        'date': current_date,
                                        'score': score,
                                        'year': year
                                    }

                                    matches.append(match_data)
                                    i += 2  # Skip both rows
                                    continue

                                except Exception as e:
                                    pass

                    i += 1

            return matches

        except Exception as e:
            print(f"Error fetching results: {e}")
            return matches

    def fetch_recent_days(self, days_back: int = 7, tour_type: str = "atp-single",
                          progress_callback=None) -> List[Dict]:
        """Fetch match results for a specific number of recent days.

        This is much faster than fetch_recent_results as it only fetches
        a limited number of days instead of full months.

        Args:
            days_back: Number of days to fetch (default 7)
            tour_type: Tour type to fetch (e.g., 'atp-single', 'wta-single')
            progress_callback: Optional callback for progress updates

        Returns:
            List of match dictionaries
        """
        import time

        all_matches = []
        today = datetime.now()
        tour_label = "ATP" if "atp" in tour_type else ("WTA" if "wta" in tour_type else "ITF")

        for i in range(days_back):
            target_date = today - timedelta(days=i)
            year = target_date.year
            month = target_date.month
            day = target_date.day

            if progress_callback:
                progress_callback(f"  Fetching {tour_label} {target_date.strftime('%Y-%m-%d')}...")

            day_matches = self.fetch_results_day(year, month, day, tour_type)
            all_matches.extend(day_matches)

            # Small delay to be respectful to server
            if i < days_back - 1:
                time.sleep(0.3)

        if progress_callback:
            progress_callback(f"  Found {len(all_matches)} {tour_label} matches")

        return all_matches

    def fetch_recent_results(self, months_back: int = 3, tour_types: List[str] = None,
                            progress_callback=None) -> List[Dict]:
        """Fetch recent match results from Tennis Explorer.

        Args:
            months_back: Number of months to fetch (default 3)
            tour_types: List of tour types to fetch (default: ATP and WTA singles)
            progress_callback: Optional callback for progress updates

        Returns:
            List of all match dictionaries
        """
        if tour_types is None:
            tour_types = ["atp-single", "wta-single"]

        all_matches = []
        now = datetime.now()

        for tour_type in tour_types:
            tour_label = "ATP" if "atp" in tour_type else "WTA"

            for i in range(months_back):
                # Calculate year/month going backwards
                target_date = datetime(now.year, now.month, 1)
                for _ in range(i):
                    target_date = target_date.replace(day=1) - timedelta(days=1)
                    target_date = target_date.replace(day=1)

                year = target_date.year
                month = target_date.month

                if progress_callback:
                    progress_callback(f"Fetching {tour_label} results for {year}-{month:02d}...")

                matches = self.fetch_results_page(year, month, tour_type)
                all_matches.extend(matches)

                if progress_callback:
                    progress_callback(f"Found {len(matches)} {tour_label} matches for {year}-{month:02d}")

                # Small delay to be respectful
                import time
                time.sleep(0.5)

        return all_matches

    def import_results_to_database(self, matches: List[Dict], progress_callback=None,
                                    players_locked: bool = True) -> Dict:
        """Import scraped match results into the database.

        Args:
            matches: List of match dictionaries from fetch_recent_results
            progress_callback: Optional callback for progress updates
            players_locked: If True, skip matches with unknown players (no new players created)
                           If False, create new players with negative IDs

        Returns:
            Dictionary with import statistics
        """
        from datetime import timedelta

        stats = {
            'matches_imported': 0,
            'players_created': 0,
            'players_matched': 0,
            'matches_skipped': 0,
            'errors': 0
        }

        # Use the robust PlayerNameMatcher for player lookup
        name_matcher = PlayerNameMatcher()
        try:
            with db.get_connection() as conn:
                name_matcher.load_players(conn)
            if progress_callback:
                progress_callback(f"Loaded {len(name_matcher.players)} players for matching")
                if players_locked:
                    progress_callback("Players LOCKED - unknown players will be skipped")
        except Exception as e:
            print(f"Error loading players: {e}")

        # Track new players to create (only used if players_locked=False)
        new_players = {}
        next_negative_id = -1
        if not players_locked:
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT MIN(id) FROM players WHERE id < 0")
                    result = cursor.fetchone()
                    if result[0]:
                        next_negative_id = result[0] - 1
            except:
                pass

        if progress_callback:
            progress_callback(f"Processing {len(matches)} matches...")

        matches_to_insert = []
        matched_count = 0
        created_count = 0
        skipped_count = 0

        for match in matches:
            try:
                winner_name = match['winner_name']
                loser_name = match['loser_name']

                # Look up winner using robust name matcher
                winner_key = name_matcher._normalize(winner_name)
                winner_id = name_matcher.find_player_id(winner_name)
                if winner_id:
                    matched_count += 1
                    # Use canonical name from database for consistency
                    canonical_name = name_matcher.get_player_name(winner_id)
                    if canonical_name:
                        winner_name = canonical_name
                elif players_locked:
                    # Players locked - skip this match
                    skipped_count += 1
                    continue
                elif winner_key in new_players:
                    winner_id = new_players[winner_key]
                else:
                    winner_id = next_negative_id
                    new_players[winner_key] = winner_id
                    name_matcher.add_player(winner_id, winner_name)
                    next_negative_id -= 1
                    created_count += 1

                # Look up loser using robust name matcher
                loser_key = name_matcher._normalize(loser_name)
                loser_id = name_matcher.find_player_id(loser_name)
                if loser_id:
                    matched_count += 1
                    # Use canonical name from database for consistency
                    canonical_name = name_matcher.get_player_name(loser_id)
                    if canonical_name:
                        loser_name = canonical_name
                elif players_locked:
                    # Players locked - skip this match
                    skipped_count += 1
                    continue
                elif loser_key in new_players:
                    loser_id = new_players[loser_key]
                else:
                    loser_id = next_negative_id
                    new_players[loser_key] = loser_id
                    name_matcher.add_player(loser_id, loser_name)
                    next_negative_id -= 1
                    created_count += 1

                # Create match record
                match_record = {
                    'tournament': match.get('tournament', 'Unknown'),
                    'surface': match.get('surface', 'Hard'),
                    'date': match.get('date'),
                    'winner_id': winner_id,
                    'winner_name': winner_name,
                    'loser_id': loser_id,
                    'loser_name': loser_name,
                    'score': match.get('score', ''),
                }

                matches_to_insert.append(match_record)

            except Exception as e:
                stats['errors'] += 1
                continue

        stats['players_matched'] = matched_count
        stats['matches_skipped'] = skipped_count
        if progress_callback:
            if players_locked:
                progress_callback(f"Matched {matched_count} players, skipped {skipped_count} matches (unknown players)")
            else:
                progress_callback(f"Matched {matched_count} player references, creating {len(new_players)} new players")

        # Insert new players (only if not locked)
        if new_players and not players_locked:
            if progress_callback:
                progress_callback(f"Creating {len(new_players)} new players...")

            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    for name, player_id in new_players.items():
                        # Convert name back to title case
                        display_name = name.title()
                        cursor.execute("""
                            INSERT OR IGNORE INTO players (id, name, country, hand)
                            VALUES (?, ?, '', 'U')
                        """, (player_id, display_name))
                    conn.commit()
                    stats['players_created'] = len(new_players)
            except Exception as e:
                print(f"Error creating players: {e}")

        # Insert matches
        if matches_to_insert:
            if progress_callback:
                progress_callback(f"Inserting {len(matches_to_insert)} matches...")

            try:
                # Import validator for data validation
                try:
                    from data_validation import validate_match_data
                except ImportError:
                    validate_match_data = None

                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    inserted = 0
                    rejected = 0
                    for m in matches_to_insert:
                        # Generate a unique match ID
                        match_id = f"TE_{m['date']}_{m['winner_id']}_{m['loser_id']}"

                        # Prepare match data for validation
                        match_data = {
                            'id': match_id,
                            'tournament': m['tournament'],
                            'tourney_name': m['tournament'],
                            'surface': m['surface'],
                            'date': m['date'],
                            'winner_id': m['winner_id'],
                            'winner_name': m['winner_name'],
                            'loser_id': m['loser_id'],
                            'loser_name': m['loser_name'],
                            'score': m['score'],
                        }

                        # Validate before insertion
                        if validate_match_data:
                            is_valid, errors = validate_match_data(match_data, source="tennis_explorer")
                            if not is_valid:
                                rejected += 1
                                continue  # Skip invalid matches

                        cursor.execute("""
                            INSERT OR IGNORE INTO matches
                            (id, tournament, surface, date, winner_id, winner_name, loser_id, loser_name, score)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (match_id, m['tournament'], m['surface'], m['date'],
                              m['winner_id'], m['winner_name'], m['loser_id'], m['loser_name'], m['score']))
                        if cursor.rowcount > 0:
                            inserted += 1
                    conn.commit()
                    stats['matches_imported'] = inserted
                    if rejected > 0:
                        print(f"[VALIDATION] Rejected {rejected} invalid matches from Tennis Explorer")
            except Exception as e:
                print(f"Error inserting matches: {e}")

        return stats

    def fetch_player_match_history(self, player_id: int, player_name: str,
                                   limit: int = 50, years_back: int = 2,
                                   progress_callback=None) -> Dict:
        """
        Fetch and import match history for a specific player from year-specific pages.

        Args:
            player_id: Database ID of the player
            player_name: Player's name for searching
            limit: Maximum number of matches to import (default 50)
            years_back: How many years back to fetch (default 2)
            progress_callback: Optional callback for progress updates

        Returns:
            Dict with success status and counts
        """
        import time

        stats = {
            'success': False,
            'message': '',
            'matches_found': 0,
            'matches_imported': 0,
            'players_created': 0
        }

        if progress_callback:
            progress_callback(f"Searching for {player_name}...")

        # Search for player
        slug = self.search_player(player_name)
        if not slug:
            stats['message'] = f"Could not find {player_name} on Tennis Explorer"
            return stats

        if progress_callback:
            progress_callback(f"Found player ({slug}), fetching match history...")

        # Fetch matches from year-specific pages (most recent years first)
        current_year = datetime.now().year
        all_matches = []

        for year in range(current_year, current_year - years_back - 1, -1):
            if progress_callback:
                progress_callback(f"Fetching {year} matches for {player_name}...")

            year_matches = self.fetch_player_year_matches(slug, player_name, year)
            all_matches.extend(year_matches)

            if progress_callback:
                progress_callback(f"Found {len(year_matches)} matches in {year}")

            # Stop if we have enough
            if len(all_matches) >= limit:
                break

            time.sleep(0.3)  # Be respectful to server

        matches = all_matches[:limit]
        stats['matches_found'] = len(all_matches)

        if not matches:
            stats['message'] = "No matches found on Tennis Explorer"
            return stats

        if progress_callback:
            progress_callback(f"Processing {len(matches)} matches...")

        # Use robust PlayerNameMatcher for opponent lookup
        name_matcher = PlayerNameMatcher()
        try:
            with db.get_connection() as conn:
                name_matcher.load_players(conn)
        except Exception as e:
            print(f"Error loading players for matching: {e}")

        # Get next negative ID for creating new players
        next_negative_id = -1
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT MIN(id) FROM players WHERE id < 0")
                result = cursor.fetchone()
                if result[0]:
                    next_negative_id = result[0] - 1
        except:
            pass

        # Process each match
        matches_to_insert = []
        new_players = {}  # normalized opponent_name -> player_id

        print(f"DEBUG HISTORY IMPORT: player_id={player_id}, player_name={player_name}")

        for match in matches:
            opponent_name = match.get('opponent', '').strip()
            if not opponent_name:
                continue

            # Look up or create opponent using robust name matcher
            opponent_key = name_matcher._normalize(opponent_name)
            if opponent_key not in new_players:
                # Check if opponent exists in database
                opponent_id = name_matcher.find_player_id(opponent_name)
                if opponent_id:
                    new_players[opponent_key] = opponent_id
                    # Get canonical name for consistency
                    canonical_name = name_matcher.get_player_name(opponent_id)
                    if canonical_name:
                        opponent_name = canonical_name
                else:
                    # Create new auto-ID for opponent
                    new_players[opponent_key] = next_negative_id
                    name_matcher.add_player(next_negative_id, opponent_name)
                    next_negative_id -= 1

            opponent_id = new_players[opponent_key]

            # Skip if both IDs are the same (shouldn't happen)
            if player_id == opponent_id:
                continue

            # Determine winner/loser
            won = match.get('won', False)
            if won:
                winner_id = player_id
                winner_name = player_name
                loser_id = opponent_id
                loser_name = opponent_name
            else:
                winner_id = opponent_id
                winner_name = opponent_name
                loser_id = player_id
                loser_name = player_name

            matches_to_insert.append({
                'tournament': match.get('tournament', 'Unknown'),
                'surface': match.get('surface', 'Hard'),
                'date': match.get('date', ''),
                'winner_id': winner_id,
                'winner_name': winner_name,
                'loser_id': loser_id,
                'loser_name': loser_name,
                'score': match.get('score', ''),
                'round': match.get('round', '')
            })

        if not matches_to_insert:
            stats['message'] = "No valid matches to import"
            return stats

        # Create new players first
        players_to_create = [(pid, name.title()) for name, pid in new_players.items()
                            if pid < 0 and not db.get_player(pid)]

        if players_to_create:
            if progress_callback:
                progress_callback(f"Creating {len(players_to_create)} opponent records...")

            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    for pid, name in players_to_create:
                        cursor.execute("""
                            INSERT OR IGNORE INTO players (id, name, country, hand)
                            VALUES (?, ?, '', 'U')
                        """, (pid, name))
                    conn.commit()
                    stats['players_created'] = len(players_to_create)
            except Exception as e:
                print(f"Error creating players: {e}")

        # Insert matches
        if progress_callback:
            progress_callback(f"Inserting {len(matches_to_insert)} matches...")

        try:
            # Import validator
            try:
                from data_validation import validate_match_data
            except ImportError:
                validate_match_data = None

            with db.get_connection() as conn:
                cursor = conn.cursor()
                inserted = 0
                for m in matches_to_insert:
                    # Generate unique match ID
                    match_id = f"TE_{m['date']}_{m['winner_id']}_{m['loser_id']}"

                    # Prepare match data for validation
                    match_data = {
                        'id': match_id,
                        'tournament': m['tournament'],
                        'tourney_name': m['tournament'],
                        'surface': m['surface'],
                        'date': m['date'],
                        'winner_id': m['winner_id'],
                        'winner_name': m['winner_name'],
                        'loser_id': m['loser_id'],
                        'loser_name': m['loser_name'],
                        'score': m['score'],
                        'round': m['round']
                    }

                    # Validate
                    if validate_match_data:
                        is_valid, errors = validate_match_data(match_data, source="tennis_explorer")
                        if not is_valid:
                            continue

                    cursor.execute("""
                        INSERT OR IGNORE INTO matches
                        (id, tournament, surface, date, round, winner_id, winner_name, loser_id, loser_name, score)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (match_id, m['tournament'], m['surface'], m['date'], m['round'],
                          m['winner_id'], m['winner_name'], m['loser_id'], m['loser_name'], m['score']))

                    if cursor.rowcount > 0:
                        inserted += 1

                conn.commit()
                stats['matches_imported'] = inserted

        except Exception as e:
            stats['message'] = f"Error inserting matches: {e}"
            return stats

        # Post-import: merge auto-created players to real players and deduplicate
        if progress_callback:
            progress_callback("Merging auto-created players to real players...")

        auto_player_ids = [pid for pid in new_players.values() if pid < 0]
        merge_stats = self._merge_auto_players_and_dedupe(auto_player_ids, progress_callback)

        stats['players_merged'] = merge_stats.get('players_merged', 0)
        stats['duplicates_removed'] = merge_stats.get('duplicates_removed', 0)

        # Adjust players_created count (subtract merged ones)
        stats['players_created'] = max(0, stats['players_created'] - stats['players_merged'])

        stats['success'] = True
        msg = f"Imported {stats['matches_imported']} matches for {player_name}"
        if stats['players_merged'] > 0:
            msg += f", merged {stats['players_merged']} players"
        if stats['duplicates_removed'] > 0:
            msg += f", removed {stats['duplicates_removed']} duplicates"
        stats['message'] = msg

        return stats

    def _merge_auto_players_and_dedupe(self, auto_player_ids: List[int],
                                        progress_callback=None) -> Dict:
        """
        Merge auto-created players (negative IDs) into matching real players,
        then deduplicate any resulting duplicate matches.

        Args:
            auto_player_ids: List of auto-created player IDs (negative) to check
            progress_callback: Optional callback for progress updates

        Returns:
            Dict with merge statistics
        """
        stats = {
            'players_merged': 0,
            'duplicates_removed': 0
        }

        if not auto_player_ids:
            return stats

        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()

                # Build index of real players by last name for matching
                cursor.execute("SELECT id, name FROM players WHERE id > 0")
                real_players_by_lastname = {}
                for row in cursor.fetchall():
                    pid, name = row
                    # Try to extract last name (could be "FirstName LastName" or "LastName FirstName")
                    parts = name.split()
                    if parts:
                        # Index by each word (both first and last name)
                        for part in parts:
                            key = part.lower().rstrip('.')
                            if len(key) > 1:  # Skip initials
                                if key not in real_players_by_lastname:
                                    real_players_by_lastname[key] = []
                                real_players_by_lastname[key].append((pid, name))

                # Process each auto-created player
                merged_player_ids = set()

                for auto_id in auto_player_ids:
                    # Get auto player's name
                    cursor.execute("SELECT name FROM players WHERE id = ?", (auto_id,))
                    row = cursor.fetchone()
                    if not row:
                        continue

                    auto_name = row[0]
                    # Parse name - format is usually "LastName F." or "Lastname Firstname"
                    parts = auto_name.split()
                    if not parts:
                        continue

                    # Extract last name (first word, strip trailing period)
                    last_name = parts[0].lower().rstrip('.')

                    # Extract first initial if available
                    first_initial = None
                    if len(parts) > 1:
                        first_initial = parts[1][0].lower() if parts[1] else None

                    # Look for matching real player
                    candidates = real_players_by_lastname.get(last_name, [])

                    best_match = None
                    for real_id, real_name in candidates:
                        if real_id == auto_id:
                            continue

                        real_parts = real_name.split()
                        if not real_parts:
                            continue

                        # Check if first initial matches
                        if first_initial:
                            # Real name could be "FirstName LastName" or "LastName FirstName"
                            matches_initial = False
                            for rpart in real_parts:
                                if rpart.lower().startswith(first_initial) and len(rpart) > 1:
                                    matches_initial = True
                                    break

                            if matches_initial:
                                best_match = (real_id, real_name)
                                break
                        elif len(candidates) == 1:
                            # No initial to check, but only one candidate
                            best_match = (real_id, real_name)
                            break

                    if best_match:
                        real_id, real_name = best_match

                        # Merge: update all matches to use real player ID
                        cursor.execute("""
                            UPDATE matches SET winner_id = ?, winner_name = ?
                            WHERE winner_id = ?
                        """, (real_id, real_name, auto_id))
                        winner_updated = cursor.rowcount

                        cursor.execute("""
                            UPDATE matches SET loser_id = ?, loser_name = ?
                            WHERE loser_id = ?
                        """, (real_id, real_name, auto_id))
                        loser_updated = cursor.rowcount

                        if winner_updated > 0 or loser_updated > 0:
                            # Delete the auto player
                            cursor.execute("DELETE FROM players WHERE id = ?", (auto_id,))
                            stats['players_merged'] += 1
                            merged_player_ids.add(real_id)

                            if progress_callback:
                                progress_callback(f"  Merged '{auto_name}' -> '{real_name}'")

                conn.commit()

                # Now deduplicate matches for merged players
                if merged_player_ids:
                    if progress_callback:
                        progress_callback("Removing duplicate matches...")

                    # Find and remove duplicate matches
                    # Duplicates have same date, same players (by ID), similar score
                    for player_id in merged_player_ids:
                        cursor.execute("""
                            SELECT id, date, winner_id, loser_id, score, tournament
                            FROM matches
                            WHERE winner_id = ? OR loser_id = ?
                            ORDER BY date, winner_id, loser_id
                        """, (player_id, player_id))

                        matches = cursor.fetchall()

                        # Group by date + winner_id + loser_id
                        seen = {}
                        duplicates_to_delete = []

                        for match in matches:
                            mid, date, w_id, l_id, score, tourn = match
                            # Normalize score for comparison (just digits)
                            score_digits = ''.join(c for c in (score or '') if c.isdigit())[:6]
                            key = f"{date}_{w_id}_{l_id}_{score_digits}"

                            if key in seen:
                                # This is a duplicate - keep the one with more info
                                existing = seen[key]
                                # Prefer the one with tournament name
                                if len(tourn or '') > len(existing[5] or ''):
                                    # Current one is better, delete existing
                                    duplicates_to_delete.append(existing[0])
                                    seen[key] = match
                                else:
                                    # Existing is better, delete current
                                    duplicates_to_delete.append(mid)
                            else:
                                seen[key] = match

                        # Delete duplicates
                        for dup_id in duplicates_to_delete:
                            cursor.execute("DELETE FROM matches WHERE id = ?", (dup_id,))
                            stats['duplicates_removed'] += 1

                    conn.commit()

        except Exception as e:
            print(f"Error in merge/dedupe: {e}")

        return stats


def test_scraper():
    """Test the Tennis Explorer scraper."""
    scraper = TennisExplorerScraper()

    # Test with Kayla Day
    print("Testing Tennis Explorer scraper with Kayla Day...")

    slug = scraper.search_player("Kayla Day")
    print(f"Found player slug: {slug}")

    if slug:
        profile = scraper.fetch_player_profile(slug)
        if profile:
            print(f"\nPlayer: {profile['name']}")
            print(f"Country: {profile['country']}")
            print(f"DOB: {profile['dob']}")
            print(f"Height: {profile['height']}cm")
            print(f"Hand: {profile['hand']}")
            print(f"Ranking: {profile['ranking']}")
            print(f"\nRecent matches: {len(profile['matches'])}")
            for match in profile['matches'][:5]:
                print(f"  vs {match['opponent']} - {match['tournament']} ({match['surface']})")


def test_results_scraper():
    """Test the match results scraper."""
    scraper = TennisExplorerScraper()

    print("Testing Tennis Explorer results scraper...")
    print("Fetching January 2026 ATP results...")

    matches = scraper.fetch_results_page(2026, 1, "atp-single")

    print(f"\nFound {len(matches)} matches")
    for match in matches[:10]:
        print(f"  {match['winner_name']} def. {match['loser_name']} - {match['tournament']} ({match['date']})")


if __name__ == "__main__":
    test_results_scraper()
