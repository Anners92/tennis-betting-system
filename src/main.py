"""
Tennis Betting System - Main Application
Modern UI matching the football betting tool style.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
import os
import threading
import time
from datetime import datetime, timedelta

# Set Windows AppUserModelID so taskbar shows our icon instead of Python's
try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('TennisBettingSystem.App.1.0')
except Exception:
    pass  # Not on Windows or failed - ignore

# Handle PyInstaller frozen executable
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    application_path = os.path.dirname(sys.executable)
else:
    # Running as script
    application_path = os.path.dirname(os.path.abspath(__file__))

# Add application path so local modules (selenium, webdriver_manager, etc.) can be found
if application_path not in sys.path:
    sys.path.insert(0, application_path)

from config import DB_PATH, SURFACES, calculate_bet_model
from database import db
from betfair_capture import BetfairTennisCapture
from tennis_abstract_scraper import TennisAbstractScraper
from match_analyzer import MatchAnalyzerUI
from bet_suggester import BetSuggesterUI
from bet_tracker import BetTrackerUI
from player_lookup import PlayerLookupUI
from data_loader import DataLoaderUI
from odds_scraper import OddsManagerUI
from te_import_dialog import open_te_import_dialog
from match_assignment import open_match_assignment

SCRAPER_AVAILABLE = True


class ModernButton(tk.Frame):
    """A modern ghost/outline style button using Frame + Label."""

    def __init__(self, parent, text, command, color='#3b82f6', width=100, height=36,
                 font_size=10, **kwargs):
        self.parent_bg = parent['bg']
        self.color = color
        self.command = command

        # Create frame as button container with border
        super().__init__(parent, bg=self.parent_bg, highlightthickness=2,
                        highlightbackground=color, highlightcolor=color,
                        width=width, height=height, **kwargs)
        self.pack_propagate(False)  # Enforce fixed size

        # Inner label acts as button face - fixed size
        self.label = tk.Label(self, text=text, bg=self.parent_bg, fg=color,
                             font=('Segoe UI', font_size, 'bold'), cursor='hand2')
        self.label.place(relx=0.5, rely=0.5, anchor='center')

        # Bind events
        for widget in (self, self.label):
            widget.bind('<Enter>', self._on_enter)
            widget.bind('<Leave>', self._on_leave)
            widget.bind('<Button-1>', self._on_press)
            widget.bind('<ButtonRelease-1>', self._on_release)

    def _on_enter(self, event):
        try:
            self.label.configure(bg=self.color, fg='white')
            self.configure(bg=self.color)
        except tk.TclError:
            pass

    def _on_leave(self, event):
        try:
            self.label.configure(bg=self.parent_bg, fg=self.color)
            self.configure(bg=self.parent_bg)
        except tk.TclError:
            pass

    def _on_press(self, event):
        try:
            darker = self._darken_color(self.color, 0.15)
            self.label.configure(bg=darker)
            self.configure(bg=darker)
        except tk.TclError:
            pass

    def _on_release(self, event):
        try:
            self.label.configure(bg=self.color, fg='white')
            self.configure(bg=self.color)
            if self.command:
                self.command()
        except tk.TclError:
            pass

    def _darken_color(self, hex_color, factor):
        """Darken a hex color."""
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:], 16)
        r = max(0, int(r * (1 - factor)))
        g = max(0, int(g * (1 - factor)))
        b = max(0, int(b * (1 - factor)))
        return f'#{r:02x}{g:02x}{b:02x}'


class BackgroundUpdater:
    """Background thread to update players with matches within 3 days."""

    def __init__(self, root, status_callback=None):
        self.root = root
        self.status_callback = status_callback
        self.scraper = TennisAbstractScraper() if SCRAPER_AVAILABLE else None
        self.running = False
        self.thread = None
        self.update_interval = 30 * 60  # 30 minutes between full cycles
        self.player_delay = 5  # 5 seconds between player updates to avoid rate limiting

    def start(self):
        """Start the background updater."""
        if self.running:
            return
        if not self.scraper:
            # Scraper not available, don't start background updates
            return
        self.running = True
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the background updater."""
        self.running = False

    def _set_status(self, text, is_updating=False):
        """Update status via callback (thread-safe)."""
        if self.status_callback:
            self.root.after(0, lambda: self.status_callback(text, is_updating))

    def _get_players_with_recent_matches(self):
        """Get unique players with matches within 3 days of today."""
        players = {}
        today = datetime.now().date()
        window_start = today - timedelta(days=3)
        window_end = today + timedelta(days=3)

        # Get upcoming matches
        try:
            upcoming = db.get_upcoming_matches()
            for match in upcoming:
                match_date_str = match.get('date', '')
                if match_date_str:
                    try:
                        match_date = datetime.strptime(match_date_str[:10], '%Y-%m-%d').date()
                        if window_start <= match_date <= window_end:
                            p1_id = match.get('player1_id')
                            p2_id = match.get('player2_id')
                            p1_name = match.get('player1_name')
                            p2_name = match.get('player2_name')
                            if p1_id and p1_name:
                                players[p1_id] = p1_name
                            if p2_id and p2_name:
                                players[p2_id] = p2_name
                    except ValueError:
                        pass
        except Exception as e:
            print(f"Error getting upcoming matches: {e}")

        # Also check recent matches from database
        try:
            recent = db.get_recent_matches(days=3)
            for match in recent:
                winner_id = match.get('winner_id')
                loser_id = match.get('loser_id')
                winner_name = match.get('winner_name')
                loser_name = match.get('loser_name')
                if winner_id and winner_name:
                    players[winner_id] = winner_name
                if loser_id and loser_name:
                    players[loser_id] = loser_name
        except Exception as e:
            print(f"Error getting recent matches: {e}")

        return players

    def _update_loop(self):
        """Main update loop."""
        while self.running:
            try:
                players = self._get_players_with_recent_matches()

                if players:
                    # Filter out players updated within 6 hours
                    players_to_update = {
                        pid: name for pid, name in players.items()
                        if db.player_needs_ta_update(pid, hours=6)
                    }

                    if players_to_update:
                        self._set_status(f"Updating {len(players_to_update)} players...", True)
                        updated_count = 0

                        for i, (player_id, player_name) in enumerate(players_to_update.items(), 1):
                            if not self.running:
                                break

                            self._set_status(f"Updating {player_name} ({i}/{len(players_to_update)})", True)

                            try:
                                self.scraper.fetch_and_update_player(player_id, player_name)
                                updated_count += 1
                            except Exception as e:
                                print(f"Error updating {player_name}: {e}")

                            # Delay between players
                            if self.running and i < len(players_to_update):
                                time.sleep(self.player_delay)

                        self._set_status(f"Updated {updated_count} players", False)
                    else:
                        skipped = len(players)
                        self._set_status(f"All {skipped} players up to date", False)
                else:
                    self._set_status("No recent players to update", False)

            except Exception as e:
                self._set_status(f"Error: {str(e)[:30]}", False)

            # Wait for next cycle
            for _ in range(self.update_interval):
                if not self.running:
                    break
                time.sleep(1)

        self._set_status("Updater stopped", False)


