"""
Tennis Betting System - Rankings Downloader
Downloads ATP and WTA rankings from Tennis Explorer and stores them locally.
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable

from config import DATA_DIR
from database import db


# Rankings cache file
RANKINGS_FILE = DATA_DIR / "rankings_cache.json"
# File for rankings name mappings (DB name -> Rankings name)
RANKINGS_MAPPINGS_FILE = DATA_DIR / "rankings_name_mappings.json"
# File to log unmatched players
UNMATCHED_PLAYERS_FILE = DATA_DIR / "unmatched_players.json"


def load_rankings_mappings() -> Dict[str, str]:
    """Load mappings from DB names to rankings names."""
    if RANKINGS_MAPPINGS_FILE.exists():
        try:
            with open(RANKINGS_MAPPINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('mappings', {})
        except:
            pass
    return {}


def save_rankings_mappings(mappings: Dict[str, str]):
    """Save rankings name mappings."""
    data = {
        "_comment": "Maps database player names to Tennis Explorer rankings names",
        "_instructions": "Add entries like: 'DB Name': 'Rankings Name'",
        "mappings": mappings
    }
    with open(RANKINGS_MAPPINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_rankings_mapping(db_name: str, rankings_name: str):
    """Add a single mapping from DB name to rankings name."""
    mappings = load_rankings_mappings()
    mappings[db_name] = rankings_name
    save_rankings_mappings(mappings)


def save_unmatched_players(players: List[Dict]):
    """Save list of unmatched players for review."""
    data = {
        "_comment": "Players that couldn't be matched to rankings. Add mappings in rankings_name_mappings.json",
        "_updated": datetime.now().isoformat(),
        "unmatched": players
    }
    with open(UNMATCHED_PLAYERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_unmatched_players() -> List[Dict]:
    """Get list of unmatched players."""
    if UNMATCHED_PLAYERS_FILE.exists():
        try:
            with open(UNMATCHED_PLAYERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('unmatched', [])
        except:
            pass
    return []


def search_rankings_for_player(search_term: str) -> List[Dict]:
    """Search the downloaded rankings for a player name."""
    if not RANKINGS_FILE.exists():
        return []

    results = []
    search_lower = search_term.lower()

    try:
        with open(RANKINGS_FILE, 'r', encoding='utf-8') as f:
            rankings = json.load(f)

        for tour in ['atp', 'wta']:
            for r in rankings.get(tour, []):
                if search_lower in r['name'].lower():
                    results.append({
                        'rank': r['rank'],
                        'name': r['name'],
                        'tour': tour.upper(),
                        'points': r.get('points')
                    })

    except Exception as e:
        print(f"Error searching rankings: {e}")

    return sorted(results, key=lambda x: x['rank'])


class RankingsDownloader:
    """Download and manage tennis rankings from Tennis Explorer."""

    BASE_URL = "https://www.tennisexplorer.com"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

    def fetch_rankings_page(self, tour: str = "atp", page: int = 1) -> List[Dict]:
        """
        Fetch a single page of rankings from Tennis Explorer.

        Args:
            tour: "atp" for men or "wta" for women
            page: Page number (1-based, each page has ~100 players)

        Returns:
            List of dicts with: rank, name, country, points
        """
        rankings = []

        if tour.lower() == "atp":
            url = f"{self.BASE_URL}/ranking/atp-men/"
        else:
            url = f"{self.BASE_URL}/ranking/wta-women/"

        # Add page parameter if not first page
        if page > 1:
            url += f"?page={page}"

        try:
            response = self.session.get(url, timeout=30)
            if response.status_code != 200:
                print(f"Failed to fetch {tour} rankings page {page}: {response.status_code}")
                return rankings

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find ranking table rows
            # Tennis Explorer uses table rows with player data
            tables = soup.select('table')

            for table in tables:
                rows = table.select('tr')

                for row in rows:
                    cells = row.select('td')
                    if len(cells) < 4:
                        continue

                    try:
                        # Extract rank from first cell
                        rank_text = cells[0].get_text(strip=True)
                        rank_match = re.match(r'^(\d+)', rank_text)
                        if not rank_match:
                            continue
                        rank = int(rank_match.group(1))

                        # Extract player name (usually in a link)
                        player_link = row.select_one('a[href*="/player/"]')
                        if not player_link:
                            continue

                        name = player_link.get_text(strip=True)
                        # Tennis Explorer stores names as "Lastname Firstname"
                        # Convert to "Firstname Lastname" for consistency
                        name_parts = name.split()
                        if len(name_parts) >= 2:
                            # Last word is usually first name
                            name = f"{name_parts[-1]} {' '.join(name_parts[:-1])}"

                        # Extract country
                        country = ""
                        country_link = row.select_one('a[href*="/ranking/"][href*="?country="]')
                        if country_link:
                            country = country_link.get_text(strip=True)

                        # Extract points (usually last numeric cell)
                        points = None
                        for cell in reversed(cells):
                            points_text = cell.get_text(strip=True).replace(',', '')
                            if points_text.isdigit():
                                points = int(points_text)
                                break

                        rankings.append({
                            'rank': rank,
                            'name': name,
                            'country': country,
                            'points': points,
                            'tour': tour.upper()
                        })

                    except Exception as e:
                        continue

            return rankings

        except Exception as e:
            print(f"Error fetching {tour} rankings page {page}: {e}")
            return rankings

    def fetch_all_rankings(self, tour: str = "atp", max_rank: int = 2000,
                          progress_callback: Callable = None) -> List[Dict]:
        """
        Fetch all rankings up to max_rank.

        Args:
            tour: "atp" or "wta"
            max_rank: Maximum rank to fetch (default 2000)
            progress_callback: Optional callback for progress updates

        Returns:
            List of all ranking entries
        """
        all_rankings = []
        page = 1
        players_per_page = 100  # Approximate

        while True:
            if progress_callback:
                progress_callback(f"Fetching {tour.upper()} rankings page {page}...")

            page_rankings = self.fetch_rankings_page(tour, page)

            if not page_rankings:
                break

            all_rankings.extend(page_rankings)

            # Check if we've reached our target
            max_rank_on_page = max(r['rank'] for r in page_rankings)
            if max_rank_on_page >= max_rank:
                # Filter to only include up to max_rank
                all_rankings = [r for r in all_rankings if r['rank'] <= max_rank]
                break

            page += 1
            time.sleep(0.5)  # Be respectful to the server

            # Safety limit
            if page > 30:
                break

        if progress_callback:
            progress_callback(f"Fetched {len(all_rankings)} {tour.upper()} rankings")

        return all_rankings

    def download_all_rankings(self, max_rank: int = 2000,
                             progress_callback: Callable = None) -> Dict:
        """
        Download both ATP and WTA rankings.

        Args:
            max_rank: Maximum rank to fetch for each tour
            progress_callback: Optional callback for progress updates

        Returns:
            Dict with 'atp' and 'wta' ranking lists
        """
        result = {
            'atp': [],
            'wta': [],
            'downloaded_at': datetime.now().isoformat(),
            'max_rank': max_rank
        }

        # Fetch ATP
        if progress_callback:
            progress_callback("Downloading ATP rankings...")
        result['atp'] = self.fetch_all_rankings('atp', max_rank, progress_callback)

        time.sleep(1)

        # Fetch WTA
        if progress_callback:
            progress_callback("Downloading WTA rankings...")
        result['wta'] = self.fetch_all_rankings('wta', max_rank, progress_callback)

        return result

    def save_rankings_to_file(self, rankings: Dict) -> str:
        """Save rankings to local JSON file."""
        with open(RANKINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(rankings, f, indent=2, ensure_ascii=False)
        return str(RANKINGS_FILE)

    def load_rankings_from_file(self) -> Optional[Dict]:
        """Load rankings from local JSON file."""
        if not RANKINGS_FILE.exists():
            return None
        try:
            with open(RANKINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading rankings file: {e}")
            return None

    def get_rankings_age(self) -> Optional[str]:
        """Get the age of the cached rankings."""
        rankings = self.load_rankings_from_file()
        if rankings and 'downloaded_at' in rankings:
            return rankings['downloaded_at']
        return None

    def update_database_rankings(self, rankings: Dict = None,
                                progress_callback: Callable = None,
                                set_default_for_unranked: bool = True) -> Dict:
        """
        Update player rankings in the database from downloaded rankings.

        Args:
            rankings: Rankings dict (loads from file if None)
            progress_callback: Optional callback for progress updates
            set_default_for_unranked: If True, set players not in rankings to 1500

        Returns:
            Dict with update statistics
        """
        if rankings is None:
            rankings = self.load_rankings_from_file()
            if rankings is None:
                return {'success': False, 'message': 'No rankings file found'}

        stats = {
            'success': True,
            'atp_updated': 0,
            'wta_updated': 0,
            'set_to_default': 0,
            'not_found': 0,
            'unmatched': [],
            'message': ''
        }

        # Default rank for players not in top 1500
        DEFAULT_RANK = 1500

        # Load custom name mappings (DB name -> Rankings name)
        custom_mappings = load_rankings_mappings()

        # Build a lookup of all rankings by name variations
        rankings_lookup = {}

        def add_name_variations(name: str, rank: int, points: int, tour: str):
            """Add various name formats to lookup."""
            name_lower = name.lower().strip()
            rankings_lookup[name_lower] = (rank, points, tour)

            # Also add "LastName FirstName" format
            parts = name.split()
            if len(parts) >= 2:
                reversed_name = f"{parts[-1]} {' '.join(parts[:-1])}".lower()
                rankings_lookup[reversed_name] = (rank, points, tour)

                # Last name + first initial for more reliable matching
                last_name = parts[-1].lower()
                first_initial = parts[0][0].lower() if parts[0] else ''
                key = f"_last_{last_name}_{first_initial}"
                if key not in rankings_lookup:
                    rankings_lookup[key] = (rank, points, tour, name)

            # Add truncated versions (for DB names that got cut off)
            # e.g., "Matheus Pucinelli De Almeida" -> also match "Matheus Pucinelli De Al"
            if len(name_lower) > 15:
                for length in [15, 18, 20, 22, 25]:
                    if len(name_lower) > length:
                        truncated = name_lower[:length]
                        if truncated not in rankings_lookup:
                            rankings_lookup[truncated] = (rank, points, tour)

        # Build lookup from ATP rankings
        for r in rankings.get('atp', []):
            add_name_variations(r['name'], r['rank'], r.get('points'), 'ATP')

        # Build lookup from WTA rankings
        for r in rankings.get('wta', []):
            add_name_variations(r['name'], r['rank'], r.get('points'), 'WTA')

        if progress_callback:
            progress_callback(f"Built lookup with {len(rankings_lookup)} name variations")

        # Get all players from database
        all_players = db.get_all_players()

        if progress_callback:
            progress_callback(f"Updating {len(all_players)} players...")

        updated_count = 0
        unmatched_players = []

        for i, player in enumerate(all_players):
            player_name_orig = player.get('name', '').strip()
            player_name = player_name_orig.lower()
            player_id = player['id']

            found = False

            # Try custom mapping first (DB name -> Rankings name)
            if player_name_orig in custom_mappings:
                mapped_name = custom_mappings[player_name_orig].lower()
                if mapped_name in rankings_lookup:
                    rank, points, tour = rankings_lookup[mapped_name][:3]
                    db.update_player_ranking(player_id, rank, points)
                    if tour == 'ATP':
                        stats['atp_updated'] += 1
                    else:
                        stats['wta_updated'] += 1
                    updated_count += 1
                    found = True

            # Try exact match
            if not found and player_name in rankings_lookup:
                rank, points, tour = rankings_lookup[player_name][:3]
                db.update_player_ranking(player_id, rank, points)
                if tour == 'ATP':
                    stats['atp_updated'] += 1
                else:
                    stats['wta_updated'] += 1
                updated_count += 1
                found = True

            # Try prefix match (DB name might be truncated)
            # e.g., "matheus pucinelli de al" should match "matheus pucinelli de almeida"
            if not found and len(player_name) >= 15:
                for rankings_name, value in rankings_lookup.items():
                    if not rankings_name.startswith('_'):  # Skip special keys
                        if rankings_name.startswith(player_name):
                            rank, points, tour = value[:3]
                            db.update_player_ranking(player_id, rank, points)
                            if tour == 'ATP':
                                stats['atp_updated'] += 1
                            else:
                                stats['wta_updated'] += 1
                            updated_count += 1
                            found = True
                            break

            # Try last name + first initial match for players not found
            if not found:
                parts = player_name.split()
                if len(parts) >= 2:
                    last_name = parts[-1].lower()
                    first_initial = parts[0][0].lower() if parts[0] else ''
                    last_key = f"_last_{last_name}_{first_initial}"
                    if last_key in rankings_lookup:
                        entry = rankings_lookup[last_key]
                        rank, points, tour = entry[:3]
                        db.update_player_ranking(player_id, rank, points)
                        if tour == 'ATP':
                            stats['atp_updated'] += 1
                        else:
                            stats['wta_updated'] += 1
                        updated_count += 1
                        found = True

            # Set default rank for players not found in rankings
            if not found:
                if set_default_for_unranked:
                    # Set default rank for any player not in the rankings list
                    # This ensures players ranked beyond 1500 get a reasonable default
                    db.update_player_ranking(player_id, DEFAULT_RANK)
                    stats['set_to_default'] += 1
                    updated_count += 1

                    # Track unmatched players (only those with reasonable names)
                    if len(player_name_orig) > 3 and ' ' in player_name_orig:
                        unmatched_players.append({
                            'id': player_id,
                            'name': player_name_orig,
                            'current_rank': DEFAULT_RANK
                        })
                else:
                    stats['not_found'] += 1

            # Progress update every 100 players
            if i % 100 == 0 and progress_callback:
                progress_callback(f"Updated {updated_count} players...")

        # Save unmatched players for review (limit to 500 most relevant)
        # Sort by name length (shorter names more likely to be real players)
        unmatched_players.sort(key=lambda x: len(x['name']))
        stats['unmatched'] = unmatched_players[:500]
        save_unmatched_players(stats['unmatched'])

        stats['message'] = (
            f"Updated {stats['atp_updated']} ATP, {stats['wta_updated']} WTA rankings. "
            f"{stats['set_to_default']} players set to default rank {DEFAULT_RANK}. "
            f"{len(stats['unmatched'])} unmatched players logged."
        )

        if progress_callback:
            progress_callback(stats['message'])

        return stats


def download_and_update_rankings(max_rank: int = 2000,
                                progress_callback: Callable = None) -> Dict:
    """
    Convenience function to download rankings and update database.

    Args:
        max_rank: Maximum rank to download
        progress_callback: Optional progress callback

    Returns:
        Dict with download and update statistics
    """
    downloader = RankingsDownloader()

    # Download rankings
    if progress_callback:
        progress_callback("Starting rankings download...")

    rankings = downloader.download_all_rankings(max_rank, progress_callback)

    # Save to file
    if progress_callback:
        progress_callback("Saving rankings to file...")
    downloader.save_rankings_to_file(rankings)

    # Update database
    if progress_callback:
        progress_callback("Updating database...")
    stats = downloader.update_database_rankings(rankings, progress_callback)

    stats['atp_total'] = len(rankings.get('atp', []))
    stats['wta_total'] = len(rankings.get('wta', []))

    return stats


def update_unranked_players_from_profiles(progress_callback: Callable = None) -> Dict:
    """
    Update rankings for players who are still at rank 1500 (below top 1500).

    This fetches rankings from individual player profiles for players
    in upcoming matches who weren't found in the top 1500 rankings list.

    Returns:
        Dict with update statistics
    """
    from tennis_explorer_scraper import TennisExplorerScraper

    stats = {
        'success': True,
        'updated': 0,
        'failed': 0,
        'already_ranked': 0,
        'updates': [],
        'message': ''
    }

    # Get all upcoming matches
    upcoming = db.get_upcoming_matches()

    if not upcoming:
        stats['message'] = "No upcoming matches found"
        return stats

    # Collect players who need updating (rank 1500 = default/unranked)
    players_to_update = {}
    seen_names = set()  # Track names to avoid duplicate player entries
    doubles_skipped = 0
    for match in upcoming:
        for pid_key, name_key in [('player1_id', 'player1_name'), ('player2_id', 'player2_name')]:
            pid = match.get(pid_key)
            pname = match.get(name_key)
            if pid and pname and pid not in players_to_update:
                # Skip doubles matches (names contain " / ")
                if ' / ' in pname:
                    doubles_skipped += 1
                    continue
                # Skip if we've already seen a similar name (duplicate players in DB)
                name_key_lower = pname.lower().strip()
                # Also check if this is a prefix of an existing name or vice versa
                is_duplicate = False
                for seen in seen_names:
                    if name_key_lower.startswith(seen) or seen.startswith(name_key_lower):
                        is_duplicate = True
                        break
                if is_duplicate:
                    continue
                # Check current ranking
                player = db.get_player(pid)
                if player:
                    current_rank = player.get('current_ranking')
                    if current_rank == 1500 or current_rank is None:
                        players_to_update[pid] = pname
                        seen_names.add(name_key_lower)
                    else:
                        stats['already_ranked'] += 1

    if not players_to_update:
        stats['message'] = f"All {stats['already_ranked']} players already have accurate rankings"
        return stats

    total = len(players_to_update)
    if progress_callback:
        progress_callback(f"Updating {total} players ranked below 1500...")

    scraper = TennisExplorerScraper()

    for i, (player_id, player_name) in enumerate(players_to_update.items()):
        if progress_callback:
            progress_callback(f"[{i+1}/{total}] {player_name}...")

        try:
            slug = scraper.search_player(player_name)
            if not slug:
                stats['failed'] += 1
                continue

            profile = scraper.fetch_player_profile(slug)
            if not profile or not profile.get('ranking'):
                stats['failed'] += 1
                continue

            ranking = profile['ranking']
            db.update_player_ranking(player_id, ranking)

            stats['updated'] += 1
            stats['updates'].append({
                'player_id': player_id,
                'player_name': player_name,
                'ranking': ranking
            })

            if progress_callback:
                progress_callback(f"  → {player_name}: Rank {ranking}")

            time.sleep(0.3)

        except Exception as e:
            stats['failed'] += 1

    stats['doubles_skipped'] = doubles_skipped
    stats['message'] = f"Updated {stats['updated']} players, {stats['already_ranked']} already ranked, {stats['failed']} failed, {doubles_skipped} doubles skipped"
    return stats


def update_rankings_for_upcoming_matches(progress_callback: Callable = None) -> Dict:
    """
    Update rankings for all players in upcoming matches.

    This fetches rankings from individual player profiles, which works
    for players ranked beyond 1500 (not in the rankings list).

    Returns:
        Dict with update statistics
    """
    from tennis_explorer_scraper import TennisExplorerScraper

    stats = {
        'success': True,
        'updated': 0,
        'failed': 0,
        'skipped': 0,
        'updates': [],
        'message': ''
    }

    # Get all upcoming matches
    upcoming = db.get_upcoming_matches()

    if not upcoming:
        stats['message'] = "No upcoming matches found"
        return stats

    # Collect unique players
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
        progress_callback(f"Updating rankings for {total} players in upcoming matches...")

    scraper = TennisExplorerScraper()

    for i, (player_id, player_name) in enumerate(players_to_update.items()):
        if progress_callback:
            progress_callback(f"[{i+1}/{total}] {player_name}...")

        try:
            # Search for player
            slug = scraper.search_player(player_name)
            if not slug:
                stats['failed'] += 1
                continue

            # Get profile
            profile = scraper.fetch_player_profile(slug)
            if not profile or not profile.get('ranking'):
                stats['failed'] += 1
                continue

            ranking = profile['ranking']

            # Update database
            db.update_player_ranking(player_id, ranking)

            stats['updated'] += 1
            stats['updates'].append({
                'player_id': player_id,
                'player_name': player_name,
                'ranking': ranking
            })

            if progress_callback:
                progress_callback(f"  → {player_name}: Rank {ranking}")

            # Be respectful to server
            time.sleep(0.3)

        except Exception as e:
            stats['failed'] += 1
            if progress_callback:
                progress_callback(f"  → Error: {e}")

    stats['message'] = f"Updated {stats['updated']} players, {stats['failed']} failed"
    return stats


if __name__ == "__main__":
    # Test the downloader
    def print_progress(msg):
        print(msg)

    print("Testing Rankings Downloader...")
    stats = download_and_update_rankings(max_rank=500, progress_callback=print_progress)
    print(f"\nResults: {stats}")
