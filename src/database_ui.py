"""
Database Management UI - Manage player IDs, aliases, and duplicates.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from database import db
from config import UI_COLORS


class DatabaseUI:
    """UI for managing database: player aliases, duplicates, etc."""

    def __init__(self, parent: tk.Tk = None):
        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()

        self.root.title("Database Management")
        self.root.configure(bg=UI_COLORS["bg_dark"])
        self.root.state('zoomed')  # Launch maximized

        self._setup_styles()
        self._build_ui()

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

        style.configure("Treeview",
                       background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["text_primary"],
                       fieldbackground=UI_COLORS["bg_medium"],
                       font=("Segoe UI", 10))
        style.configure("Treeview.Heading",
                       background=UI_COLORS["bg_light"],
                       foreground=UI_COLORS["text_primary"],
                       font=("Segoe UI", 10, "bold"))

    def _build_ui(self):
        """Build the main UI."""
        main_frame = ttk.Frame(self.root, style="Dark.TFrame", padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        header_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(header_frame, text="Database Management", style="Title.TLabel").pack(side=tk.LEFT)

        # Action buttons
        btn_frame = ttk.Frame(header_frame, style="Dark.TFrame")
        btn_frame.pack(side=tk.RIGHT)

        cleanup_btn = tk.Button(
            btn_frame,
            text="Find Duplicates",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["warning"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._find_duplicates,
            padx=15,
            pady=5
        )
        cleanup_btn.pack(side=tk.LEFT, padx=5)

        similar_btn = tk.Button(
            btn_frame,
            text="Find Similar Names",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["accent"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._find_similar_names,
            padx=15,
            pady=5
        )
        similar_btn.pack(side=tk.LEFT, padx=5)

        # Main content - two panels
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left panel: Player search
        left_frame = ttk.Frame(paned, style="Dark.TFrame")
        paned.add(left_frame, weight=1)

        # Search section
        search_frame = ttk.Frame(left_frame, style="Dark.TFrame")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text="Search Players:", style="Dark.TLabel").pack(side=tk.LEFT)

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=("Segoe UI", 11),
            bg=UI_COLORS["bg_medium"],
            fg=UI_COLORS["text_primary"],
            insertbackground=UI_COLORS["text_primary"],
            width=30
        )
        self.search_entry.pack(side=tk.LEFT, padx=(10, 5))
        self.search_entry.bind('<Return>', lambda e: self._search_players())

        search_btn = tk.Button(
            search_frame,
            text="Search",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["primary"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._search_players,
            padx=10,
            pady=3
        )
        search_btn.pack(side=tk.LEFT)

        # Players list
        ttk.Label(left_frame, text="Players", style="Dark.TLabel").pack(anchor=tk.W, pady=(10, 5))

        players_frame = ttk.Frame(left_frame, style="Card.TFrame")
        players_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("id", "name", "ranking", "matches")
        self.players_tree = ttk.Treeview(players_frame, columns=columns, show="headings", height=20)

        self.players_tree.heading("id", text="ID")
        self.players_tree.heading("name", text="Name")
        self.players_tree.heading("ranking", text="Ranking")
        self.players_tree.heading("matches", text="Matches")

        self.players_tree.column("id", width=80)
        self.players_tree.column("name", width=200)
        self.players_tree.column("ranking", width=70)
        self.players_tree.column("matches", width=70)

        players_scroll = ttk.Scrollbar(players_frame, orient=tk.VERTICAL, command=self.players_tree.yview)
        self.players_tree.configure(yscrollcommand=players_scroll.set)

        self.players_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        players_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.players_tree.bind('<<TreeviewSelect>>', self._on_player_select)

        # Right panel: Player details and aliases
        right_frame = ttk.Frame(paned, style="Dark.TFrame")
        paned.add(right_frame, weight=1)

        # Player details
        ttk.Label(right_frame, text="Player Details", style="Dark.TLabel").pack(anchor=tk.W, pady=(0, 10))

        details_frame = ttk.Frame(right_frame, style="Card.TFrame")
        details_frame.pack(fill=tk.X, pady=(0, 15))

        details_inner = tk.Frame(details_frame, bg=UI_COLORS["bg_medium"], padx=15, pady=15)
        details_inner.pack(fill=tk.X)

        self.detail_labels = {}
        for field in ["ID", "Name", "Ranking", "Matches", "Canonical ID"]:
            row = tk.Frame(details_inner, bg=UI_COLORS["bg_medium"])
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=f"{field}:", bg=UI_COLORS["bg_medium"],
                    fg=UI_COLORS["text_secondary"], font=("Segoe UI", 10), width=12, anchor='w').pack(side=tk.LEFT)
            lbl = tk.Label(row, text="-", bg=UI_COLORS["bg_medium"],
                          fg=UI_COLORS["text_primary"], font=("Segoe UI", 10, "bold"))
            lbl.pack(side=tk.LEFT)
            self.detail_labels[field] = lbl

        # Aliases section
        ttk.Label(right_frame, text="Aliases (IDs that point to this player)", style="Dark.TLabel").pack(anchor=tk.W, pady=(10, 5))

        aliases_frame = ttk.Frame(right_frame, style="Card.TFrame")
        aliases_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        alias_columns = ("alias_id", "source")
        self.aliases_tree = ttk.Treeview(aliases_frame, columns=alias_columns, show="headings", height=8)

        self.aliases_tree.heading("alias_id", text="Alias ID")
        self.aliases_tree.heading("source", text="Source")

        self.aliases_tree.column("alias_id", width=100)
        self.aliases_tree.column("source", width=150)

        self.aliases_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Add alias section
        add_alias_frame = ttk.Frame(right_frame, style="Dark.TFrame")
        add_alias_frame.pack(fill=tk.X)

        ttk.Label(add_alias_frame, text="Add Alias:", style="Dark.TLabel").pack(side=tk.LEFT)

        self.alias_id_var = tk.StringVar()
        alias_entry = tk.Entry(
            add_alias_frame,
            textvariable=self.alias_id_var,
            font=("Segoe UI", 11),
            bg=UI_COLORS["bg_medium"],
            fg=UI_COLORS["text_primary"],
            insertbackground=UI_COLORS["text_primary"],
            width=15
        )
        alias_entry.pack(side=tk.LEFT, padx=(10, 5))

        tk.Label(add_alias_frame, text="(Enter ID to mark as duplicate)",
                bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_secondary"],
                font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 10))

        add_alias_btn = tk.Button(
            add_alias_frame,
            text="Add Alias",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["success"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._add_alias,
            padx=10,
            pady=3
        )
        add_alias_btn.pack(side=tk.LEFT)

        # Status bar
        self.status_var = tk.StringVar(value="Search for a player to view details")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, style="Dark.TLabel")
        status_label.pack(anchor=tk.W, pady=(10, 0))

        # Track selected player
        self.selected_player_id = None

    def _search_players(self):
        """Search for players by name."""
        query = self.search_var.get().strip()
        if not query:
            self.status_var.set("Enter a search term")
            return

        self.players_tree.delete(*self.players_tree.get_children())

        players = db.search_players(query, limit=100)

        for p in players:
            match_count = db.get_player_match_count(p['id'])
            ranking = p.get('current_ranking', '-') or '-'

            self.players_tree.insert('', tk.END, values=(
                p['id'],
                p['name'],
                ranking,
                match_count
            ))

        self.status_var.set(f"Found {len(players)} players matching '{query}'")

    def _on_player_select(self, event):
        """Handle player selection."""
        selection = self.players_tree.selection()
        if not selection:
            return

        item = self.players_tree.item(selection[0])
        values = item['values']
        player_id = values[0]

        self.selected_player_id = player_id
        self._show_player_details(player_id)

    def _show_player_details(self, player_id: int):
        """Show details for selected player."""
        player = db.get_player(player_id)
        if not player:
            self.status_var.set(f"Player {player_id} not found")
            return

        # Get canonical ID
        canonical_id = db.get_canonical_id(player_id)
        match_count = db.get_player_match_count(player_id)

        # Update detail labels
        self.detail_labels["ID"].configure(text=str(player_id))
        self.detail_labels["Name"].configure(text=player.get('name', '-'))
        self.detail_labels["Ranking"].configure(text=str(player.get('current_ranking', '-') or '-'))
        self.detail_labels["Matches"].configure(text=str(match_count))

        if canonical_id != player_id:
            self.detail_labels["Canonical ID"].configure(text=f"{canonical_id} (this is an alias)", fg=UI_COLORS["warning"])
        else:
            self.detail_labels["Canonical ID"].configure(text=f"{canonical_id} (canonical)", fg=UI_COLORS["success"])

        # Load aliases for this player
        self._load_aliases(player_id)

    def _load_aliases(self, canonical_id: int):
        """Load aliases that point to this player."""
        self.aliases_tree.delete(*self.aliases_tree.get_children())

        # Query aliases from database
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT alias_id, source FROM player_aliases
                    WHERE canonical_id = ?
                ''', (canonical_id,))
                aliases = cursor.fetchall()

                for alias in aliases:
                    self.aliases_tree.insert('', tk.END, values=(alias[0], alias[1] or 'manual'))

        except Exception as e:
            print(f"Error loading aliases: {e}")

    def _add_alias(self):
        """Add an alias for the selected player."""
        if not self.selected_player_id:
            messagebox.showwarning("No Player", "Please select a player first.")
            return

        alias_id_str = self.alias_id_var.get().strip()
        if not alias_id_str:
            messagebox.showwarning("No ID", "Please enter an alias ID.")
            return

        try:
            alias_id = int(alias_id_str)
        except ValueError:
            messagebox.showerror("Invalid ID", "Please enter a valid numeric ID.")
            return

        if alias_id == self.selected_player_id:
            messagebox.showwarning("Same ID", "Alias ID cannot be the same as the player ID.")
            return

        # Confirm the action
        alias_player = db.get_player(alias_id)
        canonical_player = db.get_player(self.selected_player_id)

        if not alias_player:
            messagebox.showerror("Not Found", f"Player with ID {alias_id} not found.")
            return

        result = messagebox.askyesno(
            "Confirm Alias",
            f"Mark '{alias_player.get('name', alias_id)}' (ID: {alias_id})\n"
            f"as duplicate of '{canonical_player.get('name', self.selected_player_id)}' (ID: {self.selected_player_id})?\n\n"
            f"All references to ID {alias_id} will resolve to ID {self.selected_player_id}."
        )

        if not result:
            return

        try:
            db.add_player_alias(
                alias_id=alias_id,
                canonical_id=self.selected_player_id,
                source='manual'
            )
            self.status_var.set(f"Added alias: {alias_id} -> {self.selected_player_id}")
            self.alias_id_var.set("")
            self._load_aliases(self.selected_player_id)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add alias: {e}")

    def _find_duplicates(self):
        """Find and show potential duplicate players."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Find Duplicates")
        dialog.geometry("700x500")
        dialog.configure(bg=UI_COLORS["bg_dark"])
        dialog.transient(self.root)
        dialog.grab_set()

        content = tk.Frame(dialog, bg=UI_COLORS["bg_dark"], padx=20, pady=20)
        content.pack(fill=tk.BOTH, expand=True)

        tk.Label(content, text="Potential Duplicate Players", font=("Segoe UI", 14, "bold"),
                bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_primary"]).pack(anchor=tk.W, pady=(0, 15))

        # Results tree
        columns = ("name", "count", "ids")
        tree = ttk.Treeview(content, columns=columns, show="headings", height=15)

        tree.heading("name", text="Player Name")
        tree.heading("count", text="Duplicates")
        tree.heading("ids", text="IDs")

        tree.column("name", width=250)
        tree.column("count", width=80)
        tree.column("ids", width=300)

        tree.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Find duplicates
        from collections import defaultdict

        all_players = db.get_all_players()
        name_groups = defaultdict(list)

        for p in all_players:
            normalized = p['name'].lower().replace('-', ' ').strip()
            name_groups[normalized].append(p)

        duplicates = {k: v for k, v in name_groups.items() if len(v) > 1}

        for name, players in sorted(duplicates.items()):
            ids = [str(p['id']) for p in players]
            tree.insert('', tk.END, values=(
                players[0]['name'],
                len(players),
                ', '.join(ids)
            ))

        # Summary
        tk.Label(content, text=f"Found {len(duplicates)} names with duplicates",
                bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_secondary"],
                font=("Segoe UI", 10)).pack(anchor=tk.W)

        # Buttons
        btn_frame = tk.Frame(content, bg=UI_COLORS["bg_dark"])
        btn_frame.pack(fill=tk.X, pady=(15, 0))

        def run_cleanup():
            from cleanup_duplicates import cleanup_duplicates
            result = cleanup_duplicates(dry_run=False)
            messagebox.showinfo("Cleanup Complete",
                              f"Created {result.get('aliases_created', 0)} aliases")
            dialog.destroy()

        tk.Button(
            btn_frame,
            text="Alias Duplicates",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["success"],
            relief=tk.FLAT,
            cursor="hand2",
            command=run_cleanup,
            padx=15,
            pady=5
        ).pack(side=tk.LEFT, padx=(0, 10))

        def run_delete():
            if messagebox.askyesno(
                "Delete All Duplicates",
                f"This will permanently DELETE {len(duplicates)} duplicate player groups.\n\n"
                "Only the player with a ranking will be kept.\n"
                "Matches will be reassigned.\n\n"
                "This cannot be undone. Continue?"
            ):
                from delete_duplicates import delete_all_duplicates
                result = delete_all_duplicates(dry_run=False)
                if result:
                    messagebox.showinfo(
                        "Duplicates Removed",
                        f"Deleted {result.get('players_deleted', 0)} duplicate players\n"
                        f"Updated {result.get('matches_updated', 0)} match references"
                    )
                dialog.destroy()

        tk.Button(
            btn_frame,
            text="Delete All Duplicates",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["danger"],
            relief=tk.FLAT,
            cursor="hand2",
            command=run_delete,
            padx=15,
            pady=5
        ).pack(side=tk.LEFT)

        tk.Button(
            btn_frame,
            text="Close",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["bg_light"],
            relief=tk.FLAT,
            cursor="hand2",
            command=dialog.destroy,
            padx=15,
            pady=5
        ).pack(side=tk.RIGHT)

    def _find_similar_names(self):
        """Find players with similar names (fuzzy matching) that might be duplicates."""
        from name_matcher import name_matcher

        dialog = tk.Toplevel(self.root)
        dialog.title("Find Similar Player Names")
        dialog.geometry("900x600")
        dialog.configure(bg=UI_COLORS["bg_dark"])
        dialog.transient(self.root)
        dialog.grab_set()

        content = tk.Frame(dialog, bg=UI_COLORS["bg_dark"], padx=20, pady=20)
        content.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = tk.Frame(content, bg=UI_COLORS["bg_dark"])
        header_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(header_frame, text="Similar Player Names (Potential Duplicates)",
                font=("Segoe UI", 14, "bold"),
                bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_primary"]).pack(side=tk.LEFT)

        # Threshold slider
        threshold_frame = tk.Frame(header_frame, bg=UI_COLORS["bg_dark"])
        threshold_frame.pack(side=tk.RIGHT)

        tk.Label(threshold_frame, text="Similarity threshold:",
                bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_secondary"],
                font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 5))

        threshold_var = tk.DoubleVar(value=0.75)
        threshold_label = tk.Label(threshold_frame, text="75%",
                                   bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_primary"],
                                   font=("Segoe UI", 9, "bold"), width=4)
        threshold_label.pack(side=tk.RIGHT)

        def update_threshold(val):
            threshold_label.config(text=f"{int(float(val)*100)}%")

        threshold_scale = tk.Scale(threshold_frame, from_=0.5, to=0.95,
                                   resolution=0.05, orient=tk.HORIZONTAL,
                                   variable=threshold_var, command=update_threshold,
                                   bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_primary"],
                                   highlightthickness=0, length=100)
        threshold_scale.pack(side=tk.LEFT, padx=5)

        # Status label
        status_label = tk.Label(content, text="Click 'Scan' to find similar names...",
                               bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_secondary"],
                               font=("Segoe UI", 10))
        status_label.pack(anchor=tk.W, pady=(0, 10))

        # Results tree
        columns = ("player1", "player2", "similarity", "p1_matches", "p2_matches", "p1_id", "p2_id")
        tree = ttk.Treeview(content, columns=columns, show="headings", height=18)

        tree.heading("player1", text="Player 1")
        tree.heading("player2", text="Player 2")
        tree.heading("similarity", text="Similarity")
        tree.heading("p1_matches", text="P1 Matches")
        tree.heading("p2_matches", text="P2 Matches")
        tree.heading("p1_id", text="P1 ID")
        tree.heading("p2_id", text="P2 ID")

        tree.column("player1", width=200)
        tree.column("player2", width=200)
        tree.column("similarity", width=80)
        tree.column("p1_matches", width=80)
        tree.column("p2_matches", width=80)
        tree.column("p1_id", width=70)
        tree.column("p2_id", width=70)

        tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Store results for actions
        similar_pairs = []

        def scan_similar():
            """Scan database for similar names."""
            status_label.config(text="Scanning... this may take a moment...")
            dialog.update()

            # Clear tree
            for item in tree.get_children():
                tree.delete(item)
            similar_pairs.clear()

            threshold = threshold_var.get()
            all_players = db.get_all_players()

            # Compare all pairs (O(n^2) but usually manageable)
            compared = set()
            found = 0

            for i, p1 in enumerate(all_players):
                for p2 in all_players[i+1:]:
                    # Skip if already compared
                    pair_key = (min(p1['id'], p2['id']), max(p1['id'], p2['id']))
                    if pair_key in compared:
                        continue
                    compared.add(pair_key)

                    # Calculate similarity
                    similarity = name_matcher.similarity_score(p1['name'], p2['name'])

                    if similarity >= threshold:
                        p1_matches = db.get_player_match_count(p1['id'])
                        p2_matches = db.get_player_match_count(p2['id'])

                        similar_pairs.append({
                            'p1': p1, 'p2': p2,
                            'similarity': similarity,
                            'p1_matches': p1_matches,
                            'p2_matches': p2_matches
                        })
                        found += 1

                # Progress update every 100 players
                if i % 100 == 0:
                    status_label.config(text=f"Scanning... {i}/{len(all_players)} players checked, {found} similar pairs found")
                    dialog.update()

            # Sort by similarity descending
            similar_pairs.sort(key=lambda x: x['similarity'], reverse=True)

            # Populate tree
            for pair in similar_pairs:
                tree.insert('', tk.END, values=(
                    pair['p1']['name'],
                    pair['p2']['name'],
                    f"{pair['similarity']:.0%}",
                    pair['p1_matches'],
                    pair['p2_matches'],
                    pair['p1']['id'],
                    pair['p2']['id']
                ))

            status_label.config(text=f"Found {len(similar_pairs)} pairs with similarity >= {threshold:.0%}")

        def merge_selected():
            """Merge selected pair - keep the one with more matches."""
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a pair to merge.")
                return

            item = selection[0]
            values = tree.item(item, 'values')
            p1_name, p2_name = values[0], values[1]
            p1_matches, p2_matches = int(values[3]), int(values[4])
            p1_id, p2_id = int(values[5]), int(values[6])

            # Keep the one with more matches
            if p1_matches >= p2_matches:
                keep_id, keep_name = p1_id, p1_name
                remove_id, remove_name = p2_id, p2_name
            else:
                keep_id, keep_name = p2_id, p2_name
                remove_id, remove_name = p1_id, p1_name

            if messagebox.askyesno(
                "Merge Players",
                f"Merge '{remove_name}' (ID: {remove_id}) into '{keep_name}' (ID: {keep_id})?\n\n"
                f"This will:\n"
                f"- Add '{remove_name}' as an alias of '{keep_name}'\n"
                f"- Save mapping: '{remove_name}' -> {keep_id}\n\n"
                f"Continue?"
            ):
                # Add alias
                db.add_player_alias(remove_id, keep_id, source="similar_names_merge")

                # Save name mapping
                name_matcher.add_mapping(remove_name, keep_id)

                messagebox.showinfo("Merged",
                    f"'{remove_name}' is now an alias of '{keep_name}'.\n"
                    f"Name mapping saved.")

                # Remove from tree
                tree.delete(item)

        def add_mapping_selected():
            """Just add a name mapping without merging."""
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a pair.")
                return

            item = selection[0]
            values = tree.item(item, 'values')
            p1_name, p2_name = values[0], values[1]
            p1_matches, p2_matches = int(values[3]), int(values[4])
            p1_id, p2_id = int(values[5]), int(values[6])

            # Keep the one with more matches as canonical
            if p1_matches >= p2_matches:
                canonical_id, canonical_name = p1_id, p1_name
                alias_name = p2_name
            else:
                canonical_id, canonical_name = p2_id, p2_name
                alias_name = p1_name

            # Save name mapping only
            name_matcher.add_mapping(alias_name, canonical_id)

            messagebox.showinfo("Mapping Saved",
                f"Name mapping saved:\n'{alias_name}' -> {canonical_id} ({canonical_name})")

            tree.delete(item)

        # Buttons
        btn_frame = tk.Frame(content, bg=UI_COLORS["bg_dark"])
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Button(
            btn_frame,
            text="Scan",
            font=("Segoe UI", 10, "bold"),
            fg="white",
            bg=UI_COLORS["primary"],
            relief=tk.FLAT,
            cursor="hand2",
            command=scan_similar,
            padx=20,
            pady=5
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            btn_frame,
            text="Merge Selected",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["success"],
            relief=tk.FLAT,
            cursor="hand2",
            command=merge_selected,
            padx=15,
            pady=5
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            btn_frame,
            text="Add Mapping Only",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["warning"],
            relief=tk.FLAT,
            cursor="hand2",
            command=add_mapping_selected,
            padx=15,
            pady=5
        ).pack(side=tk.LEFT)

        tk.Button(
            btn_frame,
            text="Close",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["bg_light"],
            relief=tk.FLAT,
            cursor="hand2",
            command=dialog.destroy,
            padx=15,
            pady=5
        ).pack(side=tk.RIGHT)


if __name__ == "__main__":
    app = DatabaseUI()
    app.root.mainloop()
