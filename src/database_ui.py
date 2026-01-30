"""
Database Management UI - Manage player IDs, aliases, and duplicates.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from database import db
from config import UI_COLORS
from match_analyzer import MatchAnalyzer


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

        sync_btn = tk.Button(
            btn_frame,
            text="Sync Tournament Names",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["primary"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._sync_tournament_names,
            padx=15,
            pady=5
        )
        sync_btn.pack(side=tk.LEFT, padx=5)

        check_btn = tk.Button(
            btn_frame,
            text="Check Player Data",
            font=("Segoe UI", 10),
            fg="white",
            bg="#e67e22",  # Orange
            relief=tk.FLAT,
            cursor="hand2",
            command=self._check_player_data,
            padx=15,
            pady=5
        )
        check_btn.pack(side=tk.LEFT, padx=5)

        # Main content - Notebook with tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Configure notebook style - ensure tabs stay same size when selected
        style = ttk.Style()
        style.configure("TNotebook", background=UI_COLORS["bg_dark"])
        style.configure("TNotebook.Tab", background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["text_primary"], padding=[20, 8],
                       font=("Segoe UI", 11))
        style.map("TNotebook.Tab",
                 background=[("selected", UI_COLORS["bg_light"]), ("!selected", UI_COLORS["bg_medium"])],
                 foreground=[("selected", UI_COLORS["text_primary"]), ("!selected", UI_COLORS["text_secondary"])],
                 padding=[("selected", [20, 8]), ("!selected", [20, 8])],
                 expand=[("selected", [0, 0, 0, 0])])

        # ===== PLAYERS TAB =====
        players_tab = ttk.Frame(self.notebook, style="Dark.TFrame")
        self.notebook.add(players_tab, text="Players")

        # Players tab uses paned layout
        paned = ttk.PanedWindow(players_tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

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

        show_all_players_btn = tk.Button(
            search_frame,
            text="Show All",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["accent"],
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._search_players(show_all=True),
            padx=10,
            pady=3
        )
        show_all_players_btn.pack(side=tk.LEFT, padx=(5, 0))

        # Players list
        ttk.Label(left_frame, text="Players", style="Dark.TLabel").pack(anchor=tk.W, pady=(10, 5))

        players_frame = ttk.Frame(left_frame, style="Card.TFrame")
        players_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("id", "name", "ranking", "matches")
        self.players_tree = ttk.Treeview(players_frame, columns=columns, show="headings", height=25)

        # Initialize sort tracking for players
        self.player_sort_reverse = {"id": False, "name": False, "ranking": False, "matches": False}

        # Sortable column headings
        self.players_tree.heading("id", text="ID", command=lambda: self._sort_player_column("id", self.player_sort_reverse["id"]))
        self.players_tree.heading("name", text="Name", command=lambda: self._sort_player_column("name", self.player_sort_reverse["name"]))
        self.players_tree.heading("ranking", text="Ranking", command=lambda: self._sort_player_column("ranking", self.player_sort_reverse["ranking"]))
        self.players_tree.heading("matches", text="Matches", command=lambda: self._sort_player_column("matches", self.player_sort_reverse["matches"]))

        self.players_tree.column("id", width=80)
        self.players_tree.column("name", width=200)
        self.players_tree.column("ranking", width=70)
        self.players_tree.column("matches", width=70)

        players_scroll = ttk.Scrollbar(players_frame, orient=tk.VERTICAL, command=self.players_tree.yview)
        self.players_tree.configure(yscrollcommand=players_scroll.set)

        self.players_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        players_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.players_tree.bind('<<TreeviewSelect>>', self._on_player_select)

        # Right panel: Player profile (scrollable)
        right_frame = ttk.Frame(paned, style="Dark.TFrame")
        paned.add(right_frame, weight=2)  # Give more weight to profile panel

        # Create canvas for scrolling
        canvas = tk.Canvas(right_frame, bg=UI_COLORS["bg_dark"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=canvas.yview)
        self.profile_frame = tk.Frame(canvas, bg=UI_COLORS["bg_dark"])

        self.profile_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.profile_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Player Profile Header
        ttk.Label(self.profile_frame, text="Player Profile", style="Title.TLabel").pack(anchor=tk.W, pady=(0, 10))

        # Basic Info Section (compact)
        basic_frame = ttk.Frame(self.profile_frame, style="Card.TFrame")
        basic_frame.pack(fill=tk.X, pady=(0, 10))

        basic_inner = tk.Frame(basic_frame, bg=UI_COLORS["bg_medium"], padx=15, pady=10)
        basic_inner.pack(fill=tk.X)

        self.detail_labels = {}
        self.current_player_id = None  # Track current player for editing

        # Row 1: ID, Name, Edit button
        row1 = tk.Frame(basic_inner, bg=UI_COLORS["bg_medium"])
        row1.pack(fill=tk.X, pady=2)

        for field in ["ID", "Name"]:
            tk.Label(row1, text=f"{field}:", bg=UI_COLORS["bg_medium"],
                    fg=UI_COLORS["text_secondary"], font=("Segoe UI", 9)).pack(side=tk.LEFT)
            lbl = tk.Label(row1, text="-", bg=UI_COLORS["bg_medium"],
                          fg=UI_COLORS["text_primary"], font=("Segoe UI", 9, "bold"))
            lbl.pack(side=tk.LEFT, padx=(2, 15))
            self.detail_labels[field] = lbl

        # Edit button
        self.player_edit_btn = tk.Button(row1, text="Edit", font=("Segoe UI", 8),
                                         fg="white", bg=UI_COLORS["primary"],
                                         relief=tk.FLAT, cursor="hand2",
                                         command=self._edit_player, padx=8, pady=2)
        self.player_edit_btn.pack(side=tk.LEFT, padx=(10, 0))
        self.current_te_url = None  # Store current player's TE URL

        # Row 1b: Tennis Explorer URL (clickable link)
        row1b = tk.Frame(basic_inner, bg=UI_COLORS["bg_medium"])
        row1b.pack(fill=tk.X, pady=2)

        tk.Label(row1b, text="TE URL:", bg=UI_COLORS["bg_medium"],
                fg=UI_COLORS["text_secondary"], font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.te_url_label = tk.Label(row1b, text="-", bg=UI_COLORS["bg_medium"],
                                     fg="#3498db", font=("Segoe UI", 9, "underline"),
                                     cursor="hand2")
        self.te_url_label.pack(side=tk.LEFT, padx=(2, 0))
        self.te_url_label.bind("<Button-1>", lambda e: self._open_tennis_explorer())

        # Row 2: Ranking, ELO, Total Matches
        row2 = tk.Frame(basic_inner, bg=UI_COLORS["bg_medium"])
        row2.pack(fill=tk.X, pady=2)

        for field in ["Ranking", "ELO", "Matches"]:
            tk.Label(row2, text=f"{field}:", bg=UI_COLORS["bg_medium"],
                    fg=UI_COLORS["text_secondary"], font=("Segoe UI", 9)).pack(side=tk.LEFT)
            lbl = tk.Label(row2, text="-", bg=UI_COLORS["bg_medium"],
                          fg=UI_COLORS["text_primary"], font=("Segoe UI", 9, "bold"))
            lbl.pack(side=tk.LEFT, padx=(2, 15))
            self.detail_labels[field] = lbl

        # Surface Performance Section
        surface_header = tk.Frame(self.profile_frame, bg=UI_COLORS["bg_dark"])
        surface_header.pack(fill=tk.X, pady=(10, 5))
        ttk.Label(surface_header, text="Surface Performance", style="Dark.TLabel").pack(side=tk.LEFT)

        surface_frame = ttk.Frame(self.profile_frame, style="Card.TFrame")
        surface_frame.pack(fill=tk.X, pady=(0, 10))

        surface_inner = tk.Frame(surface_frame, bg=UI_COLORS["bg_medium"], padx=15, pady=10)
        surface_inner.pack(fill=tk.X)

        # Surface stats labels
        self.surface_labels = {}
        for surface in ["Hard", "Clay", "Grass"]:
            row = tk.Frame(surface_inner, bg=UI_COLORS["bg_medium"])
            row.pack(fill=tk.X, pady=1)

            tk.Label(row, text=f"{surface}:", bg=UI_COLORS["bg_medium"],
                    fg=UI_COLORS["text_secondary"], font=("Segoe UI", 9), width=6, anchor='w').pack(side=tk.LEFT)

            lbl = tk.Label(row, text="-", bg=UI_COLORS["bg_medium"],
                          fg=UI_COLORS["text_primary"], font=("Consolas", 9))
            lbl.pack(side=tk.LEFT)
            self.surface_labels[surface] = lbl

        # Current Status Section (Fatigue, Days Rest)
        status_header = tk.Frame(self.profile_frame, bg=UI_COLORS["bg_dark"])
        status_header.pack(fill=tk.X, pady=(10, 5))
        ttk.Label(status_header, text="Current Status", style="Dark.TLabel").pack(side=tk.LEFT)

        status_frame = ttk.Frame(self.profile_frame, style="Card.TFrame")
        status_frame.pack(fill=tk.X, pady=(0, 10))

        status_inner = tk.Frame(status_frame, bg=UI_COLORS["bg_medium"], padx=15, pady=10)
        status_inner.pack(fill=tk.X)

        self.status_labels = {}
        for field in ["Days Since Match", "Fatigue", "Matches (7d)", "Matches (30d)"]:
            row = tk.Frame(status_inner, bg=UI_COLORS["bg_medium"])
            row.pack(fill=tk.X, pady=1)

            tk.Label(row, text=f"{field}:", bg=UI_COLORS["bg_medium"],
                    fg=UI_COLORS["text_secondary"], font=("Segoe UI", 9), width=16, anchor='w').pack(side=tk.LEFT)

            lbl = tk.Label(row, text="-", bg=UI_COLORS["bg_medium"],
                          fg=UI_COLORS["text_primary"], font=("Segoe UI", 9, "bold"))
            lbl.pack(side=tk.LEFT)
            self.status_labels[field] = lbl

        # Notable Opponents Section
        opponents_header = tk.Frame(self.profile_frame, bg=UI_COLORS["bg_dark"])
        opponents_header.pack(fill=tk.X, pady=(10, 5))
        ttk.Label(opponents_header, text="Notable Results", style="Dark.TLabel").pack(side=tk.LEFT)

        opponents_frame = ttk.Frame(self.profile_frame, style="Card.TFrame")
        opponents_frame.pack(fill=tk.X, pady=(0, 10))

        opponents_inner = tk.Frame(opponents_frame, bg=UI_COLORS["bg_medium"], padx=15, pady=10)
        opponents_inner.pack(fill=tk.X)

        self.opponent_labels = {}
        for field in ["Best Win", "Worst Loss"]:
            row = tk.Frame(opponents_inner, bg=UI_COLORS["bg_medium"])
            row.pack(fill=tk.X, pady=2)

            tk.Label(row, text=f"{field}:", bg=UI_COLORS["bg_medium"],
                    fg=UI_COLORS["text_secondary"], font=("Segoe UI", 9), width=12, anchor='w').pack(side=tk.LEFT)

            lbl = tk.Label(row, text="-", bg=UI_COLORS["bg_medium"],
                          fg=UI_COLORS["text_primary"], font=("Segoe UI", 9))
            lbl.pack(side=tk.LEFT)
            self.opponent_labels[field] = lbl

        # Recent Matches Section
        matches_header = tk.Frame(self.profile_frame, bg=UI_COLORS["bg_dark"])
        matches_header.pack(fill=tk.X, pady=(10, 5))
        ttk.Label(matches_header, text="Recent Matches (Last 10)", style="Dark.TLabel").pack(side=tk.LEFT)

        self.form_label = tk.Label(matches_header, text="", bg=UI_COLORS["bg_dark"],
                                   fg=UI_COLORS["text_primary"], font=("Segoe UI", 9, "bold"))
        self.form_label.pack(side=tk.RIGHT)

        matches_frame = ttk.Frame(self.profile_frame, style="Card.TFrame")
        matches_frame.pack(fill=tk.X, pady=(0, 10))

        # Recent matches display (text widget for formatting)
        self.matches_text = tk.Text(matches_frame, bg=UI_COLORS["bg_medium"],
                                    fg=UI_COLORS["text_primary"], font=("Consolas", 9),
                                    height=12, wrap=tk.NONE, state=tk.DISABLED,
                                    padx=10, pady=10, relief=tk.FLAT)
        self.matches_text.pack(fill=tk.X, padx=5, pady=5)

        # Configure tags for coloring
        self.matches_text.tag_configure("win", foreground="#2ecc71")
        self.matches_text.tag_configure("loss", foreground="#e74c3c")
        self.matches_text.tag_configure("header", foreground=UI_COLORS["text_secondary"])

        # Aliases Section (compact, at bottom)
        aliases_header = tk.Frame(self.profile_frame, bg=UI_COLORS["bg_dark"])
        aliases_header.pack(fill=tk.X, pady=(10, 5))
        ttk.Label(aliases_header, text="Aliases", style="Dark.TLabel").pack(side=tk.LEFT)

        self.alias_count_label = tk.Label(aliases_header, text="", bg=UI_COLORS["bg_dark"],
                                          fg=UI_COLORS["text_secondary"], font=("Segoe UI", 9))
        self.alias_count_label.pack(side=tk.RIGHT)

        aliases_frame = ttk.Frame(self.profile_frame, style="Card.TFrame")
        aliases_frame.pack(fill=tk.X, pady=(0, 10))

        alias_columns = ("alias_id", "source")
        self.aliases_tree = ttk.Treeview(aliases_frame, columns=alias_columns, show="headings", height=3)

        self.aliases_tree.heading("alias_id", text="Alias ID")
        self.aliases_tree.heading("source", text="Source")

        self.aliases_tree.column("alias_id", width=80)
        self.aliases_tree.column("source", width=120)

        self.aliases_tree.pack(fill=tk.X, padx=5, pady=5)

        # Add alias section (compact)
        add_alias_frame = tk.Frame(self.profile_frame, bg=UI_COLORS["bg_dark"])
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

        # ===== TOURNAMENTS TAB =====
        self._build_tournaments_tab()

        # Status bar
        self.status_var = tk.StringVar(value="Search for a player or tournament to view details")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, style="Dark.TLabel")
        status_label.pack(anchor=tk.W, pady=(10, 0))

        # Track selected player
        self.selected_player_id = None
        self.selected_tournament = None

    def _build_tournaments_tab(self):
        """Build the Tournaments tab UI."""
        tournaments_tab = ttk.Frame(self.notebook, style="Dark.TFrame")
        self.notebook.add(tournaments_tab, text="Tournaments")

        # Tournaments tab uses paned layout
        t_paned = ttk.PanedWindow(tournaments_tab, orient=tk.HORIZONTAL)
        t_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel: Tournament search
        t_left_frame = ttk.Frame(t_paned, style="Dark.TFrame")
        t_paned.add(t_left_frame, weight=1)

        # Search section
        t_search_frame = ttk.Frame(t_left_frame, style="Dark.TFrame")
        t_search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(t_search_frame, text="Search Tournaments:", style="Dark.TLabel").pack(side=tk.LEFT)

        self.tournament_search_var = tk.StringVar()
        t_search_entry = tk.Entry(
            t_search_frame,
            textvariable=self.tournament_search_var,
            font=("Segoe UI", 11),
            bg=UI_COLORS["bg_medium"],
            fg=UI_COLORS["text_primary"],
            insertbackground=UI_COLORS["text_primary"],
            width=25
        )
        t_search_entry.pack(side=tk.LEFT, padx=(10, 5))
        t_search_entry.bind('<Return>', lambda e: self._search_tournaments())

        t_search_btn = tk.Button(
            t_search_frame,
            text="Search",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["primary"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._search_tournaments,
            padx=10,
            pady=3
        )
        t_search_btn.pack(side=tk.LEFT)

        # Show All button
        t_all_btn = tk.Button(
            t_search_frame,
            text="Show All",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["bg_light"],
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._search_tournaments(show_all=True),
            padx=10,
            pady=3
        )
        t_all_btn.pack(side=tk.LEFT, padx=(5, 0))

        # Tournaments list
        ttk.Label(t_left_frame, text="Tournaments", style="Dark.TLabel").pack(anchor=tk.W, pady=(10, 5))

        t_list_frame = ttk.Frame(t_left_frame, style="Card.TFrame")
        t_list_frame.pack(fill=tk.BOTH, expand=True)

        t_columns = ("name", "surface", "matches")
        self.tournaments_tree = ttk.Treeview(t_list_frame, columns=t_columns, show="headings", height=25)

        # Make columns sortable
        self.tournaments_tree.heading("name", text="Tournament", command=lambda: self._sort_tournament_column("name", False))
        self.tournaments_tree.heading("surface", text="Surface", command=lambda: self._sort_tournament_column("surface", False))
        self.tournaments_tree.heading("matches", text="Matches", command=lambda: self._sort_tournament_column("matches", False))

        self.tournaments_tree.column("name", width=220)
        self.tournaments_tree.column("surface", width=70)
        self.tournaments_tree.column("matches", width=70)

        t_scroll = ttk.Scrollbar(t_list_frame, orient=tk.VERTICAL, command=self.tournaments_tree.yview)
        self.tournaments_tree.configure(yscrollcommand=t_scroll.set)

        self.tournaments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        t_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tournaments_tree.bind('<<TreeviewSelect>>', self._on_tournament_select)

        # Track sort state
        self.tournament_sort_reverse = {"name": False, "surface": False, "matches": False}

        # Right panel: Tournament profile (scrollable)
        t_right_frame = ttk.Frame(t_paned, style="Dark.TFrame")
        t_paned.add(t_right_frame, weight=2)

        # Create canvas for scrolling
        t_canvas = tk.Canvas(t_right_frame, bg=UI_COLORS["bg_dark"], highlightthickness=0)
        t_scrollbar = ttk.Scrollbar(t_right_frame, orient="vertical", command=t_canvas.yview)
        self.tournament_profile_frame = tk.Frame(t_canvas, bg=UI_COLORS["bg_dark"])

        self.tournament_profile_frame.bind(
            "<Configure>",
            lambda e: t_canvas.configure(scrollregion=t_canvas.bbox("all"))
        )

        t_canvas.create_window((0, 0), window=self.tournament_profile_frame, anchor="nw")
        t_canvas.configure(yscrollcommand=t_scrollbar.set)

        t_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        t_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Tournament Profile Header
        ttk.Label(self.tournament_profile_frame, text="Tournament Profile", style="Title.TLabel").pack(anchor=tk.W, pady=(0, 10))

        # Basic Info Section
        t_basic_frame = ttk.Frame(self.tournament_profile_frame, style="Card.TFrame")
        t_basic_frame.pack(fill=tk.X, pady=(0, 10))

        t_basic_inner = tk.Frame(t_basic_frame, bg=UI_COLORS["bg_medium"], padx=15, pady=10)
        t_basic_inner.pack(fill=tk.X)

        self.tournament_labels = {}
        self.current_tournament_name = None  # Track current tournament for editing

        # Row 1: ID and Name with Edit button
        t_row1 = tk.Frame(t_basic_inner, bg=UI_COLORS["bg_medium"])
        t_row1.pack(fill=tk.X, pady=2)

        tk.Label(t_row1, text="ID:", bg=UI_COLORS["bg_medium"],
                fg=UI_COLORS["text_secondary"], font=("Segoe UI", 9)).pack(side=tk.LEFT)
        lbl_id = tk.Label(t_row1, text="-", bg=UI_COLORS["bg_medium"],
                         fg=UI_COLORS["text_primary"], font=("Segoe UI", 9, "bold"))
        lbl_id.pack(side=tk.LEFT, padx=(2, 15))
        self.tournament_labels["ID"] = lbl_id

        tk.Label(t_row1, text="Tournament:", bg=UI_COLORS["bg_medium"],
                fg=UI_COLORS["text_secondary"], font=("Segoe UI", 9)).pack(side=tk.LEFT)
        lbl = tk.Label(t_row1, text="-", bg=UI_COLORS["bg_medium"],
                      fg=UI_COLORS["text_primary"], font=("Segoe UI", 11, "bold"))
        lbl.pack(side=tk.LEFT, padx=(5, 0))
        self.tournament_labels["Name"] = lbl

        # Edit button
        self.tournament_edit_btn = tk.Button(t_row1, text="Edit", font=("Segoe UI", 8),
                                             fg="white", bg=UI_COLORS["primary"],
                                             relief=tk.FLAT, cursor="hand2",
                                             command=self._edit_tournament, padx=8, pady=2)
        self.tournament_edit_btn.pack(side=tk.LEFT, padx=(10, 0))

        # Row 2: Surface, Category
        t_row2 = tk.Frame(t_basic_inner, bg=UI_COLORS["bg_medium"])
        t_row2.pack(fill=tk.X, pady=2)

        for field in ["Surface", "Category", "Month"]:
            tk.Label(t_row2, text=f"{field}:", bg=UI_COLORS["bg_medium"],
                    fg=UI_COLORS["text_secondary"], font=("Segoe UI", 9)).pack(side=tk.LEFT)
            lbl = tk.Label(t_row2, text="-", bg=UI_COLORS["bg_medium"],
                          fg=UI_COLORS["text_primary"], font=("Segoe UI", 9, "bold"))
            lbl.pack(side=tk.LEFT, padx=(2, 15))
            self.tournament_labels[field] = lbl

        # Statistics Section
        t_stats_header = tk.Frame(self.tournament_profile_frame, bg=UI_COLORS["bg_dark"])
        t_stats_header.pack(fill=tk.X, pady=(10, 5))
        ttk.Label(t_stats_header, text="Statistics", style="Dark.TLabel").pack(side=tk.LEFT)

        t_stats_frame = ttk.Frame(self.tournament_profile_frame, style="Card.TFrame")
        t_stats_frame.pack(fill=tk.X, pady=(0, 10))

        t_stats_inner = tk.Frame(t_stats_frame, bg=UI_COLORS["bg_medium"], padx=15, pady=10)
        t_stats_inner.pack(fill=tk.X)

        for field in ["Total Matches", "Date Range", "Unique Players"]:
            row = tk.Frame(t_stats_inner, bg=UI_COLORS["bg_medium"])
            row.pack(fill=tk.X, pady=1)

            tk.Label(row, text=f"{field}:", bg=UI_COLORS["bg_medium"],
                    fg=UI_COLORS["text_secondary"], font=("Segoe UI", 9), width=14, anchor='w').pack(side=tk.LEFT)

            lbl = tk.Label(row, text="-", bg=UI_COLORS["bg_medium"],
                          fg=UI_COLORS["text_primary"], font=("Segoe UI", 9, "bold"))
            lbl.pack(side=tk.LEFT)
            self.tournament_labels[field] = lbl

        # Top Performers Section
        t_top_header = tk.Frame(self.tournament_profile_frame, bg=UI_COLORS["bg_dark"])
        t_top_header.pack(fill=tk.X, pady=(10, 5))
        ttk.Label(t_top_header, text="Top Performers (Most Wins)", style="Dark.TLabel").pack(side=tk.LEFT)

        t_top_frame = ttk.Frame(self.tournament_profile_frame, style="Card.TFrame")
        t_top_frame.pack(fill=tk.X, pady=(0, 10))

        self.top_performers_text = tk.Text(t_top_frame, bg=UI_COLORS["bg_medium"],
                                          fg=UI_COLORS["text_primary"], font=("Consolas", 9),
                                          height=6, wrap=tk.NONE, state=tk.DISABLED,
                                          padx=10, pady=10, relief=tk.FLAT)
        self.top_performers_text.pack(fill=tk.X, padx=5, pady=5)

        # Recent Matches Section
        t_matches_header = tk.Frame(self.tournament_profile_frame, bg=UI_COLORS["bg_dark"])
        t_matches_header.pack(fill=tk.X, pady=(10, 5))
        ttk.Label(t_matches_header, text="Recent Matches (Last 15)", style="Dark.TLabel").pack(side=tk.LEFT)

        t_matches_frame = ttk.Frame(self.tournament_profile_frame, style="Card.TFrame")
        t_matches_frame.pack(fill=tk.X, pady=(0, 10))

        self.tournament_matches_text = tk.Text(t_matches_frame, bg=UI_COLORS["bg_medium"],
                                               fg=UI_COLORS["text_primary"], font=("Consolas", 9),
                                               height=18, wrap=tk.NONE, state=tk.DISABLED,
                                               padx=10, pady=10, relief=tk.FLAT)
        self.tournament_matches_text.pack(fill=tk.X, padx=5, pady=5)

        # Configure tags for coloring
        self.tournament_matches_text.tag_configure("hard", foreground="#3b82f6")  # Blue
        self.tournament_matches_text.tag_configure("clay", foreground="#f59e0b")  # Orange
        self.tournament_matches_text.tag_configure("grass", foreground="#22c55e")  # Green
        self.tournament_matches_text.tag_configure("header", foreground=UI_COLORS["text_secondary"])

    def _search_tournaments(self, show_all=False):
        """Search for tournaments by name."""
        query = self.tournament_search_var.get().strip()
        if not query and not show_all:
            self.status_var.set("Enter a tournament name to search")
            return

        self.tournaments_tree.delete(*self.tournaments_tree.get_children())

        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()

                if show_all:
                    cursor.execute('''
                        SELECT tournament, surface, COUNT(*) as match_count
                        FROM matches
                        GROUP BY tournament
                        ORDER BY tournament ASC
                    ''')
                else:
                    cursor.execute('''
                        SELECT tournament, surface, COUNT(*) as match_count
                        FROM matches
                        WHERE tournament LIKE ?
                        GROUP BY tournament
                        ORDER BY tournament ASC
                    ''', (f'%{query}%',))

                tournaments = cursor.fetchall()

                for t in tournaments:
                    self.tournaments_tree.insert('', tk.END, values=(
                        t[0],  # name
                        t[1],  # surface
                        t[2]   # match count
                    ))

                if show_all:
                    self.status_var.set(f"Showing {len(tournaments)} tournaments (sorted A-Z)")
                    # Auto-sort alphabetically by tournament name
                    self._sort_tournament_column("name", False)
                else:
                    self.status_var.set(f"Found {len(tournaments)} tournaments matching '{query}'")

        except Exception as e:
            self.status_var.set(f"Error searching tournaments: {e}")

    def _on_tournament_select(self, event):
        """Handle tournament selection."""
        selection = self.tournaments_tree.selection()
        if not selection:
            return

        item = self.tournaments_tree.item(selection[0])
        values = item['values']
        tournament_name = values[0]

        self.selected_tournament = tournament_name
        self._show_tournament_details(tournament_name)

    def _sort_player_column(self, col, reverse):
        """Sort players treeview by column."""
        items = [(self.players_tree.set(k, col), k) for k in self.players_tree.get_children('')]

        # Sort - numeric for id, ranking, matches; alphabetic for name
        if col in ["id", "ranking", "matches"]:
            def sort_key(t):
                val = t[0]
                if val == '-' or val == '':
                    return 999999 if not reverse else -1  # Put empty/dash at end
                try:
                    return int(val)
                except:
                    return 999999
            items.sort(key=sort_key, reverse=reverse)
        else:
            items.sort(key=lambda t: t[0].lower() if t[0] else 'zzz', reverse=reverse)

        # Rearrange items
        for index, (val, k) in enumerate(items):
            self.players_tree.move(k, '', index)

        # Toggle sort direction for next click
        self.player_sort_reverse[col] = not reverse
        self.players_tree.heading(col, command=lambda: self._sort_player_column(col, self.player_sort_reverse[col]))

    def _sort_tournament_column(self, col, reverse):
        """Sort tournaments treeview by column."""
        # Get all items
        items = [(self.tournaments_tree.set(k, col), k) for k in self.tournaments_tree.get_children('')]

        # Sort - numeric for matches, alphabetic for others
        if col == "matches":
            items.sort(key=lambda t: int(t[0]) if t[0].isdigit() else 0, reverse=reverse)
        else:
            items.sort(key=lambda t: t[0].lower(), reverse=reverse)

        # Rearrange items
        for index, (val, k) in enumerate(items):
            self.tournaments_tree.move(k, '', index)

        # Toggle sort direction for next click
        self.tournament_sort_reverse[col] = not reverse
        self.tournaments_tree.heading(col, command=lambda: self._sort_tournament_column(col, self.tournament_sort_reverse[col]))

    def _show_tournament_details(self, tournament_name: str):
        """Show full tournament profile for selected tournament."""
        self.current_tournament_name = tournament_name  # Store for editing
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()

                # Get tournament ID from tournaments table
                cursor.execute('SELECT id, level FROM tournaments WHERE name = ?', (tournament_name,))
                tournament_row = cursor.fetchone()
                tournament_id = tournament_row[0] if tournament_row else "N/A"
                stored_level = tournament_row[1] if tournament_row else None

                # Get basic stats
                cursor.execute('''
                    SELECT
                        surface,
                        COUNT(*) as total_matches,
                        MIN(date) as first_match,
                        MAX(date) as last_match,
                        COUNT(DISTINCT winner_id) + COUNT(DISTINCT loser_id) as player_count
                    FROM matches
                    WHERE tournament = ?
                ''', (tournament_name,))
                stats = cursor.fetchone()

                if not stats:
                    self.status_var.set(f"No data found for {tournament_name}")
                    return

                surface = stats[0] or "Unknown"
                total_matches = stats[1]
                first_match = stats[2]
                last_match = stats[3]

                # Use stored category if available, otherwise determine from name
                category = stored_level if stored_level else self._determine_category(tournament_name)

                # Determine typical month
                cursor.execute('''
                    SELECT strftime('%m', date) as month, COUNT(*) as cnt
                    FROM matches
                    WHERE tournament = ?
                    GROUP BY month
                    ORDER BY cnt DESC
                    LIMIT 1
                ''', (tournament_name,))
                month_result = cursor.fetchone()
                month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                              'July', 'August', 'September', 'October', 'November', 'December']
                typical_month = month_names[int(month_result[0])] if month_result else "Various"

                # Get unique players count
                cursor.execute('''
                    SELECT COUNT(DISTINCT player_id) FROM (
                        SELECT winner_id as player_id FROM matches WHERE tournament = ?
                        UNION
                        SELECT loser_id as player_id FROM matches WHERE tournament = ?
                    )
                ''', (tournament_name, tournament_name))
                unique_players = cursor.fetchone()[0]

                # Update basic info labels
                self.tournament_labels["ID"].configure(text=str(tournament_id))
                self.tournament_labels["Name"].configure(text=tournament_name)

                # Surface with color
                surface_colors = {"Hard": "#3b82f6", "Clay": "#f59e0b", "Grass": "#22c55e"}
                surface_color = surface_colors.get(surface, UI_COLORS["text_primary"])
                self.tournament_labels["Surface"].configure(text=surface, fg=surface_color)

                self.tournament_labels["Category"].configure(text=category)
                self.tournament_labels["Month"].configure(text=typical_month)

                # Update statistics
                self.tournament_labels["Total Matches"].configure(text=str(total_matches))
                self.tournament_labels["Date Range"].configure(text=f"{first_match} to {last_match}")
                self.tournament_labels["Unique Players"].configure(text=str(unique_players))

                # Get top performers (most wins)
                cursor.execute('''
                    SELECT winner_name, COUNT(*) as wins
                    FROM matches
                    WHERE tournament = ?
                    GROUP BY winner_id
                    ORDER BY wins DESC
                    LIMIT 5
                ''', (tournament_name,))
                top_performers = cursor.fetchall()

                self.top_performers_text.configure(state=tk.NORMAL)
                self.top_performers_text.delete(1.0, tk.END)

                for i, (name, wins) in enumerate(top_performers, 1):
                    line = f"{i}. {name[:30]:<30} {wins} wins\n"
                    self.top_performers_text.insert(tk.END, line)

                self.top_performers_text.configure(state=tk.DISABLED)

                # Get recent matches
                cursor.execute('''
                    SELECT date, winner_name, loser_name, score, surface
                    FROM matches
                    WHERE tournament = ?
                    ORDER BY date DESC
                    LIMIT 15
                ''', (tournament_name,))
                recent_matches = cursor.fetchall()

                self.tournament_matches_text.configure(state=tk.NORMAL)
                self.tournament_matches_text.delete(1.0, tk.END)

                for m in recent_matches:
                    date = m[0][:10] if m[0] else ""
                    winner = (m[1] or "Unknown")[:20]
                    loser = (m[2] or "Unknown")[:20]
                    score = (m[3] or "")[:15]
                    match_surface = m[4] or "Hard"

                    tag = match_surface.lower() if match_surface.lower() in ["hard", "clay", "grass"] else "hard"
                    line = f"{date} | {winner:<20} d. {loser:<20} {score}\n"
                    self.tournament_matches_text.insert(tk.END, line, tag)

                self.tournament_matches_text.configure(state=tk.DISABLED)

                self.status_var.set(f"Showing profile for {tournament_name}")

        except Exception as e:
            self.status_var.set(f"Error loading tournament: {e}")
            import traceback
            traceback.print_exc()

    def _determine_category(self, tournament_name: str) -> str:
        """Determine tournament category from name."""
        name_lower = tournament_name.lower()

        if any(gs in name_lower for gs in ['australian open', 'french open', 'wimbledon', 'us open']):
            return "Grand Slam"
        elif 'masters' in name_lower or name_lower in ['indian wells', 'miami', 'monte carlo', 'madrid', 'rome', 'canada', 'cincinnati', 'shanghai', 'paris']:
            return "Masters 1000"
        elif 'wta' in name_lower:
            return "WTA"
        elif 'challenger' in name_lower:
            return "Challenger"
        elif 'itf' in name_lower or 'futures' in name_lower:
            return "ITF"
        elif 'davis cup' in name_lower:
            return "Davis Cup"
        elif 'billie jean king' in name_lower or 'fed cup' in name_lower:
            return "BJK Cup"
        else:
            return "ATP"

    def _search_players(self, show_all=False):
        """Search for players by name or show all."""
        query = self.search_var.get().strip()
        if not query and not show_all:
            self.status_var.set("Enter a search term")
            return

        self.players_tree.delete(*self.players_tree.get_children())

        if show_all:
            # Get all players with match count
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT p.id, p.name, p.current_ranking,
                           (SELECT COUNT(*) FROM matches WHERE winner_id = p.id OR loser_id = p.id) as match_count
                    FROM players p
                    ORDER BY p.name ASC
                ''')
                players = [{'id': r[0], 'name': r[1], 'current_ranking': r[2], 'match_count': r[3]}
                          for r in cursor.fetchall()]

            for p in players:
                ranking = p.get('current_ranking', '-') or '-'
                self.players_tree.insert('', tk.END, values=(
                    p['id'],
                    p['name'],
                    ranking,
                    p['match_count']
                ))

            self.status_var.set(f"Showing {len(players)} players (sorted A-Z)")
            # Auto-sort alphabetically
            self._sort_player_column("name", False)
        else:
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
        """Show full player profile for selected player."""
        self.current_player_id = player_id  # Store for editing

        player = db.get_player(player_id)
        if not player:
            self.status_var.set(f"Player {player_id} not found")
            return

        # Initialize analyzer
        analyzer = MatchAnalyzer(db)

        # Get canonical ID and match count
        canonical_id = db.get_canonical_id(player_id)
        match_count = db.get_player_match_count(player_id)

        # Update basic info
        self.detail_labels["ID"].configure(text=str(player_id))
        self.detail_labels["Name"].configure(text=player.get('name', '-'))

        # Store and display Tennis Explorer URL
        self.current_te_url = player.get('tennis_explorer_url')
        if self.current_te_url:
            self.te_url_label.configure(text=self.current_te_url)
        else:
            self.te_url_label.configure(text="Not available")

        ranking = player.get('current_ranking') or player.get('ranking')
        self.detail_labels["Ranking"].configure(text=f"#{ranking}" if ranking else "Unranked")
        self.detail_labels["Matches"].configure(text=str(match_count))

        # Calculate ELO from ranking
        try:
            if ranking:
                elo = analyzer._ranking_to_elo(int(ranking))
                self.detail_labels["ELO"].configure(text=f"{elo:.0f}")
            else:
                self.detail_labels["ELO"].configure(text="-")
        except:
            self.detail_labels["ELO"].configure(text="-")

        # Update surface performance
        for surface in ["Hard", "Clay", "Grass"]:
            stats = analyzer.get_surface_stats(player_id, surface)
            # Use career_matches if available, otherwise use recent_matches
            matches = stats.get('career_matches', 0) or stats.get('recent_matches', 0)
            if matches > 0:
                # Use combined_win_rate which blends career and recent
                win_rate = stats.get('combined_win_rate', stats.get('career_win_rate', 0.5))
                has_data = "✓" if stats['has_data'] else "✗"

                # Color based on win rate
                if win_rate >= 0.6:
                    color = "#2ecc71"  # Green
                elif win_rate >= 0.45:
                    color = UI_COLORS["text_primary"]  # Normal
                else:
                    color = "#e74c3c"  # Red

                text = f"{matches:3} matches | {win_rate:5.1%} win rate | Data: {has_data}"
                self.surface_labels[surface].configure(text=text, fg=color)
            else:
                self.surface_labels[surface].configure(text="No matches", fg=UI_COLORS["text_secondary"])

        # Update current status (fatigue)
        try:
            fatigue = analyzer.calculate_fatigue(player_id)

            # Days since last match
            days_rest = fatigue.get('days_since_match', 0)
            if days_rest == 0:
                days_text = "Today"
            elif days_rest == 1:
                days_text = "Yesterday"
            else:
                days_text = f"{days_rest} days ago"
            self.status_labels["Days Since Match"].configure(text=days_text)

            # Fatigue status with color
            fatigue_status = fatigue.get('status', 'Unknown')
            fatigue_score = fatigue.get('score', 50)
            if fatigue_status in ['Fresh', 'Good']:
                fatigue_color = "#2ecc71"
            elif fatigue_status == 'Moderate':
                fatigue_color = "#f39c12"
            else:
                fatigue_color = "#e74c3c"
            self.status_labels["Fatigue"].configure(text=f"{fatigue_status} ({fatigue_score:.0f})", fg=fatigue_color)

            # Matches in 7d and 30d
            self.status_labels["Matches (7d)"].configure(text=str(fatigue.get('matches_7d', 0)))
            self.status_labels["Matches (30d)"].configure(text=str(fatigue.get('matches_30d', 0)))
        except Exception as e:
            for field in self.status_labels:
                self.status_labels[field].configure(text="-")

        # Update notable opponents (best win / worst loss)
        all_matches = db.get_player_matches(player_id)

        best_win = None
        worst_loss = None
        best_win_rank = 99999
        worst_loss_rank = 0

        for m in all_matches:
            if db.get_canonical_id(m['winner_id']) == canonical_id:
                # This is a win - check opponent rank
                opponent = db.get_player(m['loser_id'])
                if opponent:
                    opp_rank = opponent.get('ranking') or opponent.get('current_ranking') or 9999
                    if isinstance(opp_rank, int) and opp_rank < best_win_rank:
                        best_win_rank = opp_rank
                        best_win = (opponent['name'], opp_rank, m.get('date', '')[:10])
            else:
                # This is a loss - check opponent rank
                opponent = db.get_player(m['winner_id'])
                if opponent:
                    opp_rank = opponent.get('ranking') or opponent.get('current_ranking') or 0
                    if isinstance(opp_rank, int) and opp_rank > worst_loss_rank and opp_rank < 9999:
                        worst_loss_rank = opp_rank
                        worst_loss = (opponent['name'], opp_rank, m.get('date', '')[:10])

        if best_win:
            self.opponent_labels["Best Win"].configure(
                text=f"#{best_win[1]} {best_win[0]} ({best_win[2]})",
                fg="#2ecc71"
            )
        else:
            self.opponent_labels["Best Win"].configure(text="None recorded", fg=UI_COLORS["text_secondary"])

        if worst_loss:
            self.opponent_labels["Worst Loss"].configure(
                text=f"#{worst_loss[1]} {worst_loss[0]} ({worst_loss[2]})",
                fg="#e74c3c"
            )
        else:
            self.opponent_labels["Worst Loss"].configure(text="None recorded", fg=UI_COLORS["text_secondary"])

        # Update recent matches
        recent = sorted(all_matches, key=lambda x: x.get('date', ''), reverse=True)[:10]

        self.matches_text.configure(state=tk.NORMAL)
        self.matches_text.delete(1.0, tk.END)

        wins = losses = 0
        for m in recent:
            date = m.get('date', '')[:10]
            surface = m.get('surface', '?')[0]
            tourney = m.get('tournament', '')[:22]

            if db.get_canonical_id(m['winner_id']) == canonical_id:
                result = 'W'
                wins += 1
                opponent_id = m['loser_id']
                tag = "win"
            else:
                result = 'L'
                losses += 1
                opponent_id = m['winner_id']
                tag = "loss"

            opponent = db.get_player(opponent_id)
            opp_name = (opponent['name'] if opponent else 'Unknown')[:18]
            opp_rank = opponent.get('ranking') or opponent.get('current_ranking') if opponent else '?'
            opp_rank_str = f"#{opp_rank}" if opp_rank and opp_rank != '?' else "UR"

            line = f"{date} [{surface}] {result} vs {opp_name:18} ({opp_rank_str:>5}) {tourney}\n"
            self.matches_text.insert(tk.END, line, tag)

        self.matches_text.configure(state=tk.DISABLED)

        # Update form label
        if wins + losses > 0:
            form_pct = wins / (wins + losses) * 100
            self.form_label.configure(text=f"Form: {wins}W-{losses}L ({form_pct:.0f}%)")
        else:
            self.form_label.configure(text="")

        # Load aliases for this player
        self._load_aliases(player_id)

        self.status_var.set(f"Showing profile for {player.get('name', 'Unknown')}")

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

                # Update count label
                if aliases:
                    self.alias_count_label.configure(text=f"({len(aliases)} aliases)")
                else:
                    self.alias_count_label.configure(text="(none)")

        except Exception as e:
            print(f"Error loading aliases: {e}")
            self.alias_count_label.configure(text="")

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

    def _sync_tournament_names(self):
        """Sync tournament names across all tables to use consistent Betfair naming."""
        try:
            results = db.sync_tournament_names()
            total = sum(results.values())

            if total > 0:
                msg = f"Tournament names synced!\n\n"
                msg += f"Matches table: {results['matches']} updated\n"
                msg += f"Bets table: {results['bets']} updated\n"
                msg += f"Upcoming matches: {results['upcoming_matches']} updated"
                messagebox.showinfo("Sync Complete", msg)

                # Refresh the tournaments list if on that tab
                if hasattr(self, 'tournaments_tree'):
                    self._search_tournaments(show_all=True)
            else:
                messagebox.showinfo("Sync Complete", "All tournament names are already synced.")

            self.status_var.set(f"Tournament sync complete: {total} records updated")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to sync tournament names: {e}")

    def _check_player_data(self):
        """Check all players in upcoming matches for data quality."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Player Data Check")
        dialog.geometry("900x600")
        dialog.configure(bg=UI_COLORS["bg_dark"])
        dialog.transient(self.root)
        dialog.grab_set()

        content = tk.Frame(dialog, bg=UI_COLORS["bg_dark"], padx=20, pady=20)
        content.pack(fill=tk.BOTH, expand=True)

        tk.Label(content, text="Player Data Quality Report", font=("Segoe UI", 14, "bold"),
                bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_primary"]).pack(anchor=tk.W, pady=(0, 15))

        # Results tree
        columns = ("status", "name", "matches", "surface_data", "last_match")
        tree = ttk.Treeview(content, columns=columns, show="headings", height=20)

        tree.heading("status", text="Status")
        tree.heading("name", text="Player Name")
        tree.heading("matches", text="Matches")
        tree.heading("surface_data", text="Surface Data")
        tree.heading("last_match", text="Last Match")

        tree.column("status", width=100)
        tree.column("name", width=200)
        tree.column("matches", width=80)
        tree.column("surface_data", width=250)
        tree.column("last_match", width=100)

        scrollbar = ttk.Scrollbar(content, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Get all unique players from upcoming matches
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()

                # Get unique player IDs and names from upcoming matches
                cursor.execute('''
                    SELECT DISTINCT player1_id, player1_name FROM upcoming_matches WHERE player1_id IS NOT NULL
                    UNION
                    SELECT DISTINCT player2_id, player2_name FROM upcoming_matches WHERE player2_id IS NOT NULL
                ''')
                players = cursor.fetchall()

                no_data = []
                insufficient = []
                good = []

                for player_id, player_name in players:
                    if not player_id:
                        continue

                    # Get match count
                    cursor.execute('''
                        SELECT COUNT(*) FROM matches
                        WHERE winner_id = ? OR loser_id = ?
                    ''', (player_id, player_id))
                    match_count = cursor.fetchone()[0]

                    # Get surface breakdown
                    cursor.execute('''
                        SELECT surface, COUNT(*) FROM matches
                        WHERE winner_id = ? OR loser_id = ?
                        GROUP BY surface
                    ''', (player_id, player_id))
                    surfaces = cursor.fetchall()
                    surface_str = ", ".join([f"{s}: {c}" for s, c in surfaces]) if surfaces else "None"

                    # Get last match date
                    cursor.execute('''
                        SELECT MAX(date) FROM matches
                        WHERE winner_id = ? OR loser_id = ?
                    ''', (player_id, player_id))
                    last_match = cursor.fetchone()[0] or "Never"
                    if last_match != "Never":
                        last_match = last_match[:10]  # Just the date part

                    # Categorize
                    if match_count == 0:
                        status = "NO DATA"
                        no_data.append((status, player_name, match_count, surface_str, last_match))
                    elif match_count < 5:
                        status = "LOW DATA"
                        insufficient.append((status, player_name, match_count, surface_str, last_match))
                    else:
                        status = "OK"
                        good.append((status, player_name, match_count, surface_str, last_match))

                # Insert into tree - flagged first, then OK
                for item in no_data:
                    tree.insert('', tk.END, values=item, tags=('no_data',))
                for item in insufficient:
                    tree.insert('', tk.END, values=item, tags=('low_data',))
                for item in good:
                    tree.insert('', tk.END, values=item, tags=('ok',))

                # Color tags
                tree.tag_configure('no_data', background='#c0392b', foreground='white')
                tree.tag_configure('low_data', background='#e67e22', foreground='white')
                tree.tag_configure('ok', background=UI_COLORS["bg_medium"])

                # Summary
                summary = f"Total: {len(players)} players | "
                summary += f"No Data: {len(no_data)} | "
                summary += f"Low Data (<5): {len(insufficient)} | "
                summary += f"OK: {len(good)}"

                tk.Label(content, text=summary, font=("Segoe UI", 10),
                        bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=(10, 0))

        except Exception as e:
            tk.Label(content, text=f"Error: {e}", font=("Segoe UI", 10),
                    bg=UI_COLORS["bg_dark"], fg=UI_COLORS["error"]).pack()

        # Close button
        tk.Button(dialog, text="Close", command=dialog.destroy,
                 font=("Segoe UI", 10), bg=UI_COLORS["primary"], fg="white",
                 relief=tk.FLAT, padx=20, pady=5).pack(pady=10)

        # Double-click to view player profile
        def on_double_click(event):
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                player_name = item['values'][1]
                # Search for this player
                self.search_var.set(player_name)
                self._search_players()
                dialog.destroy()

        tree.bind('<Double-1>', on_double_click)

    def _open_tennis_explorer(self):
        """Open the current player's Tennis Explorer page in browser."""
        if not hasattr(self, 'current_te_url') or not self.current_te_url:
            messagebox.showwarning("No URL", "No Tennis Explorer URL available for this player.")
            return

        import webbrowser
        webbrowser.open(self.current_te_url)

    def _edit_player(self):
        """Edit the current player's properties."""
        if not hasattr(self, 'current_player_id') or not self.current_player_id:
            messagebox.showwarning("No Player", "Please select a player first.")
            return

        player_id = self.current_player_id
        player = db.get_player(player_id)

        if not player:
            messagebox.showerror("Error", "Player not found in database.")
            return

        # Create edit dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Player: {player['name']}")
        dialog.geometry("500x450")
        dialog.configure(bg=UI_COLORS["bg_dark"])
        dialog.transient(self.root)
        dialog.grab_set()

        content = tk.Frame(dialog, bg=UI_COLORS["bg_dark"], padx=20, pady=20)
        content.pack(fill=tk.BOTH, expand=True)

        # ID (read-only)
        id_frame = tk.Frame(content, bg=UI_COLORS["bg_dark"])
        id_frame.pack(fill=tk.X, pady=5)
        tk.Label(id_frame, text="ID:", bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_secondary"],
                font=("Segoe UI", 10), width=12, anchor='w').pack(side=tk.LEFT)
        tk.Label(id_frame, text=str(player_id), bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_primary"],
                font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)

        # Name
        name_frame = tk.Frame(content, bg=UI_COLORS["bg_dark"])
        name_frame.pack(fill=tk.X, pady=5)
        tk.Label(name_frame, text="Name:", bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_secondary"],
                font=("Segoe UI", 10), width=12, anchor='w').pack(side=tk.LEFT)
        name_var = tk.StringVar(value=player['name'])
        name_entry = tk.Entry(name_frame, textvariable=name_var, font=("Segoe UI", 10),
                             bg=UI_COLORS["bg_medium"], fg=UI_COLORS["text_primary"],
                             insertbackground=UI_COLORS["text_primary"], width=35)
        name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Ranking
        ranking_frame = tk.Frame(content, bg=UI_COLORS["bg_dark"])
        ranking_frame.pack(fill=tk.X, pady=5)
        tk.Label(ranking_frame, text="Ranking:", bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_secondary"],
                font=("Segoe UI", 10), width=12, anchor='w').pack(side=tk.LEFT)
        ranking_var = tk.StringVar(value=str(player.get('current_ranking', '') or ''))
        ranking_entry = tk.Entry(ranking_frame, textvariable=ranking_var, font=("Segoe UI", 10),
                                bg=UI_COLORS["bg_medium"], fg=UI_COLORS["text_primary"],
                                insertbackground=UI_COLORS["text_primary"], width=10)
        ranking_entry.pack(side=tk.LEFT)

        # Country
        country_frame = tk.Frame(content, bg=UI_COLORS["bg_dark"])
        country_frame.pack(fill=tk.X, pady=5)
        tk.Label(country_frame, text="Country:", bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_secondary"],
                font=("Segoe UI", 10), width=12, anchor='w').pack(side=tk.LEFT)
        country_var = tk.StringVar(value=player.get('country', '') or '')
        country_entry = tk.Entry(country_frame, textvariable=country_var, font=("Segoe UI", 10),
                                bg=UI_COLORS["bg_medium"], fg=UI_COLORS["text_primary"],
                                insertbackground=UI_COLORS["text_primary"], width=10)
        country_entry.pack(side=tk.LEFT)

        # ELO
        elo_frame = tk.Frame(content, bg=UI_COLORS["bg_dark"])
        elo_frame.pack(fill=tk.X, pady=5)
        tk.Label(elo_frame, text="ELO:", bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_secondary"],
                font=("Segoe UI", 10), width=12, anchor='w').pack(side=tk.LEFT)
        elo_var = tk.StringVar(value=str(player.get('elo_rating', '') or ''))
        elo_entry = tk.Entry(elo_frame, textvariable=elo_var, font=("Segoe UI", 10),
                            bg=UI_COLORS["bg_medium"], fg=UI_COLORS["text_primary"],
                            insertbackground=UI_COLORS["text_primary"], width=10)
        elo_entry.pack(side=tk.LEFT)

        # Info
        info_frame = tk.Frame(content, bg=UI_COLORS["bg_dark"])
        info_frame.pack(fill=tk.X, pady=(20, 5))
        tk.Label(info_frame, text="Note: Changing the name will update all matches\n"
                                  "where this player appears (as winner or loser).",
                bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_secondary"],
                font=("Segoe UI", 9), justify=tk.LEFT).pack(anchor=tk.W)

        # Buttons
        btn_frame = tk.Frame(content, bg=UI_COLORS["bg_dark"])
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        def save_changes():
            new_name = name_var.get().strip()
            new_ranking = ranking_var.get().strip()
            new_country = country_var.get().strip()
            new_elo = elo_var.get().strip()

            if not new_name:
                messagebox.showerror("Error", "Player name cannot be empty.")
                return

            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()

                    # Parse numeric fields
                    ranking_int = int(new_ranking) if new_ranking else None
                    elo_int = int(new_elo) if new_elo else None

                    # Update players table
                    cursor.execute('''
                        UPDATE players SET name = ?, current_ranking = ?, country = ?, elo_rating = ?
                        WHERE id = ?
                    ''', (new_name, ranking_int, new_country or None, elo_int, player_id))

                    # If name changed, update matches table
                    old_name = player['name']
                    if new_name != old_name:
                        cursor.execute('UPDATE matches SET winner_name = ? WHERE winner_id = ?',
                                      (new_name, player_id))
                        winner_updated = cursor.rowcount
                        cursor.execute('UPDATE matches SET loser_name = ? WHERE loser_id = ?',
                                      (new_name, player_id))
                        loser_updated = cursor.rowcount
                    else:
                        winner_updated = loser_updated = 0

                    conn.commit()

                msg = "Player updated!\n\n"
                if new_name != old_name:
                    msg += f"Name: {old_name} -> {new_name}\n"
                    msg += f"Updated {winner_updated + loser_updated} match records."

                messagebox.showinfo("Success", msg)

                # Refresh display
                self._show_player_details(player_id)
                dialog.destroy()

            except ValueError:
                messagebox.showerror("Error", "Ranking and ELO must be numbers.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save changes: {e}")

        tk.Button(btn_frame, text="Save", command=save_changes, font=("Segoe UI", 10),
                 bg=UI_COLORS["success"], fg="white", relief=tk.FLAT, padx=20, pady=5).pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text="Cancel", command=dialog.destroy, font=("Segoe UI", 10),
                 bg=UI_COLORS["bg_medium"], fg=UI_COLORS["text_primary"], relief=tk.FLAT,
                 padx=20, pady=5).pack(side=tk.LEFT, padx=5)

    def _edit_tournament(self):
        """Edit the current tournament's properties."""
        if not hasattr(self, 'current_tournament_name') or not self.current_tournament_name:
            messagebox.showwarning("No Tournament", "Please select a tournament first.")
            return

        tournament_name = self.current_tournament_name

        # Create edit dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Tournament: {tournament_name}")
        dialog.geometry("500x400")
        dialog.configure(bg=UI_COLORS["bg_dark"])
        dialog.transient(self.root)
        dialog.grab_set()

        content = tk.Frame(dialog, bg=UI_COLORS["bg_dark"], padx=20, pady=20)
        content.pack(fill=tk.BOTH, expand=True)

        # Get current tournament data
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, name, surface, level FROM tournaments WHERE name = ?', (tournament_name,))
            row = cursor.fetchone()

            if not row:
                messagebox.showerror("Error", "Tournament not found in database.")
                dialog.destroy()
                return

            current_id, current_name, current_surface, current_level = row

        # ID (read-only)
        id_frame = tk.Frame(content, bg=UI_COLORS["bg_dark"])
        id_frame.pack(fill=tk.X, pady=5)
        tk.Label(id_frame, text="ID:", bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_secondary"],
                font=("Segoe UI", 10), width=12, anchor='w').pack(side=tk.LEFT)
        tk.Label(id_frame, text=str(current_id), bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_primary"],
                font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)

        # Name
        name_frame = tk.Frame(content, bg=UI_COLORS["bg_dark"])
        name_frame.pack(fill=tk.X, pady=5)
        tk.Label(name_frame, text="Name:", bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_secondary"],
                font=("Segoe UI", 10), width=12, anchor='w').pack(side=tk.LEFT)
        name_var = tk.StringVar(value=current_name)
        name_entry = tk.Entry(name_frame, textvariable=name_var, font=("Segoe UI", 10),
                             bg=UI_COLORS["bg_medium"], fg=UI_COLORS["text_primary"],
                             insertbackground=UI_COLORS["text_primary"], width=35)
        name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Surface
        surface_frame = tk.Frame(content, bg=UI_COLORS["bg_dark"])
        surface_frame.pack(fill=tk.X, pady=5)
        tk.Label(surface_frame, text="Surface:", bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_secondary"],
                font=("Segoe UI", 10), width=12, anchor='w').pack(side=tk.LEFT)
        surface_var = tk.StringVar(value=current_surface or "Hard")
        surface_options = ["Hard", "Clay", "Grass"]
        surface_menu = ttk.Combobox(surface_frame, textvariable=surface_var, values=surface_options,
                                    state="readonly", width=15, font=("Segoe UI", 10))
        surface_menu.pack(side=tk.LEFT)

        # Category/Level
        level_frame = tk.Frame(content, bg=UI_COLORS["bg_dark"])
        level_frame.pack(fill=tk.X, pady=5)
        tk.Label(level_frame, text="Category:", bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_secondary"],
                font=("Segoe UI", 10), width=12, anchor='w').pack(side=tk.LEFT)
        level_var = tk.StringVar(value=current_level or "Other")
        level_options = ["Grand Slam", "Masters 1000", "ATP 500", "ATP 250", "ATP", "WTA", "Challenger", "ITF", "Other"]
        level_menu = ttk.Combobox(level_frame, textvariable=level_var, values=level_options,
                                  state="readonly", width=15, font=("Segoe UI", 10))
        level_menu.pack(side=tk.LEFT)

        # Info about what will be updated
        info_frame = tk.Frame(content, bg=UI_COLORS["bg_dark"])
        info_frame.pack(fill=tk.X, pady=(20, 5))
        tk.Label(info_frame, text="Note: Changing the name or surface will update all matches\n"
                                  "with this tournament in the database.",
                bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_secondary"],
                font=("Segoe UI", 9), justify=tk.LEFT).pack(anchor=tk.W)

        # Buttons
        btn_frame = tk.Frame(content, bg=UI_COLORS["bg_dark"])
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        def save_changes():
            new_name = name_var.get().strip()
            new_surface = surface_var.get()
            new_level = level_var.get()

            if not new_name:
                messagebox.showerror("Error", "Tournament name cannot be empty.")
                return

            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()

                    # Update tournaments table
                    cursor.execute('''
                        UPDATE tournaments SET name = ?, surface = ?, level = ?
                        WHERE id = ?
                    ''', (new_name, new_surface, new_level, current_id))

                    # If name changed, update matches table
                    if new_name != current_name:
                        cursor.execute('UPDATE matches SET tournament = ? WHERE tournament = ?',
                                      (new_name, current_name))
                        matches_updated = cursor.rowcount

                        # Also update bets and upcoming_matches
                        cursor.execute('UPDATE bets SET tournament = ? WHERE tournament = ?',
                                      (new_name, current_name))
                        cursor.execute('UPDATE upcoming_matches SET tournament = ? WHERE tournament = ?',
                                      (new_name, current_name))

                    # If surface changed, update matches table
                    if new_surface != current_surface:
                        cursor.execute('UPDATE matches SET surface = ? WHERE tournament = ?',
                                      (new_surface, new_name))
                        surface_updated = cursor.rowcount
                    else:
                        surface_updated = 0

                    conn.commit()

                msg = f"Tournament updated!\n\n"
                msg += f"Name: {current_name} -> {new_name}\n" if new_name != current_name else ""
                msg += f"Surface: {current_surface} -> {new_surface}\n" if new_surface != current_surface else ""
                msg += f"Category: {current_level} -> {new_level}\n" if new_level != current_level else ""

                if new_surface != current_surface:
                    msg += f"\n{surface_updated} matches updated with new surface."

                messagebox.showinfo("Success", msg)

                # Update the current tournament name and refresh display
                self.current_tournament_name = new_name
                self._show_tournament_details(new_name)

                # Refresh tournaments list
                self._search_tournaments(show_all=True)

                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to save changes: {e}")

        tk.Button(btn_frame, text="Save", command=save_changes, font=("Segoe UI", 10),
                 bg=UI_COLORS["success"], fg="white", relief=tk.FLAT, padx=20, pady=5).pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text="Cancel", command=dialog.destroy, font=("Segoe UI", 10),
                 bg=UI_COLORS["bg_medium"], fg=UI_COLORS["text_primary"], relief=tk.FLAT,
                 padx=20, pady=5).pack(side=tk.LEFT, padx=5)

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


def open_player_profile(parent: tk.Tk, player_id: int, player_name: str = None):
    """Open Database Management window and navigate to the player's profile.

    This shows the exact same view as the Database Management player profile.

    Args:
        parent: Parent window
        player_id: The player's database ID
        player_name: Optional player name for searching
    """
    player = db.get_player(player_id)
    if not player:
        messagebox.showerror("Player Not Found", f"Player ID {player_id} not found in database.")
        return

    name = player_name or player.get('name', f'Player {player_id}')

    # Open Database Management and navigate to this player
    db_ui = DatabaseUI(parent)

    # Search for the player and select them
    db_ui.search_var.set(name)
    db_ui._search_players()

    # Try to select the player in the tree
    for item in db_ui.players_tree.get_children():
        values = db_ui.players_tree.item(item, 'values')
        if values and int(values[0]) == player_id:
            db_ui.players_tree.selection_set(item)
            db_ui.players_tree.see(item)
            db_ui._on_player_select(None)
            break


if __name__ == "__main__":
    app = DatabaseUI()
    app.root.mainloop()
