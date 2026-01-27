"""
Flashscore Results Checker - Lookup specific match results using Selenium
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import re
import time
from typing import Dict, List, Optional


class FlashscoreChecker:
    """Check tennis match results from Flashscore using Selenium."""

    BASE_URL = "https://www.flashscore.com"

    def __init__(self, headless: bool = True):
        """Initialize with Chrome WebDriver."""
        self.headless = headless
        self.driver = None
        self._player_cache = {}  # Cache player page URLs

    def _get_driver(self):
        """Create and return a Chrome WebDriver."""
        if self.driver is None:
            options = Options()
            if self.headless:
                options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option('excludeSwitches', ['enable-automation'])

            self.driver = webdriver.Chrome(options=options)
        return self.driver

    def close(self):
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def _normalize_name(self, name: str) -> str:
        """Normalize player name for comparison."""
        if not name:
            return ""
        name = name.lower().strip()
        name = re.sub(r'\s+', ' ', name)
        name = re.sub(r'\s*\([^)]*\)\s*', '', name)
        name = name.replace('.', '').replace('-', ' ')
        return name

    def _names_match(self, name1: str, name2: str) -> bool:
        """Check if two player names match."""
        n1 = self._normalize_name(name1)
        n2 = self._normalize_name(name2)

        if not n1 or not n2:
            return False

        if n1 == n2:
            return True

        if n1 in n2 or n2 in n1:
            return True

        # Split into parts and check for overlap
        parts1 = set(n1.split())
        parts2 = set(n2.split())

        # Check if any significant parts match (names with 3+ chars)
        significant1 = {p for p in parts1 if len(p) > 2}
        significant2 = {p for p in parts2 if len(p) > 2}

        if significant1 and significant2:
            # If any significant part matches, consider it a match
            common = significant1 & significant2
            if common:
                return True

            # Also check partial matches (one contains the other)
            for p1 in significant1:
                for p2 in significant2:
                    if len(p1) > 3 and len(p2) > 3:
                        if p1 in p2 or p2 in p1:
                            return True

        return False

    def _search_player(self, player_name: str) -> Optional[str]:
        """
        Search for a player and return their results page URL.

        Returns: URL like 'https://www.flashscore.com/player/sinner-jannik/6HdC3z4H/results/'
        """
        # Check cache first
        cache_key = self._normalize_name(player_name)
        if cache_key in self._player_cache:
            return self._player_cache[cache_key]

        driver = self._get_driver()
        # Use longest word as search term (usually the surname)
        name_parts = player_name.split()
        search_term = max(name_parts, key=len) if name_parts else player_name

        try:
            # Go to Flashscore tennis
            driver.get(f"{self.BASE_URL}/tennis/")
            time.sleep(2)

            # Click on search area
            search_block = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '#searchWindow'))
            )
            search_block.click()
            time.sleep(1)

            # Find and use the search input
            search_input = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'input.searchInput__input'))
            )
            search_input.send_keys(search_term)
            time.sleep(2)

            # Find player in search results (look for TENNIS + exact name match)
            results = driver.find_elements(By.CSS_SELECTOR, '.searchResult')

            # Get normalized name parts for verification
            name_parts = set(self._normalize_name(player_name).split())
            significant_parts = {p for p in name_parts if len(p) > 3}

            for result in results:
                text = result.text
                result_lower = text.lower()

                # Must be tennis player
                if 'TENNIS' not in text:
                    continue

                # Check that ALL significant name parts appear in the result
                result_normalized = self._normalize_name(text)
                all_parts_match = all(part in result_normalized for part in significant_parts)

                if all_parts_match and significant_parts:
                    result.click()
                    time.sleep(2)

                    # Get the player page URL
                    current_url = driver.current_url
                    if '/player/' in current_url:
                        # Navigate to results page
                        results_url = current_url.rstrip('/') + '/results/'
                        self._player_cache[cache_key] = results_url
                        return results_url

            return None

        except Exception as e:
            print(f"Error searching for player {player_name}: {e}")
            return None

    def lookup_match_result(self, player1: str, player2: str) -> Optional[Dict]:
        """
        Lookup match result between two players on Flashscore.

        Returns: Dict with 'winner', 'loser', 'score' or None
        """
        driver = self._get_driver()

        # Try to find player1's results page
        results_url = self._search_player(player1)

        if not results_url:
            # Try player2 instead
            results_url = self._search_player(player2)
            if not results_url:
                return None

        try:
            # Navigate to results page
            driver.get(results_url)
            time.sleep(2)

            # Find match against opponent
            return self._find_match_on_results_page(driver, player1, player2)

        except Exception as e:
            print(f"Error looking up {player1} vs {player2}: {e}")
            return None

    def _find_match_on_results_page(self, driver, player1: str, player2: str) -> Optional[Dict]:
        """Find match result on player's results page."""
        try:
            # Check if opponent appears on page
            page_text = driver.page_source.lower()
            p1_last = self._normalize_name(player1).split()[-1]
            p2_last = self._normalize_name(player2).split()[-1]

            if p1_last not in page_text and p2_last not in page_text:
                return None

            # Find match rows
            match_rows = driver.find_elements(By.CSS_SELECTOR, '.event__match')

            for row in match_rows:
                try:
                    # Get participants
                    participants = row.find_elements(By.CSS_SELECTOR, '.event__participant')
                    if len(participants) < 2:
                        continue

                    name1 = participants[0].text.strip()
                    name2 = participants[1].text.strip()

                    # Check if this match involves both players
                    has_p1 = self._names_match(name1, player1) or self._names_match(name2, player1)
                    has_p2 = self._names_match(name1, player2) or self._names_match(name2, player2)

                    if has_p1 and has_p2:
                        # Found the match!
                        # Get win/loss from badge (W/L indicator)
                        badges = row.find_elements(By.CSS_SELECTOR, '[class*="wcl-win"], [class*="wcl-lose"]')
                        is_win = False
                        for badge in badges:
                            badge_class = badge.get_attribute('class') or ''
                            if 'wcl-win' in badge_class:
                                is_win = True
                                break
                            elif 'wcl-lose' in badge_class:
                                is_win = False
                                break

                        # Get score - on results page it's just sets won (e.g., 2-0)
                        score_home = row.find_elements(By.CSS_SELECTOR, '.event__score--home')
                        score_away = row.find_elements(By.CSS_SELECTOR, '.event__score--away')

                        formatted_score = ""
                        if score_home and score_away:
                            s1 = score_home[0].text.strip()
                            s2 = score_away[0].text.strip()
                            formatted_score = f"{s1}-{s2}"

                        # Determine winner based on page context
                        # The results page belongs to one player
                        # is_win means that page's player won this match

                        # Get page player from URL slug (e.g., "darderi-lorenzo" -> "darderi")
                        page_player_surname = ""
                        if '/player/' in driver.current_url:
                            url_match = re.search(r'/player/([^/]+)/', driver.current_url)
                            if url_match:
                                slug = url_match.group(1)
                                page_player_surname = slug.split('-')[0] if slug else ''

                        # Figure out which of our search players is the page owner
                        page_is_player1 = (page_player_surname and
                                           page_player_surname in self._normalize_name(player1))
                        page_is_player2 = (page_player_surname and
                                           page_player_surname in self._normalize_name(player2))

                        # Determine winner
                        if page_is_player1:
                            # Page belongs to player1
                            winner = player1 if is_win else player2
                        elif page_is_player2:
                            # Page belongs to player2
                            winner = player2 if is_win else player1
                        else:
                            # Fallback: check match row participants against our players
                            # and use score to determine winner
                            if self._names_match(name1, player1):
                                winner = player1 if is_win else player2
                            else:
                                winner = player2 if is_win else player1

                        loser = player2 if self._names_match(winner, player1) else player1

                        return {
                            'winner': winner,
                            'loser': loser,
                            'score': formatted_score
                        }

                except Exception as e:
                    continue

            return None

        except Exception as e:
            print(f"Error finding match on page: {e}")
            return None