class MainApplication:
    """Main hub for the tennis betting tool."""

    # Premium Dark Mode color palette
    BG_DARK = '#0f172a'          # Deep slate background
    BG_CARD = '#1e293b'          # Slate-800 for cards
    BG_CARD_HOVER = '#334155'    # Slate-700 on hover
    BORDER_DEFAULT = '#334155'   # Subtle slate border
    BORDER_HOVER = '#475569'     # Slightly brighter on hover

    # Unified brand accent (Electric Blue)
    ACCENT_PRIMARY = '#3b82f6'   # Primary brand color for all buttons

    # Category glow colors (only used for hover glow effect)
    GLOW_CYAN = '#06b6d4'        # Betfair
    GLOW_GREEN = '#22c55e'       # Bet Suggester
    GLOW_BLUE = '#3b82f6'        # Bet Tracker
    GLOW_PURPLE = '#a855f7'      # Rankings
    GLOW_AMBER = '#f59e0b'       # Database

    # Semantic colors (for status indicators only)
    ACCENT_SUCCESS = '#22c55e'   # Green - positive ROI, success states
    ACCENT_DANGER = '#ef4444'    # Red - negative ROI, errors
    ACCENT_WARNING = '#f59e0b'   # Amber - warnings

    # Text colors
    TEXT_PRIMARY = '#f1f5f9'     # Slate-100
    TEXT_SECONDARY = '#94a3b8'   # Slate-400
    TEXT_MUTED = '#64748b'       # Slate-500

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Tennis Betting System")
        self.root.configure(bg=self.BG_DARK)
        self.root.resizable(True, True)
        self.root.state('zoomed')  # Launch maximized

        # Store reference to main app for child windows to access
        self.root.main_app = self

        # Auto Mode state
        self.auto_mode_enabled = False
        self.auto_mode_job = None
        self.auto_mode_interval = 30 * 60 * 1000  # 30 minutes in milliseconds
        self.next_auto_run = None

        # Set taskbar icon
        self._set_app_icon()

        # Configure styles
        self._setup_styles()

    def _set_app_icon(self):
        """Set the application icon for taskbar and title bar."""
        try:
            # Find icon path - check multiple locations
            if getattr(sys, 'frozen', False):
                # Running as frozen executable
                base_path = os.path.dirname(sys.executable)
            else:
                # Running as script - go up one level from src/
                base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            ico_path = os.path.join(base_path, 'Assets', 'tbs_icon.ico')
            print(f"Setting icon from: {ico_path}")

            if os.path.exists(ico_path):
                self.root.iconbitmap(default=ico_path)
                print("Icon set successfully")
            else:
                print(f"Icon not found at: {ico_path}")
        except Exception as e:
            import traceback
            print(f"Could not set app icon: {e}")
            traceback.print_exc()

        self._create_ui()
        self._update_stats()

        # Background updater disabled - we now use GitHub data which is comprehensive
        self.bg_updater = None

        # Auto-refresh data from GitHub if stale, then fetch Betfair matches
        self._auto_startup_tasks()

        # Clean up on close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_styles(self):
        """Configure ttk styles for modern look."""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('Modern.TCombobox',
                       fieldbackground=self.BG_CARD,
                       background=self.BG_CARD,
                       foreground=self.TEXT_PRIMARY)

    def _create_ui(self):
        """Create the main interface."""
        # Main container with padding
        main_container = tk.Frame(self.root, bg=self.BG_DARK)
        main_container.pack(fill=tk.BOTH, expand=True, padx=25, pady=20)

        # === HEADER ===
        self._create_header(main_container)

        # === GETTING STARTED GUIDE ===
        self._create_getting_started(main_container)

        # === STATS CARDS ===
        self._create_stats_section(main_container)

        # === MAIN FEATURE GRID ===
        self._create_feature_grid(main_container)

        # === QUICK ACTIONS ===
        self._create_quick_actions(main_container)

        # === FOOTER ===
        self._create_footer(main_container)

    def _create_header(self, parent):
        """Create the header section."""
        header = tk.Frame(parent, bg=self.BG_DARK)
        header.pack(fill=tk.X, pady=(0, 20))

        # Title - white and bold
        tk.Label(header, text="Tennis Betting System",
                font=('Segoe UI', 32, 'bold'), bg=self.BG_DARK,
                fg='#ffffff').pack(anchor='w')

        # Subtitle - lighter grey (slate-400) and smaller
        tk.Label(header, text="ATP/WTA/ITF match analysis, form tracking & expected value betting",
                font=('Segoe UI', 10), bg=self.BG_DARK,
                fg='#94a3b8').pack(anchor='w', pady=(4, 0))

    def _create_getting_started(self, parent):
        """Create a simple getting started guide for first-time users."""
        # Premium dark card style
        guide_frame = tk.Frame(parent, bg=self.BG_CARD,
                              highlightbackground=self.BORDER_DEFAULT,
                              highlightthickness=1)
        guide_frame.pack(fill=tk.X, pady=(0, 20))

        inner = tk.Frame(guide_frame, bg=self.BG_CARD, padx=25, pady=18)
        inner.pack(fill=tk.X)

        # Title row
        title_row = tk.Frame(inner, bg=self.BG_CARD)
        title_row.pack(fill=tk.X)

        tk.Label(title_row, text="Getting Started", bg=self.BG_CARD, fg=self.TEXT_PRIMARY,
                font=('Segoe UI', 14, 'bold')).pack(side=tk.LEFT)

        tk.Label(title_row, text="Database pre-loaded - start finding value bets!", bg=self.BG_CARD,
                fg=self.TEXT_MUTED, font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=(15, 0))

        # Steps container
        steps_frame = tk.Frame(inner, bg=self.BG_CARD)
        steps_frame.pack(fill=tk.X, pady=(15, 0))

        # Steps with unified brand color icons
        steps = [
            ("1", "Betfair Tennis", "Capture upcoming match odds"),
            ("2", "Bet Suggester", "Find value betting opportunities"),
            ("3", "Quick Refresh", "Update recent match results"),
        ]

        for i, (num, title, desc) in enumerate(steps):
            step = tk.Frame(steps_frame, bg=self.BG_CARD)
            step.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0 if i == 0 else 20, 0))

            # Number in brand color circle
            icon_frame = tk.Frame(step, bg=self.ACCENT_PRIMARY, width=32, height=32)
            icon_frame.pack(side=tk.LEFT, padx=(0, 12))
            icon_frame.pack_propagate(False)

            tk.Label(icon_frame, text=num, bg=self.ACCENT_PRIMARY, fg='white',
                    font=('Segoe UI', 12, 'bold')).place(relx=0.5, rely=0.5, anchor='center')

            # Text
            text_frame = tk.Frame(step, bg=self.BG_CARD)
            text_frame.pack(side=tk.LEFT, fill=tk.X)

            tk.Label(text_frame, text=title, bg=self.BG_CARD, fg=self.TEXT_PRIMARY,
                    font=('Segoe UI', 11, 'bold')).pack(anchor='w')
            tk.Label(text_frame, text=desc, bg=self.BG_CARD, fg=self.TEXT_MUTED,
                    font=('Segoe UI', 9)).pack(anchor='w', pady=(2, 0))

    def _create_stats_section(self, parent):
        """Create the stats cards section."""
        stats_frame = tk.Frame(parent, bg=self.BG_DARK)
        stats_frame.pack(fill=tk.X, pady=(0, 25))

        self.stats_labels = {}
        self.stats_colors = {}  # Store default colors for each stat
        stats_items = [
            ('players', 'P L A Y E R S', self.TEXT_PRIMARY),
            ('matches', 'M A T C H E S', self.TEXT_PRIMARY),
            ('bets', 'T O T A L  B E T S', self.TEXT_PRIMARY),
            ('roi', 'R O I', self.TEXT_MUTED),  # ROI will be color-coded dynamically
        ]

        CARD_HEIGHT = 100  # Uniform height for all cards

        for i, (key, label, default_color) in enumerate(stats_items):
            card = tk.Frame(stats_frame, bg=self.BG_CARD,
                           highlightbackground=self.BORDER_DEFAULT,
                           highlightthickness=1,
                           height=CARD_HEIGHT)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0 if i == 0 else 8, 0))
            card.pack_propagate(False)  # Enforce fixed height

            # Inner padding
            inner = tk.Frame(card, bg=self.BG_CARD, padx=20, pady=15)
            inner.pack(fill=tk.BOTH, expand=True)

            # Label (smaller, uppercase, letter-spaced, muted)
            tk.Label(inner, text=label, bg=self.BG_CARD, fg=self.TEXT_MUTED,
                    font=('Segoe UI', 8)).pack(anchor='w')

            # Value (large, bold)
            value_label = tk.Label(inner, text="-", bg=self.BG_CARD, fg=default_color,
                                  font=('Segoe UI', 28, 'bold'))
            value_label.pack(anchor='w', pady=(8, 0))
            self.stats_labels[key] = value_label
            self.stats_colors[key] = default_color

    def _create_feature_grid(self, parent):
        """Create the main feature buttons grid."""
        # Use 6-column grid for centering flexibility
        grid_frame = tk.Frame(parent, bg=self.BG_DARK)
        grid_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        # Features with glow colors for hover effect
        row1_features = [
            ("Betfair Tennis", "Fetch live matches &\nodds from Betfair Exchange",
             self.GLOW_CYAN, self._open_betfair_tennis),
            ("Bet Suggester", "Find value bets from\nupcoming matches",
             self.GLOW_GREEN, self._open_bet_suggester),
            ("Bet Tracker", "Track bets & monitor\nROI performance",
             self.GLOW_BLUE, self._open_bet_tracker),
        ]

        row2_features = [
            ("Rankings", "View ATP & WTA\nplayer rankings",
             self.GLOW_PURPLE, self._open_rankings),
            ("Database", "Manage player IDs,\naliases & duplicates",
             self.GLOW_AMBER, self._open_database),
        ]

        # Row 1: 3 cards spanning columns 0-1, 2-3, 4-5
        for i, (title, desc, glow_color, cmd) in enumerate(row1_features):
            card = self._create_feature_card(grid_frame, title, desc, glow_color, cmd)
            col = i * 2  # 0, 2, 4
            card.grid(row=0, column=col, columnspan=2,
                     padx=(0 if i == 0 else 6, 0 if i == 2 else 6),
                     pady=(0, 12), sticky='nsew')

        # Row 2: 2 cards centered - spanning columns 1-2 and 3-4
        for i, (title, desc, glow_color, cmd) in enumerate(row2_features):
            card = self._create_feature_card(grid_frame, title, desc, glow_color, cmd)
            col = 1 + (i * 2)  # 1, 3
            card.grid(row=1, column=col, columnspan=2,
                     padx=6, sticky='nsew')

        # Configure grid weights - all 6 columns equal
        for i in range(6):
            grid_frame.grid_columnconfigure(i, weight=1)
        for i in range(2):
            grid_frame.grid_rowconfigure(i, weight=1)

    def _create_feature_card(self, parent, title, desc, glow_color, cmd):
        """Create a single feature card."""
        # Card container with subtle border
        card = tk.Frame(parent, bg=self.BG_CARD,
                       highlightbackground=self.BORDER_DEFAULT,
                       highlightthickness=1)

        # Inner content with fixed padding
        inner = tk.Frame(card, bg=self.BG_CARD)
        inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        tk.Label(inner, text=title, bg=self.BG_CARD, fg=self.TEXT_PRIMARY,
                font=('Segoe UI', 14, 'bold')).pack(anchor='w')

        # Description
        tk.Label(inner, text=desc, bg=self.BG_CARD, fg=self.TEXT_SECONDARY,
                font=('Segoe UI', 10), justify=tk.LEFT).pack(anchor='w', pady=(8, 15))

        # Button - yellow ghost style
        btn = ModernButton(inner, text="Open", command=cmd, color='#eab308',
                          width=100, height=36, font_size=10)
        btn.pack(anchor='w')

        # Click anywhere on card to open
        def on_click(e):
            if cmd:
                cmd()
        card.bind('<Button-1>', on_click)
        inner.bind('<Button-1>', on_click)
        card.configure(cursor='hand2')

        # Simple border color hover - bind to card and all children
        def on_enter(e):
            card.configure(highlightbackground=glow_color)
        def on_leave(e):
            card.configure(highlightbackground=self.BORDER_DEFAULT)

        def bind_recursive(widget):
            widget.bind('<Enter>', on_enter)
            widget.bind('<Leave>', on_leave)
            for child in widget.winfo_children():
                bind_recursive(child)

        bind_recursive(card)

        return card

    def _add_card_hover(self, card, inner, glow_color):
        """Add hover effect with category-specific glow border."""
        card._hover_active = False

        def set_hover_style():
            """Apply hover styling with glow border."""
            try:
                card.configure(bg=self.BG_CARD_HOVER,
                              highlightbackground=glow_color,
                              highlightthickness=2)
                inner.configure(bg=self.BG_CARD_HOVER)
                self._update_widget_bg(inner, self.BG_CARD_HOVER)
                # Simulate lift by adjusting grid padding
                card.grid_configure(pady=(0 if card.grid_info()['row'] == 0 else 10, 4))
            except tk.TclError:
                pass

        def set_normal_style():
            """Reset card to neutral styling."""
            try:
                card.configure(bg=self.BG_CARD,
                              highlightbackground=self.BORDER_DEFAULT,
                              highlightthickness=1)
                inner.configure(bg=self.BG_CARD)
                self._update_widget_bg(inner, self.BG_CARD)
                # Reset grid padding
                card.grid_configure(pady=(0 if card.grid_info()['row'] == 0 else 12, 2))
            except tk.TclError:
                pass

        def on_enter(e):
            card._hover_active = True
            set_hover_style()

        def on_leave(e):
            # Check if mouse is still within card bounds
            try:
                x, y = card.winfo_pointerxy()
                card_x = card.winfo_rootx()
                card_y = card.winfo_rooty()
                card_w = card.winfo_width()
                card_h = card.winfo_height()

                if not (card_x <= x < card_x + card_w and card_y <= y < card_y + card_h):
                    card._hover_active = False
                    set_normal_style()
            except tk.TclError:
                pass

        # Bind to card and all descendants
        self._bind_hover_recursive(card, on_enter, on_leave)

    def _update_widget_bg(self, parent, bg_color, exclude_colors=None):
        """Recursively update background color of child widgets, skipping accent-colored ones."""
        if exclude_colors is None:
            # Don't change widgets with glow/accent colors
            exclude_colors = {
                self.GLOW_CYAN, self.GLOW_GREEN, self.GLOW_BLUE,
                self.GLOW_PURPLE, self.GLOW_AMBER, self.ACCENT_PRIMARY,
                self.ACCENT_SUCCESS, self.ACCENT_DANGER, self.ACCENT_WARNING
            }
        for widget in parent.winfo_children():
            try:
                if isinstance(widget, (tk.Label, tk.Frame)):
                    # Skip widgets with accent colors
                    current_bg = widget.cget('bg')
                    if current_bg not in exclude_colors:
                        widget.configure(bg=bg_color)
                self._update_widget_bg(widget, bg_color, exclude_colors)
            except tk.TclError:
                pass

    def _bind_hover_recursive(self, widget, on_enter, on_leave):
        """Recursively bind hover events to widget and all children."""
        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)
        for child in widget.winfo_children():
            self._bind_hover_recursive(child, on_enter, on_leave)

    def _add_tooltip(self, widget, text):
        """Add a simple tooltip to a widget."""
        tooltip = None

        def show_tooltip(event):
            nonlocal tooltip
            if tooltip:
                return
            x = widget.winfo_rootx() + widget.winfo_width() // 2
            y = widget.winfo_rooty() + widget.winfo_height() + 5

            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{x}+{y}")

            label = tk.Label(tooltip, text=text, bg='#1e293b', fg='#f1f5f9',
                           font=('Segoe UI', 9), padx=8, pady=4,
                           relief=tk.SOLID, borderwidth=1)
            label.pack()

        def hide_tooltip(event):
            nonlocal tooltip
            if tooltip:
                tooltip.destroy()
                tooltip = None

        # Bind to widget and all children
        def bind_recursive(w):
            w.bind('<Enter>', show_tooltip, add='+')
            w.bind('<Leave>', hide_tooltip, add='+')
            for child in w.winfo_children():
                bind_recursive(child)

        bind_recursive(widget)

    def _update_last_refresh_display(self):
        """Update the last refresh timestamp display."""
        try:
            # Get both timestamps
            last_full = db.get_last_refresh('full')
            last_quick = db.get_last_refresh('quick')

            # Find the most recent one
            last_refresh = None
            refresh_type = None

            if last_full and last_quick:
                if last_full > last_quick:
                    last_refresh = last_full
                    refresh_type = 'Full'
                else:
                    last_refresh = last_quick
                    refresh_type = 'Quick'
            elif last_full:
                last_refresh = last_full
                refresh_type = 'Full'
            elif last_quick:
                last_refresh = last_quick
                refresh_type = 'Quick'

            if last_refresh:
                # Parse and format the timestamp
                try:
                    dt = datetime.fromisoformat(last_refresh)
                    now = datetime.now()
                    diff = now - dt

                    if diff.days > 0:
                        time_str = f"{diff.days}d ago"
                    elif diff.seconds >= 3600:
                        hours = diff.seconds // 3600
                        time_str = f"{hours}h ago"
                    elif diff.seconds >= 60:
                        mins = diff.seconds // 60
                        time_str = f"{mins}m ago"
                    else:
                        time_str = "Just now"

                    self.last_refresh_label.configure(
                        text=f"Last: {time_str}",
                        fg=self.TEXT_MUTED if diff.days == 0 else self.ACCENT_WARNING
                    )
                except:
                    self.last_refresh_label.configure(text="", fg=self.TEXT_MUTED)
            else:
                self.last_refresh_label.configure(
                    text="Never refreshed",
                    fg=self.ACCENT_WARNING
                )
        except Exception as e:
            print(f"Error updating refresh display: {e}")

    def _create_quick_actions(self, parent):
        """Create quick action buttons."""
        actions_frame = tk.Frame(parent, bg=self.BG_DARK)
        actions_frame.pack(fill=tk.X, pady=(0, 15))

        # Left side - main actions (unified brand color)
        left = tk.Frame(actions_frame, bg=self.BG_DARK)
        left.pack(side=tk.LEFT)

        # Full Refresh button with tooltip
        full_refresh_btn = ModernButton(left, "Full Refresh", self._refresh_data,
                    color=self.ACCENT_SUCCESS, width=120, height=38, font_size=10)
        full_refresh_btn.pack(side=tk.LEFT, padx=(0, 8))
        self._add_tooltip(full_refresh_btn, "6 months of ATP/WTA/ITF data (~15-20 min)")

        # Quick Refresh button with tooltip
        quick_refresh_btn = ModernButton(left, "Quick Refresh", self._quick_refresh_7_days,
                    color='#06b6d4', width=120, height=38, font_size=10)
        quick_refresh_btn.pack(side=tk.LEFT, padx=(0, 8))
        self._add_tooltip(quick_refresh_btn, "Last 7 days only (~2-3 min)")

        # Last refresh timestamp
        self.last_refresh_label = tk.Label(left, text="", bg=self.BG_DARK,
                                           fg=self.TEXT_MUTED, font=('Segoe UI', 8))
        self.last_refresh_label.pack(side=tk.LEFT, padx=(5, 15))
        self._update_last_refresh_display()

        ModernButton(left, "TE Import", self._open_te_import,
                    color=self.ACCENT_PRIMARY, width=100, height=38, font_size=10).pack(side=tk.LEFT, padx=(0, 10))

        ModernButton(left, "Clear Matches", self._clear_all_matches,
                    color=self.ACCENT_DANGER, width=130, height=38, font_size=10).pack(side=tk.LEFT, padx=(0, 15))

        # Auto Mode section (right side of quick actions)
        right = tk.Frame(actions_frame, bg=self.BG_DARK)
        right.pack(side=tk.RIGHT)

        # Auto mode status label
        self.auto_mode_status = tk.Label(right, text="Auto: OFF", bg=self.BG_DARK,
                                         fg=self.TEXT_MUTED, font=('Segoe UI', 9))
        self.auto_mode_status.pack(side=tk.LEFT, padx=(0, 8))

        # Auto mode toggle button
        self.auto_mode_btn = ModernButton(right, "Auto Mode", self._toggle_auto_mode,
                    color='#8b5cf6', width=100, height=38, font_size=10)
        self.auto_mode_btn.pack(side=tk.LEFT)

    def _create_footer(self, parent):
        """Create footer section."""
        footer = tk.Frame(parent, bg=self.BG_DARK)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        # Surface pills
        surfaces_frame = tk.Frame(footer, bg=self.BG_DARK)
        surfaces_frame.pack(side=tk.LEFT)

        tk.Label(surfaces_frame, text="Surfaces:", bg=self.BG_DARK, fg=self.TEXT_MUTED,
                font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(0, 10))

        surface_colors = {
            'Hard': '#3b82f6',
            'Clay': '#f97316',
            'Grass': '#22c55e',
            'Carpet': '#a855f7',
        }
        for surface in SURFACES:
            pill = tk.Label(surfaces_frame, text=surface, bg=surface_colors.get(surface, '#334155'),
                           fg='white', font=('Segoe UI', 7), padx=6, pady=1)
            pill.pack(side=tk.LEFT, padx=1)

        # Background updater status (middle)
        self.bg_status_frame = tk.Frame(footer, bg=self.BG_DARK)
        self.bg_status_frame.pack(side=tk.LEFT, padx=20, expand=True)

        self.bg_status_indicator = tk.Canvas(self.bg_status_frame, width=10, height=10,
                                             bg=self.BG_DARK, highlightthickness=0)
        self.bg_status_indicator.pack(side=tk.LEFT, padx=(0, 5))
        self.bg_status_indicator.create_oval(2, 2, 8, 8, fill=self.TEXT_MUTED, outline='', tags='dot')

        self.bg_status_label = tk.Label(self.bg_status_frame, text="Using GitHub data (daily updates)",
                                        bg=self.BG_DARK, fg=self.TEXT_MUTED, font=('Segoe UI', 8))
        self.bg_status_label.pack(side=tk.LEFT)

        # Data source info
        tk.Label(footer, text="Data: GitHub (ATP/WTA 2019+)  |  Pre-Match Only",
                bg=self.BG_DARK, fg=self.TEXT_MUTED,
                font=('Segoe UI', 9)).pack(side=tk.RIGHT)

    def _update_bg_status(self, text, is_updating=False):
        """Update the background updater status display."""
        try:
            self.bg_status_label.configure(text=text)
            # Update indicator color: green when updating, gray when idle
            color = self.ACCENT_SUCCESS if is_updating else self.TEXT_MUTED
            self.bg_status_indicator.delete('dot')
            self.bg_status_indicator.create_oval(2, 2, 8, 8, fill=color, outline='', tags='dot')
        except tk.TclError:
            pass  # Widget may have been destroyed

    def _on_close(self):
        """Handle window close - stop background updater and auto mode."""
        if hasattr(self, 'bg_updater') and self.bg_updater:
            self.bg_updater.stop()
        # Stop auto mode
        self.auto_mode_enabled = False
        if self.auto_mode_job:
            self.root.after_cancel(self.auto_mode_job)
        self.root.destroy()

    def _update_stats(self):
        """Update the stats display."""
        try:
            db_stats = db.get_database_stats()
            bet_stats = db.get_betting_stats()

            self.stats_labels['players'].configure(text=f"{db_stats.get('total_players', 0):,}")
            self.stats_labels['matches'].configure(text=f"{db_stats.get('total_matches', 0):,}")
            self.stats_labels['bets'].configure(text=str(bet_stats.get('total_bets', 0) or 0))

            # ROI with color coding
            roi = bet_stats.get('roi', 0) or 0
            roi_text = f"{roi:+.1f}%" if roi != 0 else "0.0%"

            # Color code ROI: green if positive, red if negative, grey if zero
            if roi > 0:
                roi_color = self.ACCENT_SUCCESS  # Green
            elif roi < 0:
                roi_color = self.ACCENT_DANGER   # Red
            else:
                roi_color = self.TEXT_MUTED      # Grey

            self.stats_labels['roi'].configure(text=roi_text, fg=roi_color)
        except tk.TclError:
            pass  # Widget may have been destroyed
        except Exception as e:
            print(f"Error updating stats: {e}")

    def _open_match_analyzer(self):
        try:
            MatchAnalyzerUI(self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Match Analyzer:\n{e}")

    def _open_bet_suggester(self):
        try:
            BetSuggesterUI(self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Bet Suggester:\n{e}")

    def _open_bet_tracker(self):
        try:
            BetTrackerUI(self.root, on_change_callback=self._update_stats)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Bet Tracker:\n{e}")

    def _open_player_lookup(self):
        try:
            PlayerLookupUI(self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Player Lookup:\n{e}")

    def _open_data_loader(self):
        try:
            DataLoaderUI(self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Data Loader:\n{e}")

    def _open_odds_manager(self):
        try:
            OddsManagerUI(self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Odds Manager:\n{e}")

    def _open_rankings(self):
        try:
            from rankings_ui import RankingsUI
            RankingsUI(self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Rankings:\n{e}")

    def _open_betfair_tennis(self):
        try:
            from betfair_capture import BetfairCaptureUI
            BetfairCaptureUI(self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Betfair Tennis:\n{e}")

    def _open_database(self):
        try:
            from database_ui import DatabaseUI
            DatabaseUI(self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Database:\n{e}")

    def _download_data(self):
        """Download Tennis Explorer data from GitHub - redirects to Refresh Data."""
        self._refresh_data()

    def _quick_import(self):
        """Quick import recent data (last 5 years)."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Quick Import")
        dialog.geometry("500x400")
        dialog.configure(bg=self.BG_DARK)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 500) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 400) // 2
        dialog.geometry(f"+{x}+{y}")

        content = tk.Frame(dialog, bg=self.BG_DARK, padx=30, pady=25)
        content.pack(fill=tk.BOTH, expand=True)

        tk.Label(content, text="Quick Import Data", font=('Segoe UI', 16, 'bold'),
                bg=self.BG_DARK, fg=self.TEXT_PRIMARY).pack(anchor='w')

        tk.Label(content, text="Import player and match data (recent 5 years)",
                font=('Segoe UI', 10), bg=self.BG_DARK, fg=self.TEXT_SECONDARY).pack(anchor='w', pady=(5, 20))

        # Log area
        log_frame = tk.Frame(content, bg=self.BG_CARD)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        log_text = tk.Text(log_frame, height=10, bg=self.BG_CARD, fg=self.TEXT_SECONDARY,
                          font=('Consolas', 9), wrap=tk.WORD, state=tk.DISABLED)
        log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def log_message(msg):
            log_text.configure(state=tk.NORMAL)
            log_text.insert(tk.END, msg + "\n")
            log_text.see(tk.END)
            log_text.configure(state=tk.DISABLED)
            dialog.update()

        progress = ttk.Progressbar(content, mode='determinate', length=350, maximum=100)
        progress.pack()

        def do_import():
            def import_thread():
                try:
                    from data_loader import DataLoader
                    from datetime import datetime
                    loader = DataLoader()

                    def update_progress(msg, pct=None):
                        dialog.after(0, lambda: log_message(msg))
                        if pct is not None:
                            dialog.after(0, lambda: progress.configure(value=pct))

                    loader.set_progress_callback(update_progress)

                    if not loader.check_data_exists():
                        update_progress("Data not found. Downloading first...")
                        loader.download_data()

                    current_year = datetime.now().year
                    start_year = 2019  # Only import players active since 2019

                    # Clean up old data files (before 2019)
                    update_progress("Cleaning up old data files...")
                    loader._cleanup_old_data()

                    # Clear existing database for fresh import
                    update_progress("Clearing existing database for fresh import...")
                    loader.db.clear_import_data()

                    # Get active player IDs from match files (2019+)
                    update_progress(f"Scanning matches for active players since {start_year}...")
                    active_player_ids = loader.get_player_ids_from_matches(start_year=start_year)
                    update_progress(f"Found {len(active_player_ids)} active players", 10)

                    # Load only active players
                    update_progress(f"Loading {len(active_player_ids)} active players...")
                    players = loader.load_players(player_ids=active_player_ids)
                    update_progress(f"Loaded {players} players", 30)

                    update_progress(f"Loading matches ({start_year}-{current_year})...")
                    matches = loader.load_matches(start_year=start_year)
                    update_progress(f"Loaded {matches} matches", 70)

                    update_progress("Loading current rankings...")
                    rankings = loader.load_current_rankings_only()
                    update_progress(f"Loaded {rankings} rankings", 85)

                    update_progress("Updating player rankings...")
                    loader.update_player_rankings()
                    update_progress("Computing surface stats...")
                    loader.compute_surface_stats()

                    update_progress(f"Import complete!", 100)
                    dialog.after(100, self._update_stats)

                except Exception as e:
                    dialog.after(0, lambda: log_message(f"Error: {e}"))

            thread = threading.Thread(target=import_thread, daemon=True)
            thread.start()

        btn_frame = tk.Frame(content, bg=self.BG_DARK)
        btn_frame.pack(fill=tk.X, pady=(15, 0))

        ModernButton(btn_frame, "Start Import", do_import, color=self.ACCENT_SUCCESS,
                    width=120, height=38, font_size=10).pack(side=tk.LEFT)

        ModernButton(btn_frame, "Close", dialog.destroy, color='#475569',
                    width=80, height=38, font_size=10).pack(side=tk.RIGHT)

    def _refresh_data(self):
        """Quick refresh - pull latest data from GitHub and update current year."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Refresh Data")
        dialog.geometry("500x400")
        dialog.configure(bg=self.BG_DARK)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 500) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 400) // 2
        dialog.geometry(f"+{x}+{y}")

        content = tk.Frame(dialog, bg=self.BG_DARK, padx=30, pady=25)
        content.pack(fill=tk.BOTH, expand=True)

        tk.Label(content, text="Refresh Data", font=('Segoe UI', 16, 'bold'),
                bg=self.BG_DARK, fg=self.TEXT_PRIMARY).pack(anchor='w')

        tk.Label(content, text="Download latest ATP/WTA/ITF data from Tennis Explorer (~15-20 minutes)",
                font=('Segoe UI', 10), bg=self.BG_DARK, fg=self.TEXT_SECONDARY).pack(anchor='w', pady=(5, 20))

        # Log area
        log_frame = tk.Frame(content, bg=self.BG_CARD)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        log_text = tk.Text(log_frame, height=10, bg=self.BG_CARD, fg=self.TEXT_SECONDARY,
                          font=('Consolas', 9), wrap=tk.WORD, state=tk.DISABLED)
        log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def log_message(msg):
            try:
                log_text.configure(state=tk.NORMAL)
                log_text.insert(tk.END, msg + "\n")
                log_text.see(tk.END)
                log_text.configure(state=tk.DISABLED)
            except tk.TclError:
                pass  # Dialog may have been closed

        progress = ttk.Progressbar(content, mode='indeterminate', length=350)
        progress.pack()

        # Track last logged percentage to avoid spam
        last_pct = [-1]

        def do_refresh():
            progress.start(10)

            def refresh_thread():
                try:
                    from data_loader import DataLoader
                    loader = DataLoader()

                    def update_progress(msg, pct=None):
                        # Only log significant progress changes (every 10%) or non-percentage messages
                        if pct is not None:
                            pct_int = int(pct // 10) * 10
                            if pct_int <= last_pct[0]:
                                return  # Skip duplicate percentage updates
                            last_pct[0] = pct_int
                        dialog.after(0, lambda m=msg: log_message(m))

                    loader.set_progress_callback(update_progress)

                    update_progress("Starting quick refresh...")
                    result = loader.quick_refresh()

                    if result['success']:
                        update_progress(f"Refresh complete!")
                        update_progress(f"  Matches imported: {result.get('matches_updated', 0)}")
                        if result.get('matches_skipped', 0) > 0:
                            update_progress(f"  Matches skipped: {result.get('matches_skipped', 0)} (unknown players)")
                        update_progress(f"  Players in database: {result.get('players_in_db', result.get('players', 0))}")
                        # Record the refresh timestamp
                        db.set_last_refresh('full')
                        dialog.after(100, self._update_stats)
                        dialog.after(100, self._update_last_refresh_display)
                    else:
                        update_progress(f"Refresh failed: {result.get('message', 'Unknown error')}")

                except Exception as e:
                    dialog.after(0, lambda: log_message(f"Error: {e}"))
                finally:
                    dialog.after(0, progress.stop)

            thread = threading.Thread(target=refresh_thread, daemon=True)
            thread.start()

        btn_frame = tk.Frame(content, bg=self.BG_DARK)
        btn_frame.pack(fill=tk.X, pady=(15, 0))

        ModernButton(btn_frame, "Full Refresh", do_refresh, color=self.ACCENT_SUCCESS,
                    width=120, height=38, font_size=10).pack(side=tk.LEFT)

        ModernButton(btn_frame, "Close", dialog.destroy, color='#475569',
                    width=80, height=38, font_size=10).pack(side=tk.RIGHT)

    def _quick_refresh_7_days(self):
        """Quick refresh - only fetch matches from the last 7 days.

        This is much faster than full refresh as it only scrapes recent days.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Quick Refresh (7 Days)")
        dialog.geometry("500x400")
        dialog.configure(bg=self.BG_DARK)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 500) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 400) // 2
        dialog.geometry(f"+{x}+{y}")

        content = tk.Frame(dialog, bg=self.BG_DARK, padx=30, pady=25)
        content.pack(fill=tk.BOTH, expand=True)

        tk.Label(content, text="Quick Refresh (7 Days)", font=('Segoe UI', 16, 'bold'),
                bg=self.BG_DARK, fg=self.TEXT_PRIMARY).pack(anchor='w')

        tk.Label(content, text="Fetch only matches from the last 7 days (~2-3 minutes)",
                font=('Segoe UI', 10), bg=self.BG_DARK, fg=self.TEXT_SECONDARY).pack(anchor='w', pady=(5, 20))

        # Log area
        log_frame = tk.Frame(content, bg=self.BG_CARD)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        log_text = tk.Text(log_frame, height=10, bg=self.BG_CARD, fg=self.TEXT_SECONDARY,
                          font=('Consolas', 9), wrap=tk.WORD, state=tk.DISABLED)
        log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def log_message(msg):
            try:
                log_text.configure(state=tk.NORMAL)
                log_text.insert(tk.END, msg + "\n")
                log_text.see(tk.END)
                log_text.configure(state=tk.DISABLED)
            except tk.TclError:
                pass  # Dialog may have been closed

        progress = ttk.Progressbar(content, mode='indeterminate', length=350)
        progress.pack()

        def do_quick_refresh():
            progress.start(10)

            def refresh_thread():
                try:
                    from github_data_loader import GitHubDataLoader
                    loader = GitHubDataLoader()

                    def update_progress(msg, pct=None):
                        dialog.after(0, lambda m=msg: log_message(m))

                    loader.set_progress_callback(update_progress)

                    update_progress("Starting quick refresh (last 7 days only)...")
                    result = loader.quick_refresh_recent(days=7)

                    if result['success']:
                        update_progress(f"\nQuick refresh complete!")
                        update_progress(f"  Matches found: {result.get('matches', 0)}")
                        update_progress(f"  Matches imported: {result.get('matches_imported', 0)}")
                        if result.get('matches_skipped', 0) > 0:
                            update_progress(f"  Matches skipped: {result.get('matches_skipped', 0)} (unknown players)")
                        # Record the refresh timestamp
                        db.set_last_refresh('quick')
                        dialog.after(100, self._update_stats)
                        dialog.after(100, self._update_last_refresh_display)
                    else:
                        update_progress(f"\nQuick refresh failed")

                except Exception as e:
                    dialog.after(0, lambda: log_message(f"Error: {e}"))
                finally:
                    dialog.after(0, progress.stop)

            thread = threading.Thread(target=refresh_thread, daemon=True)
            thread.start()

        btn_frame = tk.Frame(content, bg=self.BG_DARK)
        btn_frame.pack(fill=tk.X, pady=(15, 0))

        ModernButton(btn_frame, "Start Refresh", do_quick_refresh, color='#06b6d4',
                    width=130, height=38, font_size=10).pack(side=tk.LEFT)

        ModernButton(btn_frame, "Close", dialog.destroy, color='#475569',
                    width=80, height=38, font_size=10).pack(side=tk.RIGHT)

    def _add_upcoming_match(self):
        """Quick add an upcoming match."""
        self._open_bet_suggester()  # Bet suggester has add match functionality

    def _open_te_import(self):
        """Open Tennis Explorer import dialog."""
        try:
            open_te_import_dialog(self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open TE Import:\n{e}")

    def _open_match_assignment(self):
        """Open Match Assignment dialog to fix wrong player assignments."""
        try:
            open_match_assignment(self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Match Assignment:\n{e}")

    def _clear_all_matches(self):
        """Clear all matches from the database."""
        # Get count first
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM matches')
            count = cursor.fetchone()[0]

        if count == 0:
            messagebox.showinfo("No Matches", "There are no matches to clear.")
            return

        # Confirm deletion
        result = messagebox.askyesno(
            "Clear All Matches",
            f"Are you sure you want to delete ALL {count} matches?\n\n"
            "This cannot be undone.",
            icon='warning'
        )

        if not result:
            return

        # Delete all matches
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM matches')
            conn.commit()

        messagebox.showinfo("Matches Cleared", f"Deleted {count} matches.")
        self._update_stats()

    def _auto_startup_tasks(self):
        """Run startup tasks: backfill model tags and fetch Betfair matches."""
        def startup_thread():
            try:
                # Backfill model tags for any bets missing them
                self.root.after(0, lambda: self._update_bg_status("Checking bet model tags...", True))
                backfilled = db.backfill_model_tags()
                if backfilled > 0:
                    print(f"Backfilled model tags for {backfilled} bets")
                    self.root.after(0, lambda: self._update_bg_status(f"Updated {backfilled} bet model tags", False))
                else:
                    self.root.after(0, lambda: self._update_bg_status("Ready", False))

                # Fetch Betfair matches
                time.sleep(0.5)  # Small delay to ensure UI updates
                capturer = BetfairTennisCapture()
                if capturer.app_key and capturer.username:
                    self.root.after(0, lambda: self._update_bg_status("Fetching Betfair matches...", True))
                    matches = capturer.capture_all_tennis_matches(hours_ahead=48)
                    if matches:
                        count = capturer.save_to_database(matches)
                        self.root.after(0, lambda: self._update_bg_status(
                            f"Loaded {count} matches from Betfair", False))
                    else:
                        self.root.after(0, lambda: self._update_bg_status(
                            "No Betfair matches found", False))
                else:
                    self.root.after(0, lambda: self._update_bg_status(
                        "Betfair credentials not configured", False))
            except Exception as e:
                print(f"Startup tasks error: {e}")
                self.root.after(0, lambda: self._update_bg_status(f"Startup: {str(e)[:30]}", False))

        threading.Thread(target=startup_thread, daemon=True).start()

    def _toggle_auto_mode(self):
        """Toggle automatic data capture and bet tracking mode."""
        self.auto_mode_enabled = not self.auto_mode_enabled

        if self.auto_mode_enabled:
            # Update UI to show enabled
            self.auto_mode_status.configure(text="Auto: ON", fg=self.ACCENT_SUCCESS)
            self.auto_mode_btn.label.configure(text="Stop Auto")
            self._update_bg_status("Auto mode enabled - running now...", True)

            # Run immediately, then schedule next run
            self._run_auto_cycle()
        else:
            # Cancel scheduled job
            if self.auto_mode_job:
                self.root.after_cancel(self.auto_mode_job)
                self.auto_mode_job = None
            self.next_auto_run = None

            # Update UI to show disabled
            self.auto_mode_status.configure(text="Auto: OFF", fg=self.TEXT_MUTED)
            self.auto_mode_btn.label.configure(text="Auto Mode")
            self._update_bg_status("Auto mode disabled", False)

    def _run_auto_cycle(self):
        """Execute one auto-mode cycle: capture odds, analyze, add bets."""
        if not self.auto_mode_enabled:
            return

        def auto_cycle_thread():
            try:
                # Step 1: Capture Betfair odds
                self.root.after(0, lambda: self._update_bg_status("Auto: Fetching Betfair odds...", True))
                capturer = BetfairTennisCapture()
                if capturer.app_key and capturer.username:
                    matches = capturer.capture_all_tennis_matches(hours_ahead=48)
                    if matches:
                        count = capturer.save_to_database(matches)
                        self.root.after(0, lambda: self._update_bg_status(f"Auto: Captured {count} matches", True))
                    else:
                        self.root.after(0, lambda: self._update_bg_status("Auto: No Betfair matches found", True))
                else:
                    self.root.after(0, lambda: self._update_bg_status("Auto: Betfair not configured", True))
                    # Continue anyway to process existing matches

                # Small delay between steps
                time.sleep(1)

                # Step 2: Find value bets
                self.root.after(0, lambda: self._update_bg_status("Auto: Analyzing matches...", True))
                from bet_suggester import BetSuggester
                suggester = BetSuggester()
                value_bets = suggester.get_top_value_bets()

                if value_bets:
                    # Step 3: Add bets to tracker (without confirmation)
                    self.root.after(0, lambda: self._update_bg_status(f"Auto: Found {len(value_bets)} value bets, adding...", True))
                    added = self._auto_add_bets_to_tracker(value_bets)
                    self.root.after(0, lambda: self._update_bg_status(f"Auto: Added {added} bets to tracker", True))
                else:
                    self.root.after(0, lambda: self._update_bg_status("Auto: No value bets found", True))

                # Update stats
                self.root.after(100, self._update_stats)

                # Calculate next run time
                time.sleep(1)
                if self.auto_mode_enabled:
                    next_time = datetime.now() + timedelta(milliseconds=self.auto_mode_interval)
                    self.next_auto_run = next_time
                    next_str = next_time.strftime("%H:%M")
                    self.root.after(0, lambda: self._update_bg_status(f"Auto: Next run at {next_str}", False))
                    self.root.after(0, lambda: self.auto_mode_status.configure(
                        text=f"Auto: ON (next {next_str})", fg=self.ACCENT_SUCCESS))

            except Exception as e:
                print(f"Auto cycle error: {e}")
                self.root.after(0, lambda: self._update_bg_status(f"Auto error: {str(e)[:40]}", False))

            finally:
                # Schedule next run if still enabled
                if self.auto_mode_enabled:
                    self.auto_mode_job = self.root.after(self.auto_mode_interval, self._run_auto_cycle)

        threading.Thread(target=auto_cycle_thread, daemon=True).start()

    def _auto_add_bets_to_tracker(self, value_bets: list) -> int:
        """Add value bets to the tracker automatically (no confirmation dialog).

        Returns the number of bets added.
        """
        added = 0
        added_this_batch = set()

        for bet_info in value_bets:
            try:
                match = bet_info.get('match_info', {})
                match_description = f"{match.get('player1', '')} vs {match.get('player2', '')}"
                selection = bet_info.get('player', '')
                match_date = match.get('date', '')
                tournament = match.get('tournament', '')

                # Check for duplicate within this batch
                batch_key = (tournament, match_description, selection)
                if batch_key in added_this_batch:
                    continue

                # Check for duplicate in database
                if db.check_duplicate_bet(match_description, selection, match_date, tournament):
                    continue

                # Prepare bet data
                db_bet = {
                    'match_date': match_date or datetime.now().strftime("%Y-%m-%d"),
                    'tournament': match.get('tournament', ''),
                    'match_description': match_description,
                    'player1': match.get('player1', ''),
                    'player2': match.get('player2', ''),
                    'market': 'Match Winner',
                    'selection': selection,
                    'stake': bet_info.get('recommended_units', 1),
                    'odds': bet_info.get('odds'),
                    'our_probability': bet_info.get('our_probability'),
                    'implied_probability': bet_info.get('implied_probability'),
                    'ev_at_placement': bet_info.get('expected_value'),
                    'notes': f"[AUTO] Surface: {match.get('surface', '')} | Kelly: {bet_info.get('kelly_stake_pct', 0):.1f}%",
                }

                # Calculate model and skip if doesn't qualify for any
                model = calculate_bet_model(
                    db_bet.get('our_probability', 0.5),
                    db_bet.get('implied_probability', 0.5),
                    db_bet.get('tournament', ''),
                    db_bet.get('odds'),
                    None  # No factor scores in auto mode
                )
                if model == "None" or not model:
                    continue
                db_bet['model'] = model

                db.add_bet(db_bet)
                added += 1
                added_this_batch.add(batch_key)

            except Exception as e:
                print(f"Error adding auto bet: {e}")
                continue

        return added

    def run(self):
        """Run the main application."""
        self.root.mainloop()


def main():
    app = MainApplication()
    app.run()


if __name__ == "__main__":
    main()
