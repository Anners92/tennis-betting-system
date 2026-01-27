"""
Tennis Explorer Import Dialog
Allows manual import of match data from specific Tennis Explorer player URLs.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import requests
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Optional
from datetime import datetime

from config import UI_COLORS
from database import db
from name_matcher import name_matcher


class PlayerAssignDialog:
    """Dialog for searching and selecting a player to assign."""

    def __init__(self, parent, current_name: str, current_id, callback):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Assign Player")
        self.dialog.geometry("500x450")
        self.dialog.configure(bg=UI_COLORS["bg_dark"])
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.callback = callback
        self.selected_player = None

        # Center dialog
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 500) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 450) // 2
        self.dialog.geometry(f"+{x}+{y}")

        self._create_widgets(current_name, current_id)

    def _create_widgets(self, current_name: str, current_id):
        """Create dialog widgets."""
        main_frame = tk.Frame(self.dialog, bg=UI_COLORS["bg_dark"], padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Current assignment
        current_frame = tk.Frame(main_frame, bg=UI_COLORS["bg_dark"])
        current_frame.pack(fill=tk.X, pady=(0, 15))

        tk.Label(
            current_frame,
            text="Scraped player name:",
            font=("Segoe UI", 10),
            fg=UI_COLORS["text_secondary"],
            bg=UI_COLORS["bg_dark"]
        ).pack(anchor=tk.W)

        tk.Label(
            current_frame,
            text=f"{current_name}",
            font=("Segoe UI", 11, "bold"),
            fg=UI_COLORS["text_primary"],
            bg=UI_COLORS["bg_dark"]
        ).pack(anchor=tk.W)

        if current_id:
            tk.Label(
                current_frame,
                text=f"Currently matched to ID: {current_id}",
                font=("Segoe UI", 9),
                fg=UI_COLORS["text_secondary"],
                bg=UI_COLORS["bg_dark"]
            ).pack(anchor=tk.W, pady=(5, 0))

        # Search
        tk.Label(
            main_frame,
            text="Search for correct player:",
            font=("Segoe UI", 10),
            fg=UI_COLORS["text_primary"],
            bg=UI_COLORS["bg_dark"]
        ).pack(anchor=tk.W, pady=(0, 5))

        search_frame = tk.Frame(main_frame, bg=UI_COLORS["bg_dark"])
        search_frame.pack(fill=tk.X, pady=(0, 10))

        # Default to last name for search
        default_search = current_name.split()[-1] if current_name else ""
        self.search_var = tk.StringVar(value=default_search)
        search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=("Segoe UI", 11),
            bg=UI_COLORS["bg_medium"],
            fg=UI_COLORS["text_primary"],
            insertbackground=UI_COLORS["text_primary"],
            width=35
        )
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        search_entry.bind('<Return>', lambda e: self._do_search())
        search_entry.bind('<KeyRelease>', lambda e: self._do_search())

        search_btn = tk.Button(
            search_frame,
            text="Search",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["accent"],
            relief=tk.FLAT,
            command=self._do_search,
            padx=15,
            pady=5
        )
        search_btn.pack(side=tk.LEFT, padx=(10, 0))

        # Results list
        tk.Label(
            main_frame,
            text="Select the correct player:",
            font=("Segoe UI", 10),
            fg=UI_COLORS["text_primary"],
            bg=UI_COLORS["bg_dark"]
        ).pack(anchor=tk.W, pady=(10, 5))

        results_frame = tk.Frame(main_frame, bg=UI_COLORS["bg_medium"])
        results_frame.pack(fill=tk.BOTH, expand=True)

        self.results_listbox = tk.Listbox(
            results_frame,
            font=("Segoe UI", 10),
            bg=UI_COLORS["bg_medium"],
            fg=UI_COLORS["text_primary"],
            selectbackground=UI_COLORS["accent"],
            height=10
        )
        self.results_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_listbox.yview)
        self.results_listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.results_listbox.bind('<<ListboxSelect>>', self._on_select)
        self.results_listbox.bind('<Double-1>', lambda e: self._confirm())

        # Store search results
        self.search_results = []

        # Buttons
        btn_frame = tk.Frame(main_frame, bg=UI_COLORS["bg_dark"])
        btn_frame.pack(fill=tk.X, pady=(15, 0))

        cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["text_secondary"],
            relief=tk.FLAT,
            command=self.dialog.destroy,
            padx=20,
            pady=8
        )
        cancel_btn.pack(side=tk.RIGHT)

        self.confirm_btn = tk.Button(
            btn_frame,
            text="Use Selected Player",
            font=("Segoe UI", 10, "bold"),
            fg="white",
            bg="#22c55e",
            relief=tk.FLAT,
            command=self._confirm,
            padx=20,
            pady=8,
            state=tk.DISABLED
        )
        self.confirm_btn.pack(side=tk.RIGHT, padx=(0, 10))

        # Initial search
        self._do_search()

    def _do_search(self):
        """Search for players."""
        query = self.search_var.get().strip()
        if len(query) < 2:
            return

        self.results_listbox.delete(0, tk.END)
        self.search_results = db.search_players(query, limit=30)

        # Filter to only show canonical players (not aliases)
        canonical_results = []
        for p in self.search_results:
            canonical_id = db.get_canonical_id(p['id'])
            if canonical_id == p['id']:
                canonical_results.append(p)

        self.search_results = canonical_results

        for p in self.search_results:
            rank = p.get('current_ranking')
            rank_str = f"Rank #{rank}" if rank else "Unranked"
            country = p.get('country', '')
            country_str = f" ({country})" if country else ""
            self.results_listbox.insert(
                tk.END,
                f"{p['name']}{country_str} - {rank_str} [ID: {p['id']}]"
            )

    def _on_select(self, event):
        """Handle selection."""
        selection = self.results_listbox.curselection()
        if selection:
            self.selected_player = self.search_results[selection[0]]
            self.confirm_btn.config(state=tk.NORMAL)
        else:
            self.selected_player = None
            self.confirm_btn.config(state=tk.DISABLED)

    def _confirm(self):
        """Confirm selection and close."""
        if self.selected_player:
            self.callback(self.selected_player)
            self.dialog.destroy()


class TennisExplorerImportDialog:
    """Dialog for importing matches from Tennis Explorer player URLs."""

    def __init__(self, parent):
        self.parent = parent
        self.matches = []
        self.player_name = ""  # Name scraped from Tennis Explorer
        self.player_id = None  # Database player ID to assign matches to
        self.matched_player = None  # Full player dict from database

        self._create_dialog()

    def _create_dialog(self):
        """Create the import dialog."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Import from Tennis Explorer")
        self.dialog.geometry("900x600")
        self.dialog.configure(bg=UI_COLORS["bg_dark"])
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Main container
        main_frame = ttk.Frame(self.dialog, style="Dark.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # URL input section
        url_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        url_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(url_frame, text="Tennis Explorer URL:",
                  style="Dark.TLabel").pack(side=tk.LEFT)

        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(url_frame, textvariable=self.url_var, width=70)
        self.url_entry.pack(side=tk.LEFT, padx=(10, 10), fill=tk.X, expand=True)

        self.preview_btn = ttk.Button(url_frame, text="Preview",
                                       command=self._preview_matches)
        self.preview_btn.pack(side=tk.LEFT, padx=(0, 5))

        # Help text
        help_text = "Example: https://www.tennisexplorer.com/player/schiessl-c0557/?annual=2025"
        ttk.Label(main_frame, text=help_text, style="Dark.TLabel",
                  foreground="#888888").pack(anchor=tk.W)

        # Status/Player info
        self.status_var = tk.StringVar(value="Enter a Tennis Explorer player URL and click Preview")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var,
                                       style="Dark.TLabel")
        self.status_label.pack(fill=tk.X, pady=(10, 5))

        # Player assignment section (hidden until preview)
        self.assign_frame = tk.Frame(main_frame, bg=UI_COLORS["bg_medium"], padx=10, pady=8)
        # Don't pack yet - will be shown after preview

        tk.Label(
            self.assign_frame,
            text="Assign matches to:",
            font=("Segoe UI", 10),
            fg=UI_COLORS["text_secondary"],
            bg=UI_COLORS["bg_medium"]
        ).pack(side=tk.LEFT)

        self.assign_player_label = tk.Label(
            self.assign_frame,
            text="",
            font=("Segoe UI", 11, "bold"),
            fg=UI_COLORS["text_primary"],
            bg=UI_COLORS["bg_medium"]
        )
        self.assign_player_label.pack(side=tk.LEFT, padx=(10, 0))

        self.assign_btn = tk.Button(
            self.assign_frame,
            text="Change",
            font=("Segoe UI", 9),
            fg="white",
            bg="#8b5cf6",
            relief=tk.FLAT,
            cursor="hand2",
            command=self._open_assign_dialog,
            padx=10,
            pady=2
        )
        self.assign_btn.pack(side=tk.LEFT, padx=(15, 0))

        self.assign_status_label = tk.Label(
            self.assign_frame,
            text="",
            font=("Segoe UI", 9),
            fg="#22c55e",
            bg=UI_COLORS["bg_medium"]
        )
        self.assign_status_label.pack(side=tk.LEFT, padx=(15, 0))

        # Matches treeview
        tree_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

        columns = ("date", "result", "opponent", "round", "score", "tournament")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                  style="Dark.Treeview")

        self.tree.heading("date", text="Date")
        self.tree.heading("result", text="W/L")
        self.tree.heading("opponent", text="Opponent")
        self.tree.heading("round", text="Round")
        self.tree.heading("score", text="Score")
        self.tree.heading("tournament", text="Tournament")

        self.tree.column("date", width=90)
        self.tree.column("result", width=50)
        self.tree.column("opponent", width=180)
        self.tree.column("round", width=60)
        self.tree.column("score", width=120)
        self.tree.column("tournament", width=200)

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bottom buttons
        btn_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        self.import_btn = ttk.Button(btn_frame, text="Import Matches",
                                      command=self._import_matches, state=tk.DISABLED)
        self.import_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.clear_btn = ttk.Button(btn_frame, text="Clear", command=self._clear)
        self.clear_btn.pack(side=tk.LEFT)

        ttk.Button(btn_frame, text="Close",
                   command=self.dialog.destroy).pack(side=tk.RIGHT)

        # Match count label
        self.count_var = tk.StringVar(value="")
        ttk.Label(btn_frame, textvariable=self.count_var,
                  style="Dark.TLabel").pack(side=tk.RIGHT, padx=20)

    def _preview_matches(self):
        """Fetch and preview matches from the URL."""
        url = self.url_var.get().strip()

        if not url:
            messagebox.showwarning("No URL", "Please enter a Tennis Explorer URL")
            return

        if "tennisexplorer.com/player/" not in url:
            messagebox.showwarning("Invalid URL",
                "Please enter a valid Tennis Explorer player URL\n"
                "Example: https://www.tennisexplorer.com/player/player-name/?annual=2025")
            return

        self.status_var.set("Fetching data...")
        self.dialog.update()

        try:
            matches, player_name = self._scrape_url(url)
            self.matches = matches
            self.player_name = player_name

            # Clear tree
            self.tree.delete(*self.tree.get_children())

            # Populate tree
            for m in matches:
                result_display = "W" if m['won'] else "L"
                tag = "win" if m['won'] else "loss"
                self.tree.insert("", tk.END, values=(
                    m['date'],
                    result_display,
                    m['opponent'],
                    m['round'],
                    m['score'],
                    m['tournament']
                ), tags=(tag,))

            # Configure tags for coloring
            self.tree.tag_configure("win", foreground="#4ade80")
            self.tree.tag_configure("loss", foreground="#f87171")

            self.status_var.set(f"Scraped: {player_name}")
            self.count_var.set(f"Found {len(matches)} matches")

            # Find matched database player
            self._find_matched_player(player_name)

            # Show assignment section
            self.assign_frame.pack(fill=tk.X, pady=(5, 5))

            if matches:
                self.import_btn.config(state=tk.NORMAL)
            else:
                self.import_btn.config(state=tk.DISABLED)

        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
            messagebox.showerror("Error", f"Failed to fetch data:\n{str(e)}")

    def _find_matched_player(self, player_name: str):
        """Find the database player that matches the scraped name."""
        import random

        # Check name_matcher first for explicit mapping
        mapped_id = name_matcher.get_db_id(player_name)
        if mapped_id:
            player = db.get_player(mapped_id)
            if player:
                self.matched_player = player
                self.player_id = player['id']
                self._update_assign_display()
                return

        # Try database lookup
        player = db.get_player_by_name(player_name)
        if player:
            self.matched_player = player
            self.player_id = player['id']
            self._update_assign_display()
            return

        # No match found - will create new player on import
        self.matched_player = None
        self.player_id = None
        self._update_assign_display()

    def _update_assign_display(self):
        """Update the assignment display."""
        if self.matched_player:
            name = self.matched_player.get('name', 'Unknown')
            player_id = self.matched_player.get('id')
            rank = self.matched_player.get('current_ranking')
            rank_str = f" (Rank #{rank})" if rank else ""
            self.assign_player_label.config(
                text=f"{name}{rank_str} [ID: {player_id}]",
                fg=UI_COLORS["text_primary"]
            )
            self.assign_status_label.config(text="")
        else:
            self.assign_player_label.config(
                text="No match found - will create new player",
                fg="#f97316"  # Orange warning color
            )
            self.assign_status_label.config(text="Click 'Change' to assign to existing player")

    def _open_assign_dialog(self):
        """Open the player assignment dialog."""
        def on_player_selected(player):
            self.matched_player = player
            self.player_id = player['id']
            self._update_assign_display()
            self.assign_status_label.config(text="Assignment changed!")

            # Save name mapping for future imports
            name_matcher.add_mapping(self.player_name, player['id'])

        PlayerAssignDialog(
            self.dialog,
            current_name=self.player_name,
            current_id=self.player_id,
            callback=on_player_selected
        )

    def _scrape_url(self, url: str) -> tuple[List[Dict], str]:
        """Scrape matches from Tennis Explorer URL."""
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")

        soup = BeautifulSoup(response.text, 'html.parser')

        # Get player name
        player_name = 'Unknown'
        h3 = soup.select_one('h3')
        if h3:
            player_name = h3.get_text(strip=True).split('Country')[0].strip()

        # Extract year from URL if present
        year = datetime.now().year
        year_match = re.search(r'annual=(\d{4})', url)
        if year_match:
            year = int(year_match.group(1))

        matches = []
        current_tournament = ''

        # Find the "Played Matches - Singles" section specifically
        # Look for div/section with "Singles" in class or preceding header
        # Skip Balance tables, Tournament Results tables, etc.
        singles_section = None

        # Method 1: Find by looking for "balance" divs and avoiding them
        # The played matches tables are typically in a div after "Singles" header
        for div in soup.select('div.box'):
            # Check if this div has a header mentioning "Singles" or "Played"
            header = div.select_one('div.box-header, h2, h3')
            if header:
                header_text = header.get_text(strip=True).lower()
                if 'singles' in header_text or 'played' in header_text:
                    singles_section = div
                    break

        # If we found a singles section, only parse tables from it
        # Otherwise fall back to parsing all tables (but skip balance-like tables)
        if singles_section:
            tables = singles_section.select('table')
        else:
            tables = soup.select('table')
            # Filter out balance/stats tables by checking for specific patterns
            tables = [t for t in tables if not t.select_one('th') or
                      not any(kw in (t.select_one('th').get_text(strip=True).lower() if t.select_one('th') else '')
                              for kw in ['balance', 'total', 'clay', 'hard', 'grass'])]

        for table in tables:
            rows = table.select('tr')
            for row in rows:
                row_class = row.get('class', [])
                cells = row.select('td')

                if not cells:
                    continue

                # Tournament header row - check multiple patterns
                # Pattern 1: Row with 'head' and 'flags' classes
                # Pattern 2: Row with tournament link (href containing tournament path)
                # Pattern 3: Row that looks like a header (no date, has tournament-like text)
                is_tournament_header = False

                if 'head' in row_class and 'flags' in row_class:
                    is_tournament_header = True
                elif 'head' in row_class:
                    # Some headers only have 'head' class
                    is_tournament_header = True
                else:
                    # Check if first cell contains a tournament link
                    tournament_link = cells[0].select_one('a[href*="/atp"], a[href*="/wta"], a[href*="challenger"], a[href*="itf"]')
                    if tournament_link:
                        is_tournament_header = True
                    # Or if first cell text looks like a tournament (no date pattern, has location words)
                    elif not re.match(r'^\d{1,2}\.\d{1,2}\.$', cells[0].get_text(strip=True)):
                        text = cells[0].get_text(strip=True)
                        if any(keyword in text.lower() for keyword in ['open', 'masters', 'challenger', 'atp', 'wta', 'itf', 'grand slam']):
                            is_tournament_header = True

                if is_tournament_header:
                    current_tournament = cells[0].get_text(strip=True)
                    continue

                # Match row - check for date
                first_cell = cells[0].get_text(strip=True)
                date_match = re.match(r'^(\d{1,2})\.(\d{1,2})\.$', first_cell)

                if date_match and len(cells) >= 4:
                    day, month = date_match.groups()

                    # Find the cell containing player names (format: "Player1-Player2")
                    # This cell contains a dash between two names, NOT a round indicator
                    match_cell = ''
                    match_cell_idx = -1

                    # Round indicators we need to avoid mistaking for player names
                    round_pattern = re.compile(r'^(F|SF|QF|R16|R32|R64|R128|[1-4]R|Q-[1-3]R|Q-R\d+|RR|BR)$')

                    for idx, cell in enumerate(cells[1:], start=1):  # Skip date cell
                        text = cell.get_text(strip=True)
                        # Player cell has a dash, contains letters, and is NOT a round indicator
                        if '-' in text and re.search(r'[a-zA-Z]{2,}', text) and not round_pattern.match(text):
                            match_cell = text
                            match_cell_idx = idx
                            break

                    if not match_cell:
                        continue

                    # Skip doubles (contains "/" for team separator)
                    if '/' in match_cell:
                        continue

                    # Find round and score from cells AFTER the player cell
                    round_name = ''
                    score = ''

                    for cell in cells[match_cell_idx + 1:]:
                        text = cell.get_text(strip=True)
                        if round_pattern.match(text) and not round_name:
                            round_name = text
                        elif re.match(r'^\d+-\d+', text):
                            # Score starts with digits-digits (e.g., "6-4", "7-6(5)", "64-7")
                            # Can appear with or without round
                            score = text
                            break

                    # Parse players from the match cell
                    # Handle format like "Fritz-Garin" or "Spizzirri E.-Garin C."
                    # Find the split point - look for pattern like "X.-Y" or just "-"
                    split_match = re.search(r'([A-Za-z])\.-', match_cell)
                    if split_match:
                        # Split after the period: "Spizzirri E.-Garin C." -> ["Spizzirri E.", "Garin C."]
                        idx = split_match.end() - 1
                        player1 = match_cell[:idx].strip()
                        player2 = match_cell[idx+1:].strip()
                    else:
                        # Simple split: "Fritz-Garin" -> ["Fritz", "Garin"]
                        parts = match_cell.split('-', 1)
                        player1 = parts[0].strip()
                        player2 = parts[1].strip() if len(parts) > 1 else ''

                    if not player2:
                        continue

                    # Determine win/loss - check if our player name is first (winner)
                    player_parts = player_name.lower().split()
                    player1_lower = player1.lower()

                    won = any(part in player1_lower for part in player_parts if len(part) > 2)
                    opponent = player2 if won else player1

                    # Skip matches with invalid tournament names (just years like "2025", "2024")
                    # These come from Balance/Stats tables, not actual played matches
                    if current_tournament and re.match(r'^\d{4}$', current_tournament):
                        continue

                    matches.append({
                        'date': f'{year}-{month.zfill(2)}-{day.zfill(2)}',
                        'tournament': current_tournament,
                        'won': won,
                        'opponent': opponent,
                        'round': round_name,
                        'score': score,
                        'player_name': player_name
                    })

        # Deduplicate matches (page may have multiple tables with same data)
        seen = set()
        unique_matches = []
        for m in matches:
            key = (m['date'], m['opponent'], m['score'])
            if key not in seen:
                seen.add(key)
                unique_matches.append(m)
        matches = unique_matches

        # Fix year assignments - Tennis Explorer "annual=YYYY" pages show the season
        # which can span two calendar years. January matches on a 2025 page are likely 2026.
        # Detect year boundary: if we go from early months (Jan-Mar) to later months (Apr-Dec),
        # the earlier months should be year+1
        if matches:
            # Check if we have a year boundary situation
            has_early_months = any(int(m['date'][5:7]) <= 3 for m in matches)
            has_late_months = any(int(m['date'][5:7]) >= 9 for m in matches)

            if has_early_months and has_late_months:
                # We have matches spanning a year boundary
                # Early months (Jan-Mar) should be year+1
                for m in matches:
                    month = int(m['date'][5:7])
                    if month <= 3:  # January, February, March
                        old_year = int(m['date'][:4])
                        m['date'] = f"{old_year + 1}{m['date'][4:]}"

            # Filter to only include matches from the requested year
            matches = [m for m in matches if int(m['date'][:4]) == year]

        return matches, player_name

    def _import_matches(self):
        """Import the previewed matches to the database."""
        if not self.matches:
            messagebox.showwarning("No Matches", "No matches to import")
            return

        # Confirm import
        result = messagebox.askyesno("Confirm Import",
            f"Import {len(self.matches)} matches for {self.player_name}?\n\n"
            "This will add these matches to the database.")

        if not result:
            return

        try:
            imported, skipped = self._do_import()

            messagebox.showinfo("Import Complete",
                f"Successfully imported {imported} matches.\n"
                f"Skipped {skipped} duplicates.")

            self.status_var.set(f"Imported {imported} matches, skipped {skipped} duplicates")

        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import:\n{str(e)}")

    def _do_import(self) -> tuple[int, int]:
        """Perform the actual database import."""
        import random

        imported = 0
        skipped = 0

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Use pre-selected player_id from assignment dialog if available
            if self.player_id:
                player_id = self.player_id
                player_name_for_match = self.matched_player['name'] if self.matched_player else self.player_name
                print(f"TE Import: Using pre-assigned player ID {player_id} ({player_name_for_match})")
            else:
                # Create new player if no assignment was made
                # Use hash of name for deterministic ID (avoids collisions from random)
                import hashlib
                name_hash = int(hashlib.md5(self.player_name.lower().encode()).hexdigest()[:8], 16)
                player_id = -(name_hash % 900000 + 100000)
                player_name_for_match = self.player_name
                cursor.execute("""
                    INSERT OR IGNORE INTO players (id, name, country)
                    VALUES (?, ?, '')
                """, (player_id, self.player_name))
                print(f"TE Import: Created new player: {self.player_name} (ID: {player_id})")
                self.player_id = player_id

            for match in self.matches:
                # Get or create opponent - prioritize upcoming_matches IDs
                opponent_name = match['opponent']
                opponent_id = None

                # First check upcoming_matches for the correct ID
                opp_parts = opponent_name.lower().split()
                opp_last = opp_parts[-1] if opp_parts else ""
                opp_first = opp_parts[0] if opp_parts else ""

                cursor.execute("""
                    SELECT player1_id, player1_name, player2_id, player2_name
                    FROM upcoming_matches
                    WHERE LOWER(player1_name) LIKE ? OR LOWER(player2_name) LIKE ?
                """, (f"%{opp_last}%", f"%{opp_last}%"))

                for row in cursor.fetchall():
                    p1_lower = (row[1] or "").lower()
                    p2_lower = (row[3] or "").lower()
                    if opp_last in p1_lower and (opp_first in p1_lower or len(opp_first) < 3):
                        opponent_id = row[0]
                        break
                    if opp_last in p2_lower and (opp_first in p2_lower or len(opp_first) < 3):
                        opponent_id = row[2]
                        break

                # Fall back to database lookup
                if not opponent_id:
                    opponent = db.get_player_by_name(opponent_name)
                    if opponent:
                        opponent_id = opponent['id']

                # Create new player if not found
                if not opponent_id:
                    # Use hash of name for deterministic ID (avoids collisions from random)
                    import hashlib
                    opp_hash = int(hashlib.md5(opponent_name.lower().encode()).hexdigest()[:8], 16)
                    opponent_id = -(opp_hash % 900000 + 100000)
                    cursor.execute("""
                        INSERT OR IGNORE INTO players (id, name, country)
                        VALUES (?, ?, '')
                    """, (opponent_id, opponent_name))

                # Determine winner/loser
                if match['won']:
                    winner_id = player_id
                    winner_name = player_name_for_match
                    loser_id = opponent_id
                    loser_name = opponent_name
                else:
                    winner_id = opponent_id
                    winner_name = opponent_name
                    loser_id = player_id
                    loser_name = player_name_for_match

                # Check if match already exists by date + score + player involved
                # This catches duplicates while avoiding false positives from other players' matches
                cursor.execute("""
                    SELECT id FROM matches
                    WHERE date = ? AND score = ?
                    AND (winner_name LIKE ? OR loser_name LIKE ?)
                """, (match['date'], match['score'], f'%{self.player_name.split()[0]}%', f'%{self.player_name.split()[0]}%'))
                existing = cursor.fetchone()

                if existing:
                    skipped += 1
                    continue

                # Create unique match ID
                match_id = f"TE_{match['date']}_{winner_id}_{loser_id}"

                # Determine surface from tournament name
                surface = self._guess_surface(match['tournament'])

                # Insert match
                cursor.execute("""
                    INSERT INTO matches (id, tournament, surface, date, round,
                                        winner_id, winner_name, loser_id, loser_name, score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    match_id,
                    match['tournament'],
                    surface,
                    match['date'],
                    match['round'],
                    winner_id,
                    winner_name,
                    loser_id,
                    loser_name,
                    match['score']
                ))
                imported += 1

        return imported, skipped

    def _guess_surface(self, tournament: str) -> str:
        """Guess surface from tournament name."""
        tournament_lower = tournament.lower()

        if any(x in tournament_lower for x in ['clay', 'roland', 'rome', 'madrid', 'barcelona']):
            return 'Clay'
        elif any(x in tournament_lower for x in ['grass', 'wimbledon', 'halle', 'queens']):
            return 'Grass'
        elif any(x in tournament_lower for x in ['carpet']):
            return 'Carpet'
        else:
            return 'Hard'

    def _clear(self):
        """Clear the form."""
        self.url_var.set("")
        self.tree.delete(*self.tree.get_children())
        self.matches = []
        self.player_name = ""
        self.player_id = None
        self.matched_player = None
        self.status_var.set("Enter a Tennis Explorer player URL and click Preview")
        self.count_var.set("")
        self.import_btn.config(state=tk.DISABLED)
        self.assign_frame.pack_forget()  # Hide assignment section


def open_te_import_dialog(parent):
    """Open the Tennis Explorer import dialog."""
    TennisExplorerImportDialog(parent)