def check_flashscore_results(db, max_bets: int = 10, progress_callback=None) -> Dict:
    """
    Check pending bet results using Flashscore.

    Args:
        db: Database instance
        max_bets: Maximum bets to check
        progress_callback: Optional callback(current, total, player1, player2) for progress updates

    Returns:
        Dict with results
    """
    checker = FlashscoreChecker(headless=True)
    results = {
        'settled': 0,
        'wins': 0,
        'losses': 0,
        'not_found': 0,
        'checked': 0,
        'total': 0,
        'details': []
    }

    try:
        # Get pending bets
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, match_date, player1, player2, selection, match_description, stake, odds
                FROM bets
                WHERE result IS NULL
                ORDER BY match_date DESC
                LIMIT ?
            """, (max_bets,))

            columns = ['id', 'match_date', 'player1', 'player2', 'selection', 'match_description', 'stake', 'odds']
            pending_bets = [dict(zip(columns, row)) for row in cursor.fetchall()]

        if not pending_bets:
            return results

        results['total'] = len(pending_bets)
        print(f"Checking {len(pending_bets)} pending bets on Flashscore...")

        for idx, bet in enumerate(pending_bets):
            bet_id = bet['id']
            player1 = bet['player1'] or ''
            player2 = bet['player2'] or ''
            selection = bet['selection'] or ''

            # Extract names from description if needed
            if not player1 or not player2:
                match_desc = bet.get('match_description', '')
                for sep in [' vs ', ' v ', ' - ']:
                    if sep in match_desc:
                        parts = match_desc.split(sep, 1)
                        if len(parts) == 2:
                            player1 = parts[0].strip()
                            player2 = parts[1].strip()
                            break

            if not player1 or not player2:
                results['not_found'] += 1
                continue

            results['checked'] += 1

            # Report progress
            if progress_callback:
                progress_callback(idx + 1, len(pending_bets), player1, player2)

            print(f"  Looking up: {player1} vs {player2}...")

            match_result = checker.lookup_match_result(player1, player2)

            if match_result:
                winner = match_result['winner']
                loser = match_result['loser']
                score = match_result.get('score', '')

                selection_won = checker._names_match(selection, winner)
                bet_result = 'Win' if selection_won else 'Loss'

                stake = bet.get('stake', 0) or 0
                odds = bet.get('odds', 0) or 0
                commission = 0.05

                if bet_result == 'Win':
                    profit_loss = stake * (odds - 1) * (1 - commission)
                    results['wins'] += 1
                else:
                    profit_loss = -stake
                    results['losses'] += 1

                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE bets SET result = ?, profit_loss = ? WHERE id = ?
                    """, (bet_result, profit_loss, bet_id))
                    conn.commit()

                results['settled'] += 1
                opponent = loser if selection_won else winner
                results['details'].append({
                    'bet_id': bet_id,
                    'selection': selection,
                    'result': bet_result,
                    'opponent': opponent,
                    'score': score
                })

                print(f"    Found: {selection} {bet_result} (vs {opponent}, {score})")
            else:
                results['not_found'] += 1
                print(f"    Not found")

            time.sleep(1)

    finally:
        checker.close()

    return results


# Backward compatibility
def check_results_flashscore(db) -> Dict:
    return check_flashscore_results(db, max_bets=10)


if __name__ == "__main__":
    checker = FlashscoreChecker(headless=False)  # Show browser for testing
    try:
        result = checker.lookup_match_result("Jannik Sinner", "Ben Shelton")
        print(f"Result: {result}")
    finally:
        checker.close()
