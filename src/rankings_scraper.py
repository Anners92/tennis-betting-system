"""
Rankings Scraper - Fetch current ATP and WTA rankings
"""

import requests
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Optional
from database import db


class RankingsScraper:
    """Scrape current rankings from ATP and WTA websites."""

    ATP_RANKINGS_URL = "https://www.atptour.com/en/rankings/singles"
    WTA_RANKINGS_URL = "https://www.wtatennis.com/rankings/singles"

    # Alternative: Tennis Explorer rankings pages (more reliable)
    TE_ATP_URL = "https://www.tennisexplorer.com/ranking/atp-men/"
    TE_WTA_URL = "https://www.tennisexplorer.com/ranking/wta-women/"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def scrape_atp_rankings(self, max_rank: int = 500) -> List[Dict]:
        """Scrape ATP rankings from Tennis Explorer."""
        rankings = []
        page = 1

        print("Scraping ATP rankings...")

        while len(rankings) < max_rank:
            url = f"{self.TE_ATP_URL}?page={page}"
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                # Find ranking table (the one with "Rank" header)
                tables = soup.find_all('table', class_='result')
                table = None
                for t in tables:
                    header = t.find('tr')
                    if header and 'Rank' in header.get_text():
                        table = t
                        break

                if not table:
                    break

                rows = table.find_all('tr')[1:]  # Skip header
                if not rows:
                    break

                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 5:
                        try:
                            # Cell 0: Rank (e.g., "1.")
                            # Cell 1: Move indicator
                            # Cell 2: Player name
                            # Cell 3: Country
                            # Cell 4: Points
                            rank_text = cells[0].get_text(strip=True)
                            rank = int(re.sub(r'[^\d]', '', rank_text))

                            name_cell = cells[2]
                            name_link = name_cell.find('a')
                            if name_link:
                                name = name_link.get_text(strip=True)
                                slug = name_link.get('href', '').split('/')[-2] if name_link.get('href') else None
                            else:
                                name = name_cell.get_text(strip=True)
                                slug = None

                            # Keep name as-is - fuzzy matching will handle different formats

                            country_cell = cells[3]
                            country = country_cell.get_text(strip=True) if country_cell else ''

                            points_cell = cells[4]
                            points_text = points_cell.get_text(strip=True) if points_cell else '0'
                            points = int(re.sub(r'[^\d]', '', points_text)) if points_text else 0

                            if rank <= max_rank and name:
                                rankings.append({
                                    'rank': rank,
                                    'name': name,
                                    'country': country,
                                    'points': points,
                                    'tour': 'ATP',
                                    'slug': slug
                                })

                        except (ValueError, AttributeError) as e:
                            continue

                page += 1
                if page > 10:  # Safety limit
                    break

            except Exception as e:
                print(f"Error scraping ATP page {page}: {e}")
                break

        print(f"Found {len(rankings)} ATP rankings")
        return rankings

    def scrape_wta_rankings(self, max_rank: int = 500) -> List[Dict]:
        """Scrape WTA rankings from Tennis Explorer."""
        rankings = []
        page = 1

        print("Scraping WTA rankings...")

        while len(rankings) < max_rank:
            url = f"{self.TE_WTA_URL}?page={page}"
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                # Find ranking table (the one with "Rank" header)
                tables = soup.find_all('table', class_='result')
                table = None
                for t in tables:
                    header = t.find('tr')
                    if header and 'Rank' in header.get_text():
                        table = t
                        break

                if not table:
                    break

                rows = table.find_all('tr')[1:]  # Skip header
                if not rows:
                    break

                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 5:
                        try:
                            # Cell 0: Rank (e.g., "1.")
                            # Cell 1: Move indicator
                            # Cell 2: Player name
                            # Cell 3: Country
                            # Cell 4: Points
                            rank_text = cells[0].get_text(strip=True)
                            rank = int(re.sub(r'[^\d]', '', rank_text))

                            name_cell = cells[2]
                            name_link = name_cell.find('a')
                            if name_link:
                                name = name_link.get_text(strip=True)
                                slug = name_link.get('href', '').split('/')[-2] if name_link.get('href') else None
                            else:
                                name = name_cell.get_text(strip=True)
                                slug = None

                            # Keep name as-is - fuzzy matching will handle different formats

                            country_cell = cells[3]
                            country = country_cell.get_text(strip=True) if country_cell else ''

                            points_cell = cells[4]
                            points_text = points_cell.get_text(strip=True) if points_cell else '0'
                            points = int(re.sub(r'[^\d]', '', points_text)) if points_text else 0

                            if rank <= max_rank and name:
                                rankings.append({
                                    'rank': rank,
                                    'name': name,
                                    'country': country,
                                    'points': points,
                                    'tour': 'WTA',
                                    'slug': slug
                                })

                        except (ValueError, AttributeError) as e:
                            continue

                page += 1
                if page > 10:  # Safety limit
                    break

            except Exception as e:
                print(f"Error scraping WTA page {page}: {e}")
                break

        print(f"Found {len(rankings)} WTA rankings")
        return rankings

    def update_database(self, rankings: List[Dict]) -> int:
        """Update player rankings in the database."""
        import sqlite3
        from fuzzywuzzy import fuzz

        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()

        updated = 0
        not_found = []

        # Get all players from database
        cursor.execute("SELECT id, name, slug, tour FROM players WHERE name NOT LIKE '%/%'")
        db_players = cursor.fetchall()

        for rank_entry in rankings:
            rank = rank_entry['rank']
            name = rank_entry['name']
            tour = rank_entry['tour']
            slug = rank_entry.get('slug')
            country = rank_entry.get('country', '')
            points = rank_entry.get('points', 0)

            # Try to match by slug first
            matched_id = None

            if slug:
                for pid, pname, pslug, ptour in db_players:
                    if pslug and slug.lower() in pslug.lower():
                        matched_id = pid
                        break

            # If no slug match, try fuzzy name match
            if not matched_id:
                best_match = None
                best_score = 0

                for pid, pname, pslug, ptour in db_players:
                    # Only match within same tour
                    if ptour != tour:
                        continue

                    score = fuzz.ratio(name.lower(), pname.lower())
                    if score > best_score and score >= 80:
                        best_score = score
                        best_match = pid

                if best_match:
                    matched_id = best_match

            # Update the player
            if matched_id:
                cursor.execute("""
                    UPDATE players
                    SET current_ranking = ?, ranking = ?, country = COALESCE(NULLIF(country, ''), ?)
                    WHERE id = ?
                """, (rank, rank, country, matched_id))
                updated += 1
            else:
                not_found.append(f"{name} (#{rank})")

        conn.commit()
        conn.close()

        if not_found and len(not_found) <= 20:
            print(f"Could not match: {', '.join(not_found[:20])}")
        elif not_found:
            print(f"Could not match {len(not_found)} players")

        return updated

    def scrape_all(self, max_rank: int = 200) -> Dict:
        """Scrape both ATP and WTA rankings and update database."""
        results = {
            'atp_scraped': 0,
            'wta_scraped': 0,
            'atp_updated': 0,
            'wta_updated': 0
        }

        # Scrape ATP
        atp_rankings = self.scrape_atp_rankings(max_rank)
        results['atp_scraped'] = len(atp_rankings)
        if atp_rankings:
            results['atp_updated'] = self.update_database(atp_rankings)

        # Scrape WTA
        wta_rankings = self.scrape_wta_rankings(max_rank)
        results['wta_scraped'] = len(wta_rankings)
        if wta_rankings:
            results['wta_updated'] = self.update_database(wta_rankings)

        print(f"\nRankings update complete:")
        print(f"  ATP: {results['atp_updated']}/{results['atp_scraped']} players updated")
        print(f"  WTA: {results['wta_updated']}/{results['wta_scraped']} players updated")

        return results


if __name__ == "__main__":
    scraper = RankingsScraper()
    scraper.scrape_all(max_rank=200)
