"""
Tennis Betting System - Odds Scraper/Manager
Manage and integrate betting odds from various sources
"""

import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.filedialog as filedialog
from datetime import datetime
from typing import Dict, List, Optional
import json
import csv
import urllib.request
import urllib.error

from config import UI_COLORS, SURFACES
from database import db, TennisDatabase


class OddsManager:
    """Manage betting odds from various sources."""

    def __init__(self, database: TennisDatabase = None):
        self.db = database or db

    def add_odds_manually(self, match_data: Dict) -> int:
        """Add odds manually for an upcoming match."""
        return self.db.add_upcoming_match(match_data)

    def update_odds(self, match_id: int, p1_odds: float, p2_odds: float):
        """Update odds for an existing upcoming match."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE upcoming_matches
                SET player1_odds = ?, player2_odds = ?
                WHERE id = ?
            """, (p1_odds, p2_odds, match_id))

    def import_from_csv(self, filepath: str) -> int:
        """
        Import upcoming matches with odds from CSV file.
        Expected columns: tournament, date, surface, player1, player2, p1_odds, p2_odds
        """
        imported = 0

        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # Try to find player IDs
                    p1_name = row.get('player1', '').strip()
                    p2_name = row.get('player2', '').strip()

                    p1 = self.db.get_player_by_name(p1_name)
                    p2 = self.db.get_player_by_name(p2_name)

                    p1_odds = float(row.get('p1_odds', 0)) if row.get('p1_odds') else None
                    p2_odds = float(row.get('p2_odds', 0)) if row.get('p2_odds') else None

                    match_data = {
                        'tournament': row.get('tournament', ''),
                        'date': row.get('date', datetime.now().strftime("%Y-%m-%d")),
                        'surface': row.get('surface', 'Hard'),
                        'round': row.get('round', ''),
                        'player1_id': p1['id'] if p1 else None,
                        'player2_id': p2['id'] if p2 else None,
                        'player1_name': p1_name,
                        'player2_name': p2_name,
                        'player1_odds': p1_odds,
                        'player2_odds': p2_odds,
                    }

                    self.db.add_upcoming_match(match_data)
                    imported += 1
                except Exception as e:
                    print(f"Error importing row: {e}")
                    continue

        return imported

    def export_to_csv(self, filepath: str) -> int:
        """Export upcoming matches to CSV."""
        matches = self.db.get_upcoming_matches()

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['tournament', 'date', 'round', 'surface',
                            'player1', 'player2', 'p1_odds', 'p2_odds'])

            for match in matches:
                writer.writerow([
                    match.get('tournament', ''),
                    match.get('date', ''),
                    match.get('round', ''),
                    match.get('surface', ''),
                    match.get('player1_name', ''),
                    match.get('player2_name', ''),
                    match.get('player1_odds', ''),
                    match.get('player2_odds', ''),
                ])

        return len(matches)

    def calculate_implied_probabilities(self, p1_odds: float, p2_odds: float) -> Dict:
        """Calculate implied probabilities and overround from odds."""
        if not p1_odds or not p2_odds:
            return {}

        p1_implied = 1 / p1_odds
        p2_implied = 1 / p2_odds
        overround = (p1_implied + p2_implied - 1) * 100

        # Fair probabilities (removing overround)
        total_implied = p1_implied + p2_implied
        p1_fair = p1_implied / total_implied
        p2_fair = p2_implied / total_implied

        return {
            'p1_implied': p1_implied,
            'p2_implied': p2_implied,
            'p1_fair': p1_fair,
            'p2_fair': p2_fair,
            'overround': overround,
        }

    def convert_odds(self, odds: float, from_format: str, to_format: str) -> float:
        """
        Convert odds between formats.
        Formats: decimal, american, fractional
        """
        # First convert to decimal
        if from_format == 'decimal':
            decimal_odds = odds
        elif from_format == 'american':
            if odds > 0:
                decimal_odds = (odds / 100) + 1
            else:
                decimal_odds = (100 / abs(odds)) + 1
        elif from_format == 'fractional':
            # Assuming fractional passed as decimal (e.g., 2.5 for 5/2)
            decimal_odds = odds + 1
        else:
            return odds

        # Convert from decimal to target
        if to_format == 'decimal':
            return round(decimal_odds, 2)
        elif to_format == 'american':
            if decimal_odds >= 2:
                return round((decimal_odds - 1) * 100)
            else:
                return round(-100 / (decimal_odds - 1))
        elif to_format == 'fractional':
            return round(decimal_odds - 1, 2)

        return decimal_odds


