"""
Tennis Betting System - Betfair Tennis Scraper
Fetch tennis matches and odds from Betfair Exchange
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import threading
import re

from config import UI_COLORS, SURFACES
from database import db, TennisDatabase


class BetfairTennisScraper:
    """Scrape tennis matches and odds from Betfair."""

    # Betfair Exchange API endpoints (public)
    BETFAIR_EXCHANGE_URL = "https://www.betfair.com/exchange/plus/"

    # Alternative: Use the Betfair API navigation data
    NAVIGATION_URL = "https://www.betfair.com/www/sports/navigation/facet/v1/search?_ak=nzIFcwyWhrlwYMrh&alt=json"

    # Direct exchange data endpoint
    EXCHANGE_API = "https://ero.betfair.com/www/sports/exchange/readonly/v1/bymarket"

    # Tennis event type ID on Betfair
    TENNIS_EVENT_TYPE_ID = "2"

    def __init__(self, database: TennisDatabase = None):
        self.db = database or db
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

    def _make_request(self, url: str, headers: Dict = None) -> Optional[Dict]:
        """Make HTTP request and return JSON response."""
        if headers is None:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Accept-Language': 'en-GB,en;q=0.9',
            }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30, context=self.ssl_context) as response:
                data = response.read().decode('utf-8')
                return json.loads(data)
        except Exception as e:
            print(f"Request error: {e}")
            return None

    def fetch_tennis_events(self) -> List[Dict]:
        """Fetch current tennis events/tournaments from Betfair."""
        # Betfair navigation endpoint for tennis
        url = f"https://www.betfair.com/www/sports/navigation/facet/v1/search?_ak=nzIFcwyWhrlwYMrh&alt=json&currencyCode=GBP&exchangeLocale=en_GB&locale=en_GB&marketTypes=MATCH_ODDS&eventTypeIds={self.TENNIS_EVENT_TYPE_ID}&facets=eventType,competition,event"

        data = self._make_request(url)
        if not data:
            return []

        events = []
        try:
            attachments = data.get('attachments', {})
            competitions = attachments.get('competitions', {})

            for comp_id, comp_data in competitions.items():
                events.append({
                    'id': comp_id,
                    'name': comp_data.get('name', 'Unknown'),
                    'event_type': 'tennis',
                })
        except Exception as e:
            print(f"Error parsing events: {e}")

        return events

    def fetch_tennis_matches(self, competition_id: str = None) -> List[Dict]:
        """Fetch tennis matches with odds from Betfair."""
        matches = []

        # Try multiple approaches to get match data

        # Approach 1: Direct exchange listing
        url = f"https://www.betfair.com/www/sports/exchange/readonly/v1/bymarket?_ak=nzIFcwyWhrlwYMrh&alt=json&currencyCode=GBP&locale=en_GB&marketProjections=EVENT,COMPETITION,MARKET_DESCRIPTION,RUNNER_DESCRIPTION&marketTypes=MATCH_ODDS&eventTypeIds={self.TENNIS_EVENT_TYPE_ID}"

        if competition_id:
            url += f"&competitionIds={competition_id}"

        data = self._make_request(url)

        if data:
            matches = self._parse_exchange_data(data)

        # If no matches found, try alternative endpoint
        if not matches:
            matches = self._fetch_from_sportsbook_api()

        return matches

    def _parse_exchange_data(self, data: Dict) -> List[Dict]:
        """Parse Betfair exchange API response."""
        matches = []

        try:
            events = data.get('eventTypes', [])
            for event_type in events:
                event_nodes = event_type.get('eventNodes', [])
                for event_node in event_nodes:
                    event = event_node.get('event', {})
                    market_nodes = event_node.get('marketNodes', [])

                    for market_node in market_nodes:
                        market = market_node.get('description', {})
                        runners = market_node.get('runners', [])
                        state = market_node.get('state', {})

                        if len(runners) >= 2 and market.get('marketType') == 'MATCH_ODDS':
                            # Extract player names and odds
                            p1_data = runners[0]
                            p2_data = runners[1]

                            p1_name = p1_data.get('description', {}).get('runnerName', 'Player 1')
                            p2_name = p2_data.get('description', {}).get('runnerName', 'Player 2')

                            # Get best back odds
                            p1_exchange = p1_data.get('exchange', {})
                            p2_exchange = p2_data.get('exchange', {})

                            p1_backs = p1_exchange.get('availableToBack', [])
                            p2_backs = p2_exchange.get('availableToBack', [])

                            p1_odds = p1_backs[0].get('price', 0) if p1_backs else None
                            p2_odds = p2_backs[0].get('price', 0) if p2_backs else None

                            # Determine surface from competition name
                            competition = event_node.get('competitionNode', {}).get('competition', {})
                            comp_name = competition.get('name', '')
                            event_date = event.get('openDate', '')[:10] if event.get('openDate') else None
                            surface = self._guess_surface(comp_name, event.get('name', ''), event_date)

                            match_data = {
                                'tournament': comp_name,
                                'event_name': event.get('name', ''),
                                'market_id': market_node.get('marketId'),
                                'date': event.get('openDate', '')[:10] if event.get('openDate') else datetime.now().strftime('%Y-%m-%d'),
                                'player1_name': p1_name,
                                'player2_name': p2_name,
                                'player1_odds': p1_odds,
                                'player2_odds': p2_odds,
                                'surface': surface,
                                'in_play': state.get('inplay', False),
                                'total_matched': state.get('totalMatched', 0),
                            }

                            # Only include pre-match (not in-play)
                            if not match_data['in_play']:
                                matches.append(match_data)

        except Exception as e:
            print(f"Error parsing exchange data: {e}")

        return matches

    def _fetch_from_sportsbook_api(self) -> List[Dict]:
        """Alternative: Fetch from sportsbook-style API."""
        matches = []

        # Try the listing endpoint
        url = "https://www.betfair.com/www/sports/navigation/facet/v1/search?_ak=nzIFcwyWhrlwYMrh&alt=json&currencyCode=GBP&exchangeLocale=en_GB&locale=en_GB&marketTypes=MATCH_ODDS&eventTypeIds=2&facets=eventType,competition,event,market"

        data = self._make_request(url)
        if not data:
            return matches

        try:
            attachments = data.get('attachments', {})
            events = attachments.get('events', {})
            markets = attachments.get('markets', {})
            competitions = attachments.get('competitions', {})

            for market_id, market_data in markets.items():
                if market_data.get('marketType') != 'MATCH_ODDS':
                    continue

                event_id = market_data.get('eventId')
                event = events.get(str(event_id), {})

                comp_id = event.get('competitionId')
                competition = competitions.get(str(comp_id), {})

                runners = market_data.get('runners', [])
                if len(runners) < 2:
                    continue

                # Parse runners
                p1_name = runners[0].get('runnerName', 'Player 1')
                p2_name = runners[1].get('runnerName', 'Player 2')

                comp_name = competition.get('name', '')
                event_date = event.get('openDate', '')[:10] if event.get('openDate') else None
                surface = self._guess_surface(comp_name, event.get('name', ''), event_date)

                match_data = {
                    'tournament': comp_name,
                    'event_name': event.get('name', ''),
                    'market_id': market_id,
                    'date': event_date or datetime.now().strftime('%Y-%m-%d'),
                    'player1_name': p1_name,
                    'player2_name': p2_name,
                    'player1_odds': None,  # Need separate call for odds
                    'player2_odds': None,
                    'surface': surface,
                    'in_play': market_data.get('inPlay', False),
                }

                if not match_data['in_play']:
                    matches.append(match_data)

        except Exception as e:
            print(f"Error parsing sportsbook data: {e}")

        return matches

    def _guess_surface(self, competition_name: str, event_name: str = '', date_str: str = None) -> str:
        """Guess the surface from tournament name using centralized detection."""
        from config import get_tournament_surface
        # Combine competition and event name for better matching
        full_name = f"{competition_name} {event_name}".strip()
        return get_tournament_surface(full_name, date_str)

    def fetch_market_odds(self, market_id: str) -> Dict:
        """Fetch current odds for a specific market."""
        url = f"https://ero.betfair.com/www/sports/exchange/readonly/v1/bymarket?_ak=nzIFcwyWhrlwYMrh&alt=json&currencyCode=GBP&locale=en_GB&marketIds={market_id}&marketProjections=RUNNER_DESCRIPTION&priceProjections=BEST_OFFERS"

        data = self._make_request(url)
        if not data:
            return {}

        try:
            event_types = data.get('eventTypes', [])
            for et in event_types:
                for en in et.get('eventNodes', []):
                    for mn in en.get('marketNodes', []):
                        if mn.get('marketId') == market_id:
                            runners = mn.get('runners', [])
                            if len(runners) >= 2:
                                p1 = runners[0].get('exchange', {})
                                p2 = runners[1].get('exchange', {})

                                p1_backs = p1.get('availableToBack', [])
                                p2_backs = p2.get('availableToBack', [])

                                return {
                                    'p1_odds': p1_backs[0].get('price') if p1_backs else None,
                                    'p2_odds': p2_backs[0].get('price') if p2_backs else None,
                                    'p1_liquidity': p1_backs[0].get('size') if p1_backs else 0,
                                    'p2_liquidity': p2_backs[0].get('size') if p2_backs else 0,
                                }
        except Exception as e:
            print(f"Error fetching odds: {e}")

        return {}

    def import_matches_to_db(self, matches: List[Dict]) -> int:
        """Import fetched matches into the database."""
        imported = 0

        for match in matches:
            # Try to find player IDs
            p1 = self.db.get_player_by_name(match['player1_name'])
            p2 = self.db.get_player_by_name(match['player2_name'])

            match_data = {
                'tournament': match.get('tournament', ''),
                'date': match.get('date'),
                'surface': match.get('surface', 'Hard'),
                'round': '',
                'player1_id': p1['id'] if p1 else None,
                'player2_id': p2['id'] if p2 else None,
                'player1_name': match['player1_name'],
                'player2_name': match['player2_name'],
                'player1_odds': match.get('player1_odds'),
                'player2_odds': match.get('player2_odds'),
            }

            try:
                self.db.add_upcoming_match(match_data)
                imported += 1
            except Exception as e:
                print(f"Error importing match: {e}")

        return imported


class BetfairTennisUI:
    """UI for Betfair Tennis Scraper."""

    # Colors matching main app
    BG_DARK = '#0d0d1a'
    BG_CARD = '#1a1a2e'
    BG_CARD_HOVER = '#252542'
    ACCENT_SUCCESS = '#22c55e'
    ACCENT_INFO = '#3b82f6'
    ACCENT_WARNING = '#f59e0b'
    ACCENT_DANGER = '#ef4444'
    TEXT_PRIMARY = '#f1f5f9'
    TEXT_SECONDARY = '#94a3b8'
    TEXT_MUTED = '#64748b'

    def __init__(self, parent: tk.Tk = None):
        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()

        self.root.title("Betfair Tennis - Live Matches")
        self.root.geometry("1100x700")
        self.root.configure(bg=self.BG_DARK)

        self.scraper = BetfairTennisScraper()
        self.matches = []

        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure("Dark.TFrame", background=self.BG_DARK)
        style.configure("Card.TFrame", background=self.BG_CARD)

        style.configure("Treeview",
                       background=self.BG_CARD,
                       foreground=self.TEXT_PRIMARY,
                       fieldbackground=self.BG_CARD,
                       font=("Segoe UI", 10))
        style.configure("Treeview.Heading",
                       background=self.BG_CARD_HOVER,
                       foreground=self.TEXT_PRIMARY,
                       font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[('selected', self.ACCENT_INFO)])

    def _build_ui(self):
        """Build the UI."""
        main_frame = tk.Frame(self.root, bg=self.BG_DARK, padx=25, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header = tk.Frame(main_frame, bg=self.BG_DARK)
        header.pack(fill=tk.X, pady=(0, 20))

        tk.Label(header, text="Betfair Tennis Matches",
                font=("Segoe UI", 20, "bold"), bg=self.BG_DARK,
                fg=self.TEXT_PRIMARY).pack(side=tk.LEFT)

        # Buttons
        btn_frame = tk.Frame(header, bg=self.BG_DARK)
        btn_frame.pack(side=tk.RIGHT)

        fetch_btn = tk.Button(
            btn_frame, text="Fetch Matches",
            font=("Segoe UI", 10, "bold"), fg="white", bg=self.ACCENT_INFO,
            relief=tk.FLAT, cursor="hand2", padx=15, pady=8,
            command=self._fetch_matches
        )
        fetch_btn.pack(side=tk.LEFT, padx=5)

        import_btn = tk.Button(
            btn_frame, text="Import Selected",
            font=("Segoe UI", 10, "bold"), fg="white", bg=self.ACCENT_SUCCESS,
            relief=tk.FLAT, cursor="hand2", padx=15, pady=8,
            command=self._import_selected
        )
        import_btn.pack(side=tk.LEFT, padx=5)

        import_all_btn = tk.Button(
            btn_frame, text="Import All",
            font=("Segoe UI", 10, "bold"), fg="white", bg=self.ACCENT_WARNING,
            relief=tk.FLAT, cursor="hand2", padx=15, pady=8,
            command=self._import_all
        )
        import_all_btn.pack(side=tk.LEFT, padx=5)

        # Status
        self.status_var = tk.StringVar(value="Click 'Fetch Matches' to load tennis matches from Betfair")
        status_label = tk.Label(main_frame, textvariable=self.status_var,
                               bg=self.BG_DARK, fg=self.TEXT_MUTED,
                               font=("Segoe UI", 9))
        status_label.pack(anchor='w', pady=(0, 10))

        # Matches table
        table_frame = tk.Frame(main_frame, bg=self.BG_CARD)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("tournament", "player1", "p1_odds", "player2", "p2_odds", "surface", "date", "liquidity")
        self.matches_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=20)

        self.matches_tree.heading("tournament", text="Tournament")
        self.matches_tree.heading("player1", text="Player 1")
        self.matches_tree.heading("p1_odds", text="P1 Odds")
        self.matches_tree.heading("player2", text="Player 2")
        self.matches_tree.heading("p2_odds", text="P2 Odds")
        self.matches_tree.heading("surface", text="Surface")
        self.matches_tree.heading("date", text="Date")
        self.matches_tree.heading("liquidity", text="Matched")

        self.matches_tree.column("tournament", width=180)
        self.matches_tree.column("player1", width=150)
        self.matches_tree.column("p1_odds", width=70)
        self.matches_tree.column("player2", width=150)
        self.matches_tree.column("p2_odds", width=70)
        self.matches_tree.column("surface", width=70)
        self.matches_tree.column("date", width=90)
        self.matches_tree.column("liquidity", width=80)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.matches_tree.yview)
        self.matches_tree.configure(yscrollcommand=scrollbar.set)

        self.matches_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        # Footer info
        footer = tk.Frame(main_frame, bg=self.BG_DARK)
        footer.pack(fill=tk.X, pady=(10, 0))

        tk.Label(footer, text="Data from Betfair Exchange  |  Pre-match odds only  |  Select rows to import specific matches",
                bg=self.BG_DARK, fg=self.TEXT_MUTED, font=("Segoe UI", 9)).pack(side=tk.LEFT)

    def _fetch_matches(self):
        """Fetch matches from Betfair."""
        self.status_var.set("Fetching matches from Betfair...")
        self.root.update()

        def fetch_thread():
            try:
                matches = self.scraper.fetch_tennis_matches()
                self.matches = matches
                self.root.after(0, lambda: self._display_matches(matches))
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Error: {e}"))

        thread = threading.Thread(target=fetch_thread, daemon=True)
        thread.start()

    def _display_matches(self, matches: List[Dict]):
        """Display fetched matches in the table."""
        self.matches_tree.delete(*self.matches_tree.get_children())

        if not matches:
            self.status_var.set("No matches found. Betfair may require login for full data.")
            return

        for i, match in enumerate(matches):
            p1_odds = f"{match['player1_odds']:.2f}" if match.get('player1_odds') else "-"
            p2_odds = f"{match['player2_odds']:.2f}" if match.get('player2_odds') else "-"
            liquidity = f"£{match.get('total_matched', 0):,.0f}" if match.get('total_matched') else "-"

            self.matches_tree.insert("", tk.END, iid=i, values=(
                match.get('tournament', ''),
                match.get('player1_name', ''),
                p1_odds,
                match.get('player2_name', ''),
                p2_odds,
                match.get('surface', 'Hard'),
                match.get('date', ''),
                liquidity,
            ))

        self.status_var.set(f"Found {len(matches)} matches. Select and click 'Import' to add to your system.")

    def _import_selected(self):
        """Import selected matches to database."""
        selection = self.matches_tree.selection()
        if not selection:
            messagebox.showinfo("Select Matches", "Please select matches to import.")
            return

        selected_matches = [self.matches[int(s)] for s in selection]
        imported = self.scraper.import_matches_to_db(selected_matches)

        self.status_var.set(f"Imported {imported} matches to the database.")
        messagebox.showinfo("Import Complete", f"Imported {imported} matches.\n\nYou can now analyze them in Bet Suggester.")

    def _import_all(self):
        """Import all fetched matches."""
        if not self.matches:
            messagebox.showinfo("No Matches", "Please fetch matches first.")
            return

        imported = self.scraper.import_matches_to_db(self.matches)
        self.status_var.set(f"Imported {imported} matches to the database.")
        messagebox.showinfo("Import Complete", f"Imported {imported} matches.\n\nYou can now analyze them in Bet Suggester.")

    def run(self):
        """Run the UI."""
        self.root.mainloop()


if __name__ == "__main__":
    app = BetfairTennisUI()
    app.run()
