"""
Match Assignment UI - Fix wrong player assignments in imported matches.

When importing matches, players sometimes get assigned to the wrong person
(e.g., "Jessika Ponchet" matches to "Matt Ponchet" by last name).

This UI allows:
1. Viewing recently imported matches
2. Reassigning matches to the correct player
3. Creating name mappings to prevent future mistakes
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, List
from datetime import datetime, timedelta

from config import UI_COLORS
from database import db
from name_matcher import name_matcher


class MatchAssignmentUI:
    """UI for fixing wrong player assignments in matches."""

    def __init__(self, parent: tk.Tk = None):
        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()

        self.root.title("Match Assignment - Fix Player Assignments")
        self.root.geometry("1200x700")
        self.root.configure(bg=UI_COLORS["bg_dark"])

        self._setup_styles()
        self._create_widgets()
        self._load_recent_matches()

    def _setup_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure("Dark.TFrame", background=UI_COLORS["bg_dark"])
        style.configure("Card.TFrame", background=UI_COLORS["bg_medium"])
        style.configure(
            "Dark.TLabel",
            background=UI_COLORS["bg_dark"],
            foreground=UI_COLORS["text_primary"],
            font=("Segoe UI", 10)
        )
        style.configure(
            "Title.TLabel",
            background=UI_COLORS["bg_dark"],
            foreground=UI_COLORS["text_primary"],
            font=("Segoe UI", 16, "bold")
        )
        style.configure(
            "Treeview",
            background=UI_COLORS["bg_medium"],
            foreground=UI_COLORS["text_primary"],
            fieldbackground=UI_COLORS["bg_medium"],
            rowheight=28,
            font=("Segoe UI", 10)
        )
        style.configure(
            "Treeview.Heading",
            background=UI_COLORS["bg_light"],
            foreground=UI_COLORS["text_primary"],
            font=("Segoe UI", 10, "bold")
        )
        style.map("Treeview", background=[("selected", UI_COLORS["accent"])])

    def _create_widgets(self):
        """Create the UI widgets."""
        main_frame = ttk.Frame(self.root, style="Dark.TFrame", padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title row
        title_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        title_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(
            title_frame,
            text="Match Assignment - Fix Wrong Player Assignments",
            style="Title.TLabel"
        ).pack(side=tk.LEFT)

        # Refresh button
        refresh_btn = tk.Button(
            title_frame,
            text="Refresh",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["accent"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._load_recent_matches,
            padx=15,
            pady=5
        )
        refresh_btn.pack(side=tk.RIGHT)

        # Days filter
        days_frame = ttk.Frame(title_frame, style="Dark.TFrame")
        days_frame.pack(side=tk.RIGHT, padx=(0, 15))

        ttk.Label(days_frame, text="Show matches from last:", style="Dark.TLabel").pack(side=tk.LEFT)

        self.days_var = tk.StringVar(value="7")
        days_combo = ttk.Combobox(
            days_frame,
            textvariable=self.days_var,
            values=["3", "7", "14", "30", "90"],
            width=5,
            state="readonly"
        )
        days_combo.pack(side=tk.LEFT, padx=5)
        days_combo.bind("<<ComboboxSelected>>", lambda e: self._load_recent_matches())

        ttk.Label(days_frame, text="days", style="Dark.TLabel").pack(side=tk.LEFT)

        # Instructions
        instructions = tk.Label(
            main_frame,
            text="Select a match below, then click 'Assign Winner' or 'Assign Loser' to fix wrong player assignments.\n"
                 "This will also create a name mapping to prevent the same mistake in future imports.",
            font=("Segoe UI", 9),
            fg=UI_COLORS["text_secondary"],
            bg=UI_COLORS["bg_dark"],
            justify=tk.LEFT
        )
        instructions.pack(fill=tk.X, pady=(0, 10))

        # Matches list
        list_frame = ttk.Frame(main_frame, style="Card.TFrame")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        columns = ("date", "tournament", "winner", "winner_id", "loser", "loser_id", "score")
        self.matches_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)

        self.matches_tree.heading("date", text="Date")
        self.matches_tree.heading("tournament", text="Tournament")
        self.matches_tree.heading("winner", text="Winner")
        self.matches_tree.heading("winner_id", text="Winner ID")
        self.matches_tree.heading("loser", text="Loser")
        self.matches_tree.heading("loser_id", text="Loser ID")
        self.matches_tree.heading("score", text="Score")

        self.matches_tree.column("date", width=100, anchor=tk.CENTER)
        self.matches_tree.column("tournament", width=200)
        self.matches_tree.column("winner", width=180)
        self.matches_tree.column("winner_id", width=100, anchor=tk.CENTER)
        self.matches_tree.column("loser", width=180)
        self.matches_tree.column("loser_id", width=100, anchor=tk.CENTER)
        self.matches_tree.column("score", width=120, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.matches_tree.yview)
        self.matches_tree.configure(yscrollcommand=scrollbar.set)

        self.matches_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.matches_tree.bind('<<TreeviewSelect>>', self._on_match_select)

        # Assignment panel
        assign_frame = ttk.Frame(main_frame, style="Card.TFrame", padding=15)
        assign_frame.pack(fill=tk.X)

        # Selected match info
        info_frame = ttk.Frame(assign_frame, style="Card.TFrame")
        info_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(info_frame, text="Selected Match:", style="Dark.TLabel").pack(side=tk.LEFT)
        self.selected_match_label = tk.Label(
            info_frame,
            text="None",
            font=("Segoe UI", 10, "bold"),
            fg=UI_COLORS["text_primary"],
            bg=UI_COLORS["bg_medium"]
        )
        self.selected_match_label.pack(side=tk.LEFT, padx=(10, 0))

        # Assignment buttons row
        buttons_frame = ttk.Frame(assign_frame, style="Card.TFrame")
        buttons_frame.pack(fill=tk.X)

        # Winner assignment
        winner_frame = ttk.Frame(buttons_frame, style="Card.TFrame")
        winner_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        tk.Label(
            winner_frame,
            text="Winner:",
            font=("Segoe UI", 10, "bold"),
            fg=UI_COLORS["success"],
            bg=UI_COLORS["bg_medium"]
        ).pack(side=tk.LEFT)

        self.winner_name_label = tk.Label(
            winner_frame,
            text="-",
            font=("Segoe UI", 10),
            fg=UI_COLORS["text_primary"],
            bg=UI_COLORS["bg_medium"],
            width=25,
            anchor=tk.W
        )
        self.winner_name_label.pack(side=tk.LEFT, padx=(5, 10))

        assign_winner_btn = tk.Button(
            winner_frame,
            text="Assign Winner",
            font=("Segoe UI", 10, "bold"),
            fg="white",
            bg=UI_COLORS["success"],
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._open_assign_dialog("winner"),
            padx=15,
            pady=5
        )
        assign_winner_btn.pack(side=tk.LEFT)

        # Loser assignment
        loser_frame = ttk.Frame(buttons_frame, style="Card.TFrame")
        loser_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))

        tk.Label(
            loser_frame,
            text="Loser:",
            font=("Segoe UI", 10, "bold"),
            fg=UI_COLORS["danger"],
            bg=UI_COLORS["bg_medium"]
        ).pack(side=tk.LEFT)

        self.loser_name_label = tk.Label(
            loser_frame,
            text="-",
            font=("Segoe UI", 10),
            fg=UI_COLORS["text_primary"],
            bg=UI_COLORS["bg_medium"],
            width=25,
            anchor=tk.W
        )
        self.loser_name_label.pack(side=tk.LEFT, padx=(5, 10))

        assign_loser_btn = tk.Button(
            loser_frame,
            text="Assign Loser",
            font=("Segoe UI", 10, "bold"),
            fg="white",
            bg=UI_COLORS["danger"],
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._open_assign_dialog("loser"),
            padx=15,
            pady=5
        )
        assign_loser_btn.pack(side=tk.LEFT)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_label = tk.Label(
            main_frame,
            textvariable=self.status_var,
            font=("Segoe UI", 9),
            fg=UI_COLORS["text_secondary"],
            bg=UI_COLORS["bg_dark"],
            anchor=tk.W
        )
        status_label.pack(fill=tk.X, pady=(10, 0))

        # Store selected match data
        self.selected_match = None
        self.matches_data = []

    def _load_recent_matches(self):
        """Load recent matches from database."""
        days = int(self.days_var.get())
        self.matches_tree.delete(*self.matches_tree.get_children())

        matches = db.get_recent_matches(days=days)
        self.matches_data = matches

        for match in matches:
            match_date = match.get('date', '')[:10] if match.get('date') else ''
            tournament = match.get('tournament') or match.get('tourney_name') or match.get('tournament_id', '')
            winner_name = match.get('winner_name', 'Unknown')
            winner_id = match.get('winner_id', '')
            loser_name = match.get('loser_name', 'Unknown')
            loser_id = match.get('loser_id', '')
            score = match.get('score', '')

            self.matches_tree.insert("", tk.END, iid=match.get('id'), values=(
                match_date,
                tournament,
                winner_name,
                winner_id,
                loser_name,
                loser_id,
                score
            ))

        self.status_var.set(f"Loaded {len(matches)} matches from last {days} days")

    def _on_match_select(self, event):
        """Handle match selection."""
        selection = self.matches_tree.selection()
        if not selection:
            self.selected_match = None
            self.selected_match_label.config(text="None")
            self.winner_name_label.config(text="-")
            self.loser_name_label.config(text="-")
            return

        match_id = selection[0]
        item = self.matches_tree.item(match_id)
        values = item['values']

        # Find full match data
        self.selected_match = None
        for m in self.matches_data:
            if m.get('id') == match_id:
                self.selected_match = m
                break

        if self.selected_match:
            winner = values[2]
            loser = values[4]
            self.selected_match_label.config(text=f"{winner} vs {loser}")
            self.winner_name_label.config(text=f"{winner} (ID: {values[3]})")
            self.loser_name_label.config(text=f"{loser} (ID: {values[5]})")

    def _open_assign_dialog(self, player_type: str):
        """Open dialog to assign a player."""
        if not self.selected_match:
            messagebox.showwarning("No Match Selected", "Please select a match first.")
            return

        if player_type == "winner":
            current_name = self.selected_match.get('winner_name', 'Unknown')
            current_id = self.selected_match.get('winner_id')
        else:
            current_name = self.selected_match.get('loser_name', 'Unknown')
            current_id = self.selected_match.get('loser_id')

        dialog = PlayerAssignDialog(
            self.root,
            current_name=current_name,
            current_id=current_id,
            player_type=player_type,
            callback=lambda player: self._do_assignment(player_type, player)
        )

    def _do_assignment(self, player_type: str, new_player: Dict):
        """Perform the player assignment."""
        if not self.selected_match or not new_player:
            return

        match_id = self.selected_match.get('id')
        old_name = self.selected_match.get(f'{player_type}_name', 'Unknown')
        old_id = self.selected_match.get(f'{player_type}_id')
        new_id = new_player['id']
        new_name = new_player['name']

        # Update the match in database
        with db.get_connection() as conn:
            cursor = conn.cursor()
            if player_type == "winner":
                cursor.execute(
                    "UPDATE matches SET winner_id = ? WHERE id = ?",
                    (new_id, match_id)
                )
            else:
                cursor.execute(
                    "UPDATE matches SET loser_id = ? WHERE id = ?",
                    (new_id, match_id)
                )

        # Add name mapping to prevent future mistakes
        # Map the original name to the correct player ID
        name_matcher.add_mapping(old_name, new_id)

        # Also add to player_aliases if old_id exists and is different
        if old_id and old_id != new_id:
            db.add_player_alias(old_id, new_id, source='manual_assignment')

        self.status_var.set(
            f"Assigned '{old_name}' -> '{new_name}' (ID: {new_id}). "
            f"Name mapping saved for future imports."
        )

        # Refresh the list
        self._load_recent_matches()

        messagebox.showinfo(
            "Assignment Complete",
            f"Match updated!\n\n"
            f"'{old_name}' -> '{new_name}'\n\n"
            f"A name mapping has been saved so future imports of "
            f"'{old_name}' will automatically use '{new_name}'."
        )

    def run(self):
        """Run the window."""
        self.root.mainloop()


class PlayerAssignDialog:
    """Dialog for searching and selecting a player to assign."""

    def __init__(self, parent, current_name: str, current_id: int,
                 player_type: str, callback):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Assign {player_type.title()}")
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

        self._create_widgets(current_name, current_id, player_type)

    def _create_widgets(self, current_name: str, current_id: int, player_type: str):
        """Create dialog widgets."""
        main_frame = tk.Frame(self.dialog, bg=UI_COLORS["bg_dark"], padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Current assignment
        current_frame = tk.Frame(main_frame, bg=UI_COLORS["bg_dark"])
        current_frame.pack(fill=tk.X, pady=(0, 15))

        tk.Label(
            current_frame,
            text=f"Current {player_type}:",
            font=("Segoe UI", 10),
            fg=UI_COLORS["text_secondary"],
            bg=UI_COLORS["bg_dark"]
        ).pack(anchor=tk.W)

        tk.Label(
            current_frame,
            text=f"{current_name} (ID: {current_id})",
            font=("Segoe UI", 11, "bold"),
            fg=UI_COLORS["text_primary"],
            bg=UI_COLORS["bg_dark"]
        ).pack(anchor=tk.W)

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

        self.search_var = tk.StringVar(value=current_name.split()[-1])  # Default to last name
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
            text="Assign Selected Player",
            font=("Segoe UI", 10, "bold"),
            fg="white",
            bg=UI_COLORS["success"],
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


def open_match_assignment(parent: tk.Tk = None):
    """Open the match assignment window."""
    ui = MatchAssignmentUI(parent)
    if not parent:
        ui.run()
    return ui


if __name__ == "__main__":
    ui = MatchAssignmentUI()
    ui.run()