class OddsManagerUI:
    """Tkinter UI for Odds Manager."""

    def __init__(self, parent: tk.Tk = None):
        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()

        self.root.title("Odds Manager")
        self.root.geometry("1000x700")
        self.root.configure(bg=UI_COLORS["bg_dark"])

        self.manager = OddsManager()
        self.players_cache = []

        self._setup_styles()
        self._build_ui()
        self._load_players()
        self._refresh_matches()

    def _setup_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure("Dark.TFrame", background=UI_COLORS["bg_dark"])
        style.configure("Card.TFrame", background=UI_COLORS["bg_medium"])
        style.configure("Dark.TLabel", background=UI_COLORS["bg_dark"],
                       foreground=UI_COLORS["text_primary"], font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=UI_COLORS["bg_dark"],
                       foreground=UI_COLORS["text_primary"], font=("Segoe UI", 16, "bold"))
        style.configure("Card.TLabel", background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["text_primary"], font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["accent"], font=("Segoe UI", 11, "bold"))

        style.configure("Treeview",
                       background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["text_primary"],
                       fieldbackground=UI_COLORS["bg_medium"],
                       font=("Segoe UI", 9))
        style.configure("Treeview.Heading",
                       background=UI_COLORS["bg_light"],
                       foreground=UI_COLORS["text_primary"],
                       font=("Segoe UI", 9, "bold"))

    def _build_ui(self):
        """Build the main UI."""
        main_frame = ttk.Frame(self.root, style="Dark.TFrame", padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        header_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(header_frame, text="Odds Manager", style="Title.TLabel").pack(side=tk.LEFT)

        # Action buttons
        btn_frame = ttk.Frame(header_frame, style="Dark.TFrame")
        btn_frame.pack(side=tk.RIGHT)

        import_btn = tk.Button(
            btn_frame,
            text="Import CSV",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["accent"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._import_csv,
            padx=15,
            pady=5
        )
        import_btn.pack(side=tk.LEFT, padx=5)

        export_btn = tk.Button(
            btn_frame,
            text="Export CSV",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["success"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._export_csv,
            padx=15,
            pady=5
        )
        export_btn.pack(side=tk.LEFT, padx=5)

        # Odds converter card
        converter_card = ttk.Frame(main_frame, style="Card.TFrame", padding=15)
        converter_card.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(converter_card, text="Odds Converter", style="CardTitle.TLabel").pack(anchor=tk.W)

        converter_row = ttk.Frame(converter_card, style="Card.TFrame")
        converter_row.pack(fill=tk.X, pady=10)

        # Input odds
        ttk.Label(converter_row, text="Odds:", style="Card.TLabel").pack(side=tk.LEFT)
        self.odds_input_var = tk.StringVar()
        odds_entry = ttk.Entry(converter_row, textvariable=self.odds_input_var, width=10)
        odds_entry.pack(side=tk.LEFT, padx=5)

        # From format
        ttk.Label(converter_row, text="From:", style="Card.TLabel").pack(side=tk.LEFT, padx=(10, 0))
        self.from_format_var = tk.StringVar(value="decimal")
        from_combo = ttk.Combobox(converter_row, textvariable=self.from_format_var,
                                   values=["decimal", "american", "fractional"], width=10, state="readonly")
        from_combo.pack(side=tk.LEFT, padx=5)

        # Convert button
        convert_btn = tk.Button(
            converter_row,
            text="Convert",
            font=("Segoe UI", 9),
            fg="white",
            bg=UI_COLORS["accent"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._convert_odds,
            padx=10,
            pady=2
        )
        convert_btn.pack(side=tk.LEFT, padx=10)

        # Results
        self.convert_result_var = tk.StringVar(value="")
        ttk.Label(converter_row, textvariable=self.convert_result_var, style="Card.TLabel").pack(side=tk.LEFT, padx=10)

        # Probability calculator
        prob_row = ttk.Frame(converter_card, style="Card.TFrame")
        prob_row.pack(fill=tk.X, pady=5)

        ttk.Label(prob_row, text="P1 Odds:", style="Card.TLabel").pack(side=tk.LEFT)
        self.p1_odds_var = tk.StringVar()
        p1_entry = ttk.Entry(prob_row, textvariable=self.p1_odds_var, width=8)
        p1_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(prob_row, text="P2 Odds:", style="Card.TLabel").pack(side=tk.LEFT, padx=(10, 0))
        self.p2_odds_var = tk.StringVar()
        p2_entry = ttk.Entry(prob_row, textvariable=self.p2_odds_var, width=8)
        p2_entry.pack(side=tk.LEFT, padx=5)

        calc_btn = tk.Button(
            prob_row,
            text="Calculate",
            font=("Segoe UI", 9),
            fg="white",
            bg=UI_COLORS["success"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._calculate_probabilities,
            padx=10,
            pady=2
        )
        calc_btn.pack(side=tk.LEFT, padx=10)

        self.prob_result_var = tk.StringVar(value="")
        ttk.Label(prob_row, textvariable=self.prob_result_var, style="Card.TLabel").pack(side=tk.LEFT, padx=10)

        # Matches table
        ttk.Label(main_frame, text="Matches with Odds", style="Dark.TLabel").pack(anchor=tk.W, pady=(0, 10))

        columns = ("id", "date", "tournament", "player1", "player2", "surface", "p1_odds", "p2_odds", "overround")
        self.matches_tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=15)

        self.matches_tree.heading("id", text="ID")
        self.matches_tree.heading("date", text="Date")
        self.matches_tree.heading("tournament", text="Tournament")
        self.matches_tree.heading("player1", text="Player 1")
        self.matches_tree.heading("player2", text="Player 2")
        self.matches_tree.heading("surface", text="Surface")
        self.matches_tree.heading("p1_odds", text="P1 Odds")
        self.matches_tree.heading("p2_odds", text="P2 Odds")
        self.matches_tree.heading("overround", text="Overround")

        self.matches_tree.column("id", width=40)
        self.matches_tree.column("date", width=90)
        self.matches_tree.column("tournament", width=120)
        self.matches_tree.column("player1", width=130)
        self.matches_tree.column("player2", width=130)
        self.matches_tree.column("surface", width=70)
        self.matches_tree.column("p1_odds", width=70)
        self.matches_tree.column("p2_odds", width=70)
        self.matches_tree.column("overround", width=80)

        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.matches_tree.yview)
        self.matches_tree.configure(yscrollcommand=scrollbar.set)

        self.matches_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Double-click to edit
        self.matches_tree.bind("<Double-1>", self._edit_match_odds)

        # Bottom buttons
        bottom_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        bottom_frame.pack(fill=tk.X, pady=(10, 0))

        refresh_btn = tk.Button(
            bottom_frame,
            text="Refresh",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["accent"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._refresh_matches,
            padx=15,
            pady=5
        )
        refresh_btn.pack(side=tk.LEFT, padx=5)

        delete_btn = tk.Button(
            bottom_frame,
            text="Delete Selected",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["danger"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._delete_selected,
            padx=15,
            pady=5
        )
        delete_btn.pack(side=tk.LEFT, padx=5)

    def _load_players(self):
        """Load players cache."""
        try:
            self.players_cache = db.get_all_players()
        except Exception as e:
            print(f"Error loading players: {e}")

    def _refresh_matches(self):
        """Refresh matches table."""
        self.matches_tree.delete(*self.matches_tree.get_children())

        matches = db.get_upcoming_matches()
        for match in matches:
            p1_odds = match.get('player1_odds')
            p2_odds = match.get('player2_odds')

            overround = ""
            if p1_odds and p2_odds:
                probs = self.manager.calculate_implied_probabilities(p1_odds, p2_odds)
                overround = f"{probs.get('overround', 0):.1f}%"

            self.matches_tree.insert("", tk.END, values=(
                match.get('id'),
                match.get('date', ''),
                match.get('tournament', ''),
                match.get('player1_name', ''),
                match.get('player2_name', ''),
                match.get('surface', ''),
                f"{p1_odds:.2f}" if p1_odds else "-",
                f"{p2_odds:.2f}" if p2_odds else "-",
                overround,
            ))

    def _convert_odds(self):
        """Convert odds between formats."""
        try:
            odds = float(self.odds_input_var.get())
            from_format = self.from_format_var.get()

            decimal = self.manager.convert_odds(odds, from_format, 'decimal')
            american = self.manager.convert_odds(odds, from_format, 'american')

            self.convert_result_var.set(f"Decimal: {decimal:.2f} | American: {american:+.0f}")
        except ValueError:
            self.convert_result_var.set("Invalid input")

    def _calculate_probabilities(self):
        """Calculate implied probabilities."""
        try:
            p1_odds = float(self.p1_odds_var.get())
            p2_odds = float(self.p2_odds_var.get())

            probs = self.manager.calculate_implied_probabilities(p1_odds, p2_odds)

            self.prob_result_var.set(
                f"P1: {probs['p1_fair']:.1%} | P2: {probs['p2_fair']:.1%} | "
                f"Overround: {probs['overround']:.1f}%"
            )
        except ValueError:
            self.prob_result_var.set("Invalid input")

    def _import_csv(self):
        """Import matches from CSV."""
        filepath = filedialog.askopenfilename(
            title="Import Matches CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if filepath:
            try:
                count = self.manager.import_from_csv(filepath)
                self._refresh_matches()
                messagebox.showinfo("Import Complete", f"Imported {count} matches.")
            except Exception as e:
                messagebox.showerror("Import Error", str(e))

    def _export_csv(self):
        """Export matches to CSV."""
        filepath = filedialog.asksaveasfilename(
            title="Export Matches CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if filepath:
            try:
                count = self.manager.export_to_csv(filepath)
                messagebox.showinfo("Export Complete", f"Exported {count} matches to {filepath}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

    def _edit_match_odds(self, event):
        """Edit odds for selected match."""
        selection = self.matches_tree.selection()
        if not selection:
            return

        item = self.matches_tree.item(selection[0])
        match_id = item['values'][0]
        current_p1 = item['values'][6]
        current_p2 = item['values'][7]

        # Simple dialog to edit odds
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Odds")
        dialog.geometry("300x200")
        dialog.configure(bg=UI_COLORS["bg_dark"])
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, style="Dark.TFrame", padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Player 1 Odds:", style="Dark.TLabel").pack(anchor=tk.W)
        p1_var = tk.StringVar(value=str(current_p1) if current_p1 != "-" else "")
        p1_entry = ttk.Entry(frame, textvariable=p1_var, width=20)
        p1_entry.pack(anchor=tk.W, pady=5)

        ttk.Label(frame, text="Player 2 Odds:", style="Dark.TLabel").pack(anchor=tk.W, pady=(10, 0))
        p2_var = tk.StringVar(value=str(current_p2) if current_p2 != "-" else "")
        p2_entry = ttk.Entry(frame, textvariable=p2_var, width=20)
        p2_entry.pack(anchor=tk.W, pady=5)

        def save_odds():
            try:
                p1_odds = float(p1_var.get()) if p1_var.get() else None
                p2_odds = float(p2_var.get()) if p2_var.get() else None

                self.manager.update_odds(match_id, p1_odds, p2_odds)
                self._refresh_matches()
                dialog.destroy()
            except ValueError:
                messagebox.showwarning("Invalid", "Please enter valid decimal odds.")

        save_btn = tk.Button(
            frame,
            text="Save",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["success"],
            relief=tk.FLAT,
            cursor="hand2",
            command=save_odds,
            padx=15,
            pady=5
        )
        save_btn.pack(pady=20)

    def _delete_selected(self):
        """Delete selected match."""
        selection = self.matches_tree.selection()
        if not selection:
            messagebox.showinfo("Select", "Please select a match to delete.")
            return

        if messagebox.askyesno("Confirm", "Delete selected match?"):
            item = self.matches_tree.item(selection[0])
            match_id = item['values'][0]

            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM upcoming_matches WHERE id = ?", (match_id,))

            self._refresh_matches()

    def run(self):
        """Run the UI."""
        self.root.mainloop()


if __name__ == "__main__":
    app = OddsManagerUI()
    app.run()
