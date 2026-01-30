"""
Local Monitor with Discord Bot - Monitors bets and responds to commands.
Commands: !inplay, !pending, !stats, !refresh
"""

import json
import time
import re
import urllib.request
import urllib.error
import os
import sys
import asyncio
import threading
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

import discord
from discord.ext import commands, tasks


# ============================================================================
# LOAD CREDENTIALS
# ============================================================================

def get_app_directory() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def load_credentials() -> Dict:
    app_dir = get_app_directory()
    creds_path = os.path.join(app_dir, 'credentials.json')
    if os.path.exists(creds_path):
        with open(creds_path, 'r') as f:
            return json.load(f)
    return {}

CREDS = load_credentials()
BETFAIR_APP_KEY = CREDS.get('betfair_app_key', '')
BETFAIR_USERNAME = CREDS.get('betfair_username', '')
BETFAIR_PASSWORD = CREDS.get('betfair_password', '')
SUPABASE_URL = CREDS.get('supabase_url', '')
SUPABASE_KEY = CREDS.get('supabase_key', '')
DISCORD_BOT_TOKEN = CREDS.get('discord_bot_token', '')
DISCORD_CHANNEL_ID = 1462470788602007787  # Channel for alerts

CHECK_INTERVAL = 30

# Local SQLite database path
LOCAL_DB_PATH = r"C:\Users\Public\Documents\Tennis Betting System\data\tennis_betting.db"


def update_local_db(match_description: str, selection: str, result: str, profit_loss: float):
    """Update the local SQLite database with bet result."""
    if not os.path.exists(LOCAL_DB_PATH):
        print(f"[{timestamp()}] Local DB not found: {LOCAL_DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(LOCAL_DB_PATH)
        cursor = conn.cursor()

        # Find the bet by match_description and selection (pending bets have no result)
        cursor.execute("""
            UPDATE bets
            SET result = ?, profit_loss = ?, settled_at = ?, in_progress = 0
            WHERE match_description = ? AND selection = ? AND result IS NULL
        """, (result, profit_loss, datetime.now().isoformat(), match_description, selection))

        if cursor.rowcount > 0:
            conn.commit()
            print(f"[{timestamp()}] Local DB updated: {match_description} - {result}")
        else:
            print(f"[{timestamp()}] Local DB: No matching pending bet found for {match_description}")

        conn.close()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"[{timestamp()}] Local DB error: {e}")
        return False


def sync_live_status_from_local_db():
    """Read in_progress status from local SQLite database and sync to Supabase.

    The local bet tracker is the source of truth for which bets are in-play.
    This function reads the local DB and updates Supabase's is_live field accordingly.
    """
    if not os.path.exists(LOCAL_DB_PATH):
        return

    try:
        conn = sqlite3.connect(LOCAL_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all pending bets with their in_progress status from local DB
        cursor.execute("""
            SELECT id, in_progress, match_description
            FROM bets
            WHERE result IS NULL
        """)
        local_bets = {row['id']: dict(row) for row in cursor.fetchall()}
        conn.close()

        if not local_bets:
            return

        # Get current Supabase pending bets
        cloud_bets = supabase.get_pending_bets()
        if not cloud_bets:
            return

        # Sync: update Supabase is_live to match local in_progress
        synced = 0
        for cloud_bet in cloud_bets:
            bet_id = cloud_bet.get('id')
            if bet_id not in local_bets:
                continue

            local_in_progress = bool(local_bets[bet_id].get('in_progress', 0))
            cloud_is_live = bool(cloud_bet.get('is_live', False))

            if local_in_progress != cloud_is_live:
                supabase.mark_live(bet_id, local_in_progress)
                status_str = "LIVE" if local_in_progress else "NOT LIVE"
                print(f"[{timestamp()}] Sync: {local_bets[bet_id]['match_description']} -> {status_str}")
                synced += 1

        if synced > 0:
            print(f"[{timestamp()}] Synced {synced} live status change(s) from local DB")

    except Exception as e:
        print(f"[{timestamp()}] Live status sync error: {e}")


# ============================================================================
# BETFAIR CLIENT
# ============================================================================

class BetfairClient:
    LOGIN_URL = "https://identitysso.betfair.com/api/login"
    API_URL = "https://api.betfair.com/exchange/betting/rest/v1.0/"

    def __init__(self):
        self.session_token = None
        self.app_key = BETFAIR_APP_KEY

    def login(self) -> bool:
        if not all([BETFAIR_APP_KEY, BETFAIR_USERNAME, BETFAIR_PASSWORD]):
            return False
        headers = {
            'X-Application': BETFAIR_APP_KEY,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        data = f"username={BETFAIR_USERNAME}&password={BETFAIR_PASSWORD}".encode('utf-8')
        try:
            req = urllib.request.Request(self.LOGIN_URL, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                if result.get('status') == 'SUCCESS':
                    self.session_token = result.get('token')
                    return True
        except Exception as e:
            print(f"[{timestamp()}] Betfair login error: {e}")
        return False

    def api_request(self, endpoint: str, params: dict) -> Optional[dict]:
        if not self.session_token:
            if not self.login():
                return None
        headers = {
            'X-Application': self.app_key,
            'X-Authentication': self.session_token,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        url = self.API_URL + endpoint + "/"
        try:
            data = json.dumps(params).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                self.session_token = None
                return self.api_request(endpoint, params)
        except Exception:
            pass
        return None

    def get_inplay_tennis(self) -> List[Dict]:
        params = {
            "filter": {
                "eventTypeIds": ["2"],
                "inPlayOnly": True,
                "marketTypeCodes": ["MATCH_ODDS"]
            },
            "marketProjection": ["RUNNER_DESCRIPTION", "EVENT"],
            "maxResults": "200"
        }
        result = self.api_request("listMarketCatalogue", params)
        if not result:
            return []
        markets = []
        for market in result:
            runners = market.get('runners', [])
            if len(runners) == 2:
                sorted_runners = sorted(runners, key=lambda r: r.get('sortPriority', 0))
                markets.append({
                    'market_id': market.get('marketId'),
                    'event_name': market.get('event', {}).get('name', ''),
                    'player1': sorted_runners[0].get('runnerName', ''),
                    'player2': sorted_runners[1].get('runnerName', ''),
                    'selection_ids': {
                        sorted_runners[0].get('runnerName', ''): sorted_runners[0].get('selectionId'),
                        sorted_runners[1].get('runnerName', ''): sorted_runners[1].get('selectionId'),
                    }
                })
        return markets

    def get_market_result(self, market_id: str) -> Optional[Dict]:
        params = {
            "marketIds": [market_id],
            "priceProjection": {"priceData": ["EX_BEST_OFFERS"]}
        }
        result = self.api_request("listMarketBook", params)
        if result and len(result) > 0:
            market = result[0]
            return {
                'status': market.get('status'),
                'inplay': market.get('inplay'),
                'runners': market.get('runners', [])
            }
        return None

    def get_all_tennis_markets(self) -> List[Dict]:
        """Get ALL recent tennis match odds markets (in-play, pre-match, and recently closed)."""
        params = {
            "filter": {
                "eventTypeIds": ["2"],
                "marketTypeCodes": ["MATCH_ODDS"]
            },
            "marketProjection": ["RUNNER_DESCRIPTION", "EVENT"],
            "maxResults": "1000"
        }
        result = self.api_request("listMarketCatalogue", params)
        if not result:
            return []
        markets = []
        for market in result:
            runners = market.get('runners', [])
            if len(runners) == 2:
                sorted_runners = sorted(runners, key=lambda r: r.get('sortPriority', 0))
                markets.append({
                    'market_id': market.get('marketId'),
                    'event_name': market.get('event', {}).get('name', ''),
                    'player1': sorted_runners[0].get('runnerName', ''),
                    'player2': sorted_runners[1].get('runnerName', ''),
                    'selection_ids': {
                        sorted_runners[0].get('runnerName', ''): sorted_runners[0].get('selectionId'),
                        sorted_runners[1].get('runnerName', ''): sorted_runners[1].get('selectionId'),
                    }
                })
        return markets

    def get_market_runners(self, market_id: str) -> Optional[Dict]:
        """Get runner name to selectionId mapping for a specific market."""
        params = {
            "filter": {"marketIds": [market_id]},
            "marketProjection": ["RUNNER_DESCRIPTION"]
        }
        result = self.api_request("listMarketCatalogue", params)
        if result and len(result) > 0:
            runners = result[0].get('runners', [])
            selection_ids = {}
            for runner in runners:
                name = runner.get('runnerName', '')
                sid = runner.get('selectionId')
                if name and sid:
                    selection_ids[name] = sid
            return selection_ids if selection_ids else None
        return None


# ============================================================================
# SUPABASE CLIENT
# ============================================================================

class SupabaseClient:
    def __init__(self):
        self.url = SUPABASE_URL
        self.key = SUPABASE_KEY
        self.headers = {
            'apikey': self.key,
            'Authorization': f'Bearer {self.key}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }

    def is_configured(self) -> bool:
        return bool(self.url and self.key)

    def _request(self, endpoint: str, method: str = 'GET', data: Dict = None) -> Optional[any]:
        if not self.is_configured():
            return None
        url = f"{self.url}/rest/v1/{endpoint}"
        try:
            body = json.dumps(data).encode('utf-8') if data else None
            req = urllib.request.Request(url, data=body, headers=self.headers, method=method)
            with urllib.request.urlopen(req, timeout=10) as response:
                response_data = response.read().decode('utf-8')
                if response_data:
                    return json.loads(response_data)
                return {}
        except Exception:
            pass
        return None

    def get_pending_bets(self) -> List[Dict]:
        result = self._request('pending_bets?result=is.null&order=match_date.asc')
        return result if isinstance(result, list) else []

    def get_live_bets(self) -> List[Dict]:
        """Get bets marked as is_live=true in Supabase."""
        result = self._request('pending_bets?result=is.null&is_live=eq.true&order=match_date.asc')
        return result if isinstance(result, list) else []

    def get_settled_today(self) -> List[Dict]:
        today = datetime.now().strftime('%Y-%m-%d')
        result = self._request(f'pending_bets?finished_at=gte.{today}&order=finished_at.desc')
        return result if isinstance(result, list) else []

    def mark_live(self, bet_id: int, is_live: bool, market_id: str = None, selection_ids: Dict = None):
        data = {'is_live': is_live, 'updated_at': datetime.utcnow().isoformat()}
        if market_id:
            data['market_id'] = market_id
        if selection_ids:
            data['selection_ids'] = json.dumps(selection_ids)
        self._request(f'pending_bets?id=eq.{bet_id}', method='PATCH', data=data)

    def mark_finished(self, bet_id: int, result: str, profit_loss: float):
        self._request(
            f'pending_bets?id=eq.{bet_id}',
            method='PATCH',
            data={
                'result': result,
                'profit_loss': profit_loss,
                'is_live': False,
                'finished_at': datetime.utcnow().isoformat()
            }
        )

    def upsert_bet(self, bet_data: Dict):
        """Upsert a bet to Supabase (insert or update on id conflict)."""
        headers = dict(self.headers)
        headers['Prefer'] = 'resolution=merge-duplicates'
        url = f"{self.url}/rest/v1/pending_bets?on_conflict=id"
        try:
            body = json.dumps(bet_data).encode('utf-8')
            req = urllib.request.Request(url, data=body, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=10) as response:
                return True
        except Exception:
            return False


def sync_local_to_cloud():
    """Sync all local pending bets to Supabase so Discord always has current data."""
    if not os.path.exists(LOCAL_DB_PATH):
        return
    try:
        conn = sqlite3.connect(LOCAL_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, match_date, tournament, match_description, selection,
                   odds, stake, model, our_probability, result, profit_loss, in_progress
            FROM bets WHERE result IS NULL
        """)
        local_bets = [dict(row) for row in cursor.fetchall()]
        conn.close()

        synced = 0
        for bet in local_bets:
            cloud_bet = {
                'id': bet['id'],
                'match_date': bet.get('match_date'),
                'tournament': bet.get('tournament'),
                'match_description': bet.get('match_description'),
                'selection': bet.get('selection'),
                'odds': bet.get('odds'),
                'stake': bet.get('stake'),
                'model': bet.get('model'),
                'our_probability': bet.get('our_probability'),
                'result': bet.get('result'),
                'profit_loss': bet.get('profit_loss'),
                'is_live': bool(bet.get('in_progress', 0)),
                'updated_at': datetime.utcnow().isoformat()
            }
            if supabase.upsert_bet(cloud_bet):
                synced += 1

        if synced > 0:
            print(f"[{timestamp()}] Synced {synced} local bets to cloud")
    except Exception as e:
        print(f"[{timestamp()}] Sync to cloud error: {e}")


# ============================================================================
# DISCORD BOT ALERTS (sends to channel via bot)
# ============================================================================

# Queue for alerts to be sent by the bot
alert_queue = []


def queue_live_alert(bet: Dict):
    """Queue a live alert to be sent by the bot."""
    embed = discord.Embed(
        title=f"\U0001F3BE LIVE: {bet.get('match_description', 'Unknown')}",
        color=0x3498db,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Selection", value=f"**{bet.get('selection', '?')}**", inline=True)
    embed.add_field(name="Odds", value=f"**{bet.get('odds', 0):.2f}**", inline=True)
    embed.add_field(name="Stake", value=f"**{bet.get('stake', 0):.1f}u**", inline=True)
    embed.add_field(name="Model", value=bet.get('model', '?'), inline=True)
    if bet.get('tournament'):
        embed.add_field(name="Tournament", value=bet.get('tournament'), inline=True)
    embed.set_footer(text="Tennis Betting Monitor")
    alert_queue.append(embed)


def queue_result_alert(bet: Dict, result: str, profit_loss: float):
    """Queue a result alert to be sent by the bot."""
    if result == 'Win':
        emoji = "\u2705"  # ✅
        color = 0x22c55e
        pl_str = f"+{profit_loss:.2f}u"
    else:
        emoji = "\u274C"  # ❌
        color = 0xef4444
        pl_str = f"{profit_loss:.2f}u"

    embed = discord.Embed(
        title=f"{emoji} {result.upper()}: {bet.get('match_description', 'Unknown')}",
        color=color,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Selection", value=bet.get('selection', '?'), inline=True)
    embed.add_field(name="Odds", value=f"{bet.get('odds', 0):.2f}", inline=True)
    embed.add_field(name="P/L", value=f"**{pl_str}**", inline=True)
    embed.set_footer(text="Tennis Betting Monitor")
    alert_queue.append(embed)


async def send_queued_alerts():
    """Send all queued alerts to the channel."""
    global alert_queue
    if not alert_queue:
        return

    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if not channel:
        print(f"[{timestamp()}] Could not find channel {DISCORD_CHANNEL_ID}")
        return

    for embed in alert_queue:
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"[{timestamp()}] Failed to send alert: {e}")

    alert_queue = []


# Keep old function names for compatibility but use queue
def send_live_alert(bet: Dict):
    queue_live_alert(bet)


def send_result_alert(bet: Dict, result: str, profit_loss: float):
    queue_result_alert(bet, result, profit_loss)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def timestamp() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def normalize_name(name: str) -> str:
    """Normalize a player name for matching."""
    if not name:
        return ''
    # Remove common suffixes, accents, and normalize
    name = name.lower().strip()
    # Remove Jr., Sr., etc.
    for suffix in [' jr.', ' jr', ' sr.', ' sr', ' ii', ' iii', ' iv']:
        name = name.replace(suffix, '')
    # Handle common accent substitutions
    replacements = {
        'á': 'a', 'à': 'a', 'ä': 'a', 'â': 'a', 'ã': 'a',
        'é': 'e', 'è': 'e', 'ë': 'e', 'ê': 'e',
        'í': 'i', 'ì': 'i', 'ï': 'i', 'î': 'i',
        'ó': 'o', 'ò': 'o', 'ö': 'o', 'ô': 'o', 'õ': 'o',
        'ú': 'u', 'ù': 'u', 'ü': 'u', 'û': 'u',
        'ñ': 'n', 'ç': 'c', 'ß': 'ss',
        '-': ' ', "'": '', '.': ''
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    return name

def players_match(bet_p1: str, bet_p2: str, market_p1: str, market_p2: str) -> bool:
    """Check if bet players match market players (in either order)."""
    # Normalize all names
    bet_p1_norm = normalize_name(bet_p1)
    bet_p2_norm = normalize_name(bet_p2)
    market_p1_norm = normalize_name(market_p1)
    market_p2_norm = normalize_name(market_p2)

    # Get last names
    bet_p1_last = bet_p1_norm.split()[-1] if bet_p1_norm else ''
    bet_p2_last = bet_p2_norm.split()[-1] if bet_p2_norm else ''
    market_p1_last = market_p1_norm.split()[-1] if market_p1_norm else ''
    market_p2_last = market_p2_norm.split()[-1] if market_p2_norm else ''

    # Try exact last name match first
    if (bet_p1_last == market_p1_last and bet_p2_last == market_p2_last) or \
       (bet_p1_last == market_p2_last and bet_p2_last == market_p1_last):
        return True

    # Try partial match (one name contains the other) for hyphenated names like "De Minaur"
    def partial_match(name1: str, name2: str) -> bool:
        return name1 in name2 or name2 in name1 if name1 and name2 else False

    if (partial_match(bet_p1_last, market_p1_last) and partial_match(bet_p2_last, market_p2_last)) or \
       (partial_match(bet_p1_last, market_p2_last) and partial_match(bet_p2_last, market_p1_last)):
        return True

    return False


def find_market_for_bet(bet: Dict, markets: List[Dict]) -> Optional[Dict]:
    match_desc = bet.get('match_description', '')
    if ' vs ' not in match_desc:
        return None
    parts = match_desc.split(' vs ')
    bet_p1 = parts[0].strip()
    bet_p2 = parts[1].strip()
    for market in markets:
        if players_match(bet_p1, bet_p2, market.get('player1', ''), market.get('player2', '')):
            return market
    return None


def determine_result(bet: Dict, market_info: Dict, market_result: Dict) -> Optional[tuple]:
    runners = market_result.get('runners', [])
    selection_ids = market_info.get('selection_ids', {})
    winner_name = None
    for runner in runners:
        if runner.get('status') == 'WINNER':
            sel_id = runner.get('selectionId')
            for name, sid in selection_ids.items():
                if sid == sel_id:
                    winner_name = name
                    break
            break
    if not winner_name:
        return None
    selection = bet.get('selection', '')
    selection_last = selection.split()[-1].lower() if selection else ''
    winner_last = winner_name.split()[-1].lower() if winner_name else ''
    print(f"[{timestamp()}] Settlement detail: selection='{selection}' (last='{selection_last}'), winner='{winner_name}' (last='{winner_last}')")
    if selection_last == winner_last:
        result = 'Win'
        profit = bet.get('stake', 0) * (bet.get('odds', 0) - 1) * 0.95
    else:
        result = 'Loss'
        profit = -bet.get('stake', 0)
    return (result, profit)


def get_selection_ids_for_bet(bet: Dict) -> Optional[Dict]:
    """Get selection_ids mapping from Supabase bet data or fetch from Betfair.

    Returns dict of {runner_name: selectionId} or None.
    """
    # Try stored selection_ids from Supabase
    sel_ids_raw = bet.get('selection_ids')
    if sel_ids_raw:
        if isinstance(sel_ids_raw, str):
            try:
                selection_ids = json.loads(sel_ids_raw)
                if selection_ids:
                    print(f"[{timestamp()}] Using stored selection_ids for {bet.get('match_description')}")
                    return selection_ids
            except (json.JSONDecodeError, TypeError):
                pass
        elif isinstance(sel_ids_raw, dict) and sel_ids_raw:
            print(f"[{timestamp()}] Using stored selection_ids for {bet.get('match_description')}")
            return sel_ids_raw

    # Fallback: fetch from Betfair API
    market_id = bet.get('market_id')
    if market_id:
        print(f"[{timestamp()}] Fetching selection_ids from Betfair for {bet.get('match_description')}")
        fetched = betfair.get_market_runners(market_id)
        if fetched:
            return fetched

    print(f"[{timestamp()}] WARNING: No selection_ids available for {bet.get('match_description')}")
    return None


# ============================================================================
# TENNIS EXPLORER RESULTS CHECKER
# ============================================================================

def fetch_completed_results(days_back: int = 2) -> List[Dict]:
    """Fetch recent completed match results from Tennis Explorer.

    Returns list of dicts with 'winner_name' and 'loser_name' keys.
    Checks today and yesterday across all tour types.
    """
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    })

    all_results = []
    tour_types = ['atp-single', 'wta-single', 'itf-men-single', 'itf-women-single']

    for day_offset in range(days_back):
        date = datetime.now() - timedelta(days=day_offset)
        for tour_type in tour_types:
            url = f"https://www.tennisexplorer.com/results/?type={tour_type}&year={date.year}&month={date.month:02d}&day={date.day:02d}"
            try:
                response = session.get(url, timeout=15)
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')

                for table in soup.select('table'):
                    rows = table.select('tr')
                    i = 0
                    while i < len(rows):
                        row = rows[i]
                        row_class = row.get('class', [])

                        # Match rows come in pairs - first row has class 'bott'
                        if 'bott' in row_class:
                            p1_link = row.select_one('a[href*="/player/"]')
                            if p1_link and i + 1 < len(rows):
                                p2_link = rows[i + 1].select_one('a[href*="/player/"]')
                                if p2_link:
                                    try:
                                        p1_name = re.sub(r'\(\d+\)$', '', p1_link.get_text(strip=True)).strip()
                                        p2_name = re.sub(r'\(\d+\)$', '', p2_link.get_text(strip=True)).strip()

                                        # Skip doubles
                                        if '/' in p1_name or '/' in p2_name:
                                            i += 2
                                            continue

                                        # Get set scores to determine winner
                                        p1_scores = [c.get_text(strip=True) for c in row.select('td') if re.match(r'^\d{1,2}$', c.get_text(strip=True))]
                                        p2_scores = [c.get_text(strip=True) for c in rows[i + 1].select('td') if re.match(r'^\d{1,2}$', c.get_text(strip=True))]

                                        p1_sets = int(p1_scores[0]) if p1_scores and p1_scores[0].isdigit() else 0
                                        p2_sets = int(p2_scores[0]) if p2_scores and p2_scores[0].isdigit() else 0

                                        if p1_sets > p2_sets:
                                            all_results.append({'winner_name': p1_name, 'loser_name': p2_name})
                                        elif p2_sets > p1_sets:
                                            all_results.append({'winner_name': p2_name, 'loser_name': p1_name})
                                        # If tied sets (walkover/retirement), skip - can't determine winner reliably

                                        i += 2
                                        continue
                                    except Exception:
                                        pass
                        i += 1

                time.sleep(0.3)  # Be respectful to TE servers
            except Exception as e:
                print(f"[{timestamp()}] TE fetch error ({tour_type}): {e}")
                continue

    print(f"[{timestamp()}] Fetched {len(all_results)} completed results from Tennis Explorer")
    return all_results


def find_result_for_bet(bet: Dict, results: List[Dict]) -> Optional[str]:
    """Check if a pending bet's match appears in completed results.

    Returns the winner's name if found, None otherwise.
    """
    match_desc = bet.get('match_description', '')
    if ' vs ' not in match_desc:
        return None

    parts = match_desc.split(' vs ')
    bet_p1 = parts[0].strip()
    bet_p2 = parts[1].strip()

    for result in results:
        winner = result['winner_name']
        loser = result['loser_name']
        if players_match(bet_p1, bet_p2, winner, loser):
            return winner

    return None


def settle_from_result(bet: Dict, winner_name: str) -> Optional[tuple]:
    """Determine Win/Loss by comparing bet selection to the match winner."""
    selection = bet.get('selection', '')
    selection_last = selection.split()[-1].lower() if selection else ''
    winner_last = winner_name.split()[-1].lower() if winner_name else ''

    print(f"[{timestamp()}] TE settlement: selection='{selection}' (last='{selection_last}'), winner='{winner_name}' (last='{winner_last}')")

    if selection_last == winner_last:
        result = 'Win'
        profit = bet.get('stake', 0) * (bet.get('odds', 0) - 1) * 0.95
    else:
        result = 'Loss'
        profit = -bet.get('stake', 0)

    return (result, profit)


# ============================================================================
# DISCORD BOT
# ============================================================================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Shared state
betfair = BetfairClient()
supabase = SupabaseClient()
previously_live = {}
alerted_results = set()  # Track bet IDs that have already had result alerts sent


@bot.event
async def on_ready():
    print(f"[{timestamp()}] Discord bot connected as {bot.user}")
    monitor_loop.start()
    local_db_sync_loop.start()


def shorten_match(match_desc: str) -> str:
    """Convert 'FirstName LastName vs FirstName LastName' to 'LastName v LastName'."""
    if ' vs ' not in match_desc:
        return match_desc
    parts = match_desc.split(' vs ')
    if len(parts) == 2:
        p1_last = parts[0].strip().split()[-1] if parts[0].strip() else parts[0]
        p2_last = parts[1].strip().split()[-1] if parts[1].strip() else parts[1]
        return f"{p1_last} v {p2_last}"
    return match_desc

def shorten_selection(selection: str) -> str:
    """Get just the last name from selection."""
    if selection:
        return selection.split()[-1]
    return selection

@bot.command(name='inplay')
async def cmd_inplay(ctx):
    """Show all currently in-play bets."""
    await asyncio.to_thread(sync_local_to_cloud)
    # Get bets marked as live in Supabase (primary source)
    live_bets_from_db = supabase.get_live_bets()

    # Also check Betfair markets for any pending bets we might have missed
    pending = supabase.get_pending_bets()
    markets = betfair.get_inplay_tennis()

    # Build set of bet IDs already marked as live
    live_bet_ids = {bet.get('id') for bet in live_bets_from_db}

    # Add any pending bets that match live Betfair markets but aren't marked yet
    for bet in pending:
        if bet.get('id') not in live_bet_ids:
            market = find_market_for_bet(bet, markets)
            if market:
                live_bets_from_db.append(bet)

    live_bets = live_bets_from_db

    if not live_bets:
        await ctx.send("No bets currently in-play.")
        return

    # Build table with ASCII borders
    lines = []
    lines.append(f"**\U0001F3BE IN-PLAY BETS ({len(live_bets)})**")
    lines.append("```")
    lines.append("+" + "-"*22 + "+" + "-"*14 + "+" + "-"*6 + "+" + "-"*6 + "+" + "-"*22 + "+")
    lines.append("| Match                | Selection    | Odds | Stake| Tournament           |")
    lines.append("+" + "-"*22 + "+" + "-"*14 + "+" + "-"*6 + "+" + "-"*6 + "+" + "-"*22 + "+")

    for bet in live_bets:
        match = shorten_match(bet.get('match_description', 'Unknown'))[:20]
        selection = shorten_selection(bet.get('selection', '?'))[:12]
        odds = f"{bet.get('odds', 0):.2f}"
        stake = f"{bet.get('stake', 0):.1f}u"
        tournament = bet.get('tournament', '')[:20]
        lines.append(f"| {match:<20} | {selection:<12} | {odds:>4} | {stake:>4} | {tournament:<20} |")

    lines.append("+" + "-"*22 + "+" + "-"*14 + "+" + "-"*6 + "+" + "-"*6 + "+" + "-"*22 + "+")
    lines.append("```")

    await ctx.send("\n".join(lines))


@bot.command(name='debug')
async def cmd_debug(ctx):
    """Debug: Show Betfair markets and matching attempts."""
    pending = supabase.get_pending_bets()
    markets = betfair.get_inplay_tennis()

    lines = []
    lines.append(f"**DEBUG: {len(markets)} Betfair markets, {len(pending)} pending bets**")

    # Show Betfair markets
    await ctx.send("**Betfair In-Play Markets:**\n```" + "\n".join([f"{m.get('player1')} vs {m.get('player2')}" for m in markets[:12]]) + "```")

    # Try to match each pending bet and show details for failures
    matched_bets = []
    unmatched_bets = []

    for bet in pending:
        match_desc = bet.get('match_description', '')
        if ' vs ' not in match_desc:
            continue
        parts = match_desc.split(' vs ')
        bet_p1 = parts[0].strip()
        bet_p2 = parts[1].strip()
        bet_p1_last = bet_p1.split()[-1].lower() if bet_p1 else ''
        bet_p2_last = bet_p2.split()[-1].lower() if bet_p2 else ''

        market = find_market_for_bet(bet, markets)
        if market:
            matched_bets.append(match_desc[:35])
        else:
            # Show why it didn't match - check each market
            unmatched_bets.append(f"{bet_p1_last} v {bet_p2_last}")

    await ctx.send(f"**Matched ({len(matched_bets)}):**\n```" + "\n".join(matched_bets[:10]) + "```")
    await ctx.send(f"**Unmatched ({len(unmatched_bets)}):**\n```" + "\n".join(unmatched_bets[:10]) + "```")


@bot.command(name='pending')
async def cmd_pending(ctx):
    """Show all pending bets."""
    await asyncio.to_thread(sync_local_to_cloud)
    pending = supabase.get_pending_bets()

    if not pending:
        await ctx.send("No pending bets.")
        return

    # Calculate total stake
    total_stake = sum(bet.get('stake', 0) for bet in pending)

    # Sort by stake descending
    pending.sort(key=lambda b: b.get('stake', 0), reverse=True)

    # Build table with ASCII borders
    lines = []
    lines.append(f"**\U0001F4CB PENDING BETS ({len(pending)})**")
    lines.append("```")
    lines.append("+" + "-"*22 + "+" + "-"*14 + "+" + "-"*6 + "+" + "-"*6 + "+" + "-"*22 + "+")
    lines.append("| Match                | Selection    | Odds | Stake| Tournament           |")
    lines.append("+" + "-"*22 + "+" + "-"*14 + "+" + "-"*6 + "+" + "-"*6 + "+" + "-"*22 + "+")

    # Show first 12
    for bet in pending[:12]:
        match = shorten_match(bet.get('match_description', 'Unknown'))[:20]
        selection = shorten_selection(bet.get('selection', '?'))[:12]
        odds = f"{bet.get('odds', 0):.2f}"
        stake = f"{bet.get('stake', 0):.1f}u"
        tournament = bet.get('tournament', '')[:20]
        lines.append(f"| {match:<20} | {selection:<12} | {odds:>4} | {stake:>4} | {tournament:<20} |")

    lines.append("+" + "-"*22 + "+" + "-"*14 + "+" + "-"*6 + "+" + "-"*6 + "+" + "-"*22 + "+")
    lines.append("```")

    if len(pending) > 12:
        lines.append(f"*Showing 12 of {len(pending)} | Total stake: {total_stake:.1f}u*")
    else:
        lines.append(f"*Total stake: {total_stake:.1f}u*")

    await ctx.send("\n".join(lines))


@bot.command(name='stats')
async def cmd_stats(ctx):
    """Show today's stats."""
    await asyncio.to_thread(sync_local_to_cloud)
    settled = supabase.get_settled_today()

    if not settled:
        await ctx.send("No bets settled today.")
        return

    wins = sum(1 for b in settled if b.get('result') == 'Win')
    losses = sum(1 for b in settled if b.get('result') == 'Loss')
    total_pl = sum(b.get('profit_loss', 0) for b in settled)

    if total_pl >= 0:
        color = 0x22c55e
        pl_str = f"+{total_pl:.2f}u"
    else:
        color = 0xef4444
        pl_str = f"{total_pl:.2f}u"

    embed = discord.Embed(title="TODAY'S STATS", color=color)
    embed.add_field(name="Record", value=f"**{wins}W - {losses}L**", inline=True)
    embed.add_field(name="P/L", value=f"**{pl_str}**", inline=True)
    embed.add_field(name="Bets Settled", value=str(len(settled)), inline=True)

    await ctx.send(embed=embed)


@bot.command(name='alert')
async def cmd_alert(ctx, result: str, *, match: str):
    """Manually send an alert. Usage: !alert win/loss Match Description"""
    # Find the bet in Supabase
    pending = supabase.get_pending_bets()
    bet = None
    for b in pending:
        if match.lower() in b.get('match_description', '').lower():
            bet = b
            break

    if not bet:
        # Check settled bets
        settled = supabase.get_settled_today()
        for b in settled:
            if match.lower() in b.get('match_description', '').lower():
                bet = b
                break

    if not bet:
        await ctx.send(f"Could not find bet matching '{match}'")
        return

    result = result.capitalize()
    if result == 'Win':
        emoji = "\u2705"
        color = 0x22c55e
        profit = bet.get('stake', 0) * (bet.get('odds', 0) - 1) * 0.95
        pl_str = f"+{profit:.2f}u"
    else:
        emoji = "\u274C"
        color = 0xef4444
        profit = -bet.get('stake', 0)
        pl_str = f"{profit:.2f}u"

    embed = discord.Embed(
        title=f"{emoji} {result.upper()}: {bet.get('match_description', 'Unknown')}",
        color=color,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Selection", value=bet.get('selection', '?'), inline=True)
    embed.add_field(name="Odds", value=f"{bet.get('odds', 0):.2f}", inline=True)
    embed.add_field(name="P/L", value=f"**{pl_str}**", inline=True)
    embed.set_footer(text="Tennis Betting Monitor")

    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)
        await ctx.send(f"Alert sent for {bet.get('match_description')}")
    else:
        await ctx.send("Could not find alert channel")


@bot.command(name='refresh')
async def cmd_refresh(ctx):
    """Check all pending bets against Betfair + Tennis Explorer and settle finished matches."""
    await asyncio.to_thread(sync_local_to_cloud)
    await ctx.send("Checking pending bets...")

    # Ensure Betfair is logged in
    if not betfair.session_token:
        if not betfair.login():
            await ctx.send("Betfair login failed — will check Tennis Explorer only.")

    pending = supabase.get_pending_bets()
    if not pending:
        await ctx.send("No pending bets to check.")
        return

    settled_results = []
    now_live = []
    errors = []
    unsettled_bets = []  # Bets not resolved via Betfair, need TE check

    # ---- PHASE 1: Check Betfair ----
    all_markets = betfair.get_all_tennis_markets() if betfair.session_token else []
    print(f"[{timestamp()}] !refresh: {len(pending)} pending bets, {len(all_markets)} Betfair markets")

    for bet in pending:
        bet_id = bet.get('id')
        match_desc = bet.get('match_description', 'Unknown')
        market_id = bet.get('market_id')

        # Try to find a Betfair market for this bet
        market = None
        if not market_id:
            market = find_market_for_bet(bet, all_markets)
            if market:
                market_id = market.get('market_id')
                supabase._request(
                    f"pending_bets?id=eq.{bet_id}",
                    method='PATCH',
                    data={
                        'market_id': market.get('market_id'),
                        'selection_ids': json.dumps(market.get('selection_ids', {}))
                    }
                )

        if not market_id:
            unsettled_bets.append(bet)
            continue

        # Check market status
        result = betfair.get_market_result(market_id)
        status = result.get('status') if result else None

        if status == 'CLOSED':
            selection_ids = None
            if market and market.get('selection_ids'):
                selection_ids = market.get('selection_ids')
            else:
                selection_ids = get_selection_ids_for_bet(bet)

            settled_via_bf = False
            if selection_ids:
                market_info = {'selection_ids': selection_ids}
                outcome = determine_result(bet, market_info, result)
                if outcome:
                    bet_result, profit = outcome
                    print(f"[{timestamp()}] [PATH: refresh_betfair] {match_desc} - {bet_result}")
                    supabase.mark_finished(bet_id, bet_result, profit)
                    update_local_db(match_desc, bet.get('selection', ''), bet_result, profit)
                    if bet_id not in alerted_results:
                        send_result_alert(bet, bet_result, profit)
                        alerted_results.add(bet_id)
                    previously_live.pop(bet_id, None)
                    pl_str = f"+{profit:.2f}u" if profit >= 0 else f"{profit:.2f}u"
                    settled_results.append(f"{'W' if bet_result == 'Win' else 'L'} {shorten_match(match_desc)} ({pl_str}) [BF]")
                    settled_via_bf = True

            if not settled_via_bf:
                # Betfair says CLOSED but couldn't settle (no selection_ids or no winner) — try TE
                print(f"[{timestamp()}] [PATH: refresh_bf_to_te] {match_desc}: CLOSED but can't settle via BF, trying TE")
                unsettled_bets.append(bet)

        elif status in ['ACTIVE', 'SUSPENDED']:
            now_live.append(shorten_match(match_desc))
            if bet_id not in previously_live:
                sel_ids = (market.get('selection_ids') if market else None) or get_selection_ids_for_bet(bet) or {}
                previously_live[bet_id] = {'bet': bet, 'market': {'market_id': market_id, 'selection_ids': sel_ids}}

        elif status == 'OPEN':
            pass  # Not started yet

        else:
            # Market not found on Betfair anymore (expired) — try TE
            unsettled_bets.append(bet)

    # ---- PHASE 2: Check Tennis Explorer for remaining bets ----
    if unsettled_bets:
        await ctx.send(f"Checking Tennis Explorer for {len(unsettled_bets)} unresolved bet(s)...")
        te_results = fetch_completed_results(days_back=3)

        for bet in unsettled_bets:
            bet_id = bet.get('id')
            match_desc = bet.get('match_description', 'Unknown')

            winner_name = find_result_for_bet(bet, te_results)
            if winner_name:
                outcome = settle_from_result(bet, winner_name)
                if outcome:
                    bet_result, profit = outcome
                    print(f"[{timestamp()}] [PATH: refresh_te] {match_desc} - {bet_result}")
                    supabase.mark_finished(bet_id, bet_result, profit)
                    update_local_db(match_desc, bet.get('selection', ''), bet_result, profit)
                    if bet_id not in alerted_results:
                        send_result_alert(bet, bet_result, profit)
                        alerted_results.add(bet_id)
                    previously_live.pop(bet_id, None)
                    pl_str = f"+{profit:.2f}u" if profit >= 0 else f"{profit:.2f}u"
                    settled_results.append(f"{'W' if bet_result == 'Win' else 'L'} {shorten_match(match_desc)} ({pl_str}) [TE]")

    # Send queued result alerts
    await send_queued_alerts()

    # ---- Build summary ----
    lines = ["**Refresh complete:**"]

    if settled_results:
        total_pl = sum(float(r.split('(')[1].split('u)')[0]) for r in settled_results)
        pl_str = f"+{total_pl:.2f}u" if total_pl >= 0 else f"{total_pl:.2f}u"
        lines.append(f"\nSettled ({len(settled_results)}) — **{pl_str}**:")
        lines.append("```")
        for r in settled_results:
            lines.append(f"  {r}")
        lines.append("```")

    if now_live:
        lines.append(f"\nCurrently live ({len(now_live)}):")
        lines.append("```")
        for m in now_live:
            lines.append(f"  {m}")
        lines.append("```")

    if errors:
        lines.append(f"\nErrors ({len(errors)}):")
        lines.append("```")
        for e in errors:
            lines.append(f"  {e}")
        lines.append("```")

    # Count remaining unsettled
    settled_ids = set()
    for r in settled_results:
        # Already settled above
        pass
    remaining = len(pending) - len(settled_results) - len(now_live) - len(errors)
    if remaining > 0:
        lines.append(f"\n*{remaining} bet(s) still pending (not yet played or not found on TE)*")

    if not settled_results and not now_live and not errors:
        lines.append("No matches found to settle. Bets may not have been played yet.")

    await ctx.send("\n".join(lines))


# ============================================================================
# MONITOR LOOP (runs every 30 seconds)
# ============================================================================

@tasks.loop(seconds=CHECK_INTERVAL)
async def monitor_loop():
    global previously_live

    try:
        pending = supabase.get_pending_bets()
        if not pending:
            return

        markets = betfair.get_inplay_tennis()
        print(f"[{timestamp()}] {len(pending)} pending, {len(markets)} in-play markets")

        current_live = {}

        for bet in pending:
            bet_id = bet.get('id')
            market = find_market_for_bet(bet, markets)

            if market:
                current_live[bet_id] = market

                if bet_id not in previously_live:
                    print(f"[{timestamp()}] LIVE (Betfair matched): {bet.get('match_description')}")
                    send_live_alert(bet)
                    # Store market_id and selection_ids for result detection
                    # (local DB sync handles is_live via in_progress field)
                    supabase._request(
                        f"pending_bets?id=eq.{bet_id}",
                        method='PATCH',
                        data={
                            'market_id': market.get('market_id'),
                            'selection_ids': json.dumps(market.get('selection_ids', {}))
                        }
                    )

                previously_live[bet_id] = {'bet': bet, 'market': market}

        # Check for finished matches
        for bet_id, data in list(previously_live.items()):
            if bet_id not in current_live:
                bet = data['bet']
                market_info = data['market']
                market_id = market_info.get('market_id')

                if market_id:
                    result = betfair.get_market_result(market_id)
                    status = result.get('status') if result else None
                    print(f"[{timestamp()}] Checking finished: {bet.get('match_description')} - Status: {status}")

                    if status == 'CLOSED':
                        print(f"[{timestamp()}] [PATH: main_loop] Settling {bet.get('match_description')}")
                        outcome = determine_result(bet, market_info, result)
                        if outcome:
                            bet_result, profit = outcome
                            print(f"[{timestamp()}] FINISHED: {bet.get('match_description')} - {bet_result}")
                            if bet_id not in alerted_results:
                                send_result_alert(bet, bet_result, profit)
                                alerted_results.add(bet_id)
                            supabase.mark_finished(bet_id, bet_result, profit)
                            update_local_db(bet.get('match_description', ''), bet.get('selection', ''), bet_result, profit)
                            del previously_live[bet_id]
                        else:
                            print(f"[{timestamp()}] Could not determine winner, keeping tracked")
                    elif status == 'SUSPENDED' or status == 'ACTIVE' or status is None:
                        # Keep tracking - market not settled yet or API error
                        pass
                    else:
                        # Unknown status, keep tracking to be safe
                        print(f"[{timestamp()}] Unknown status {status}, keeping tracked")

        # Check for any bets marked as live in Supabase that we're not tracking
        # This catches bets that finished during a restart or missed alerts
        for bet in pending:
            bet_id = bet.get('id')
            if bet.get('is_live') and bet.get('market_id') and bet_id not in previously_live and bet_id not in current_live:
                market_id = bet.get('market_id')
                result = betfair.get_market_result(market_id)
                status = result.get('status') if result else None

                if status == 'CLOSED':
                    print(f"[{timestamp()}] [PATH: missed_alert_recovery] Found missed result: {bet.get('match_description')}")
                    # Use selection_ids (stored or fetched) to correctly identify winner
                    selection_ids = get_selection_ids_for_bet(bet)
                    if selection_ids:
                        market_info = {'selection_ids': selection_ids}
                        outcome = determine_result(bet, market_info, result)
                        if outcome:
                            bet_result, profit = outcome
                            print(f"[{timestamp()}] MISSED ALERT RECOVERY: {bet.get('match_description')} - {bet_result}")
                            if bet_id not in alerted_results:
                                send_result_alert(bet, bet_result, profit)
                                alerted_results.add(bet_id)
                            supabase.mark_finished(bet_id, bet_result, profit)
                            update_local_db(bet.get('match_description', ''), bet.get('selection', ''), bet_result, profit)
                        else:
                            print(f"[{timestamp()}] Could not determine winner for missed result (no WINNER runner)")
                    else:
                        print(f"[{timestamp()}] SKIPPING settlement - no selection_ids for {bet.get('match_description')}")
                elif status in ['ACTIVE', 'SUSPENDED', 'OPEN']:
                    # Still live, add to tracking with selection_ids
                    sel_ids = get_selection_ids_for_bet(bet) or {}
                    previously_live[bet_id] = {'bet': bet, 'market': {'market_id': market_id, 'selection_ids': sel_ids}}

        # Send any queued alerts via the bot
        await send_queued_alerts()
    except Exception as e:
        print(f"[{timestamp()}] Monitor error: {e}")


@monitor_loop.before_loop
async def before_monitor():
    global previously_live
    await bot.wait_until_ready()
    if not betfair.session_token:
        if betfair.login():
            print(f"[{timestamp()}] Betfair login successful")
        else:
            print(f"[{timestamp()}] Betfair login failed — monitor will use TE fallback via !refresh")

    # On startup, find ALL currently live bets and add to previously_live WITHOUT alerting
    # This prevents duplicate alerts when monitor restarts
    print(f"[{timestamp()}] Checking for currently live bets (no alerts on startup)...")
    pending = supabase.get_pending_bets()
    markets = betfair.get_inplay_tennis() if betfair.session_token else []

    for bet in pending:
        bet_id = bet.get('id')
        market = find_market_for_bet(bet, markets)

        if market:
            # Bet is currently live - add to tracking WITHOUT alerting
            print(f"[{timestamp()}] Already live (no alert): {bet.get('match_description')}")
            previously_live[bet_id] = {'bet': bet, 'market': market}
            # Store market_id and selection_ids for result detection
            # (don't set is_live - local DB sync handles that)
            supabase._request(
                f"pending_bets?id=eq.{bet_id}",
                method='PATCH',
                data={
                    'market_id': market.get('market_id'),
                    'selection_ids': json.dumps(market.get('selection_ids', {}))
                }
            )
        elif bet.get('is_live') and bet.get('market_id'):
            # Was marked live but not in current markets - check if finished
            market_id = bet.get('market_id')
            result = betfair.get_market_result(market_id)
            status = result.get('status') if result else None
            print(f"[{timestamp()}] Startup check (was live): {bet.get('match_description')} - Status: {status}")

            if status == 'CLOSED':
                print(f"[{timestamp()}] [PATH: startup_check] Settling {bet.get('match_description')}")
                # Use selection_ids (stored or fetched) to correctly identify winner
                selection_ids = get_selection_ids_for_bet(bet)
                if selection_ids:
                    market_info = {'selection_ids': selection_ids}
                    outcome = determine_result(bet, market_info, result)
                    if outcome:
                        bet_result, profit = outcome
                        print(f"[{timestamp()}] FINISHED (startup): {bet.get('match_description')} - {bet_result}")
                        send_result_alert(bet, bet_result, profit)
                        supabase.mark_finished(bet.get('id'), bet_result, profit)
                        update_local_db(bet.get('match_description', ''), bet.get('selection', ''), bet_result, profit)
                    else:
                        print(f"[{timestamp()}] Could not determine winner at startup (no WINNER runner)")
                else:
                    print(f"[{timestamp()}] SKIPPING startup settlement - no selection_ids for {bet.get('match_description')}")
            elif status in ['ACTIVE', 'SUSPENDED', 'OPEN']:
                # Still live on Betfair, add to tracking with selection_ids
                sel_ids = get_selection_ids_for_bet(bet) or {}
                previously_live[bet_id] = {'bet': bet, 'market': {'market_id': market_id, 'selection_ids': sel_ids}}
            elif status is None:
                # Market expired/gone on Betfair — leave for !refresh to settle via TE
                print(f"[{timestamp()}] Startup: {bet.get('match_description')} - market expired, use !refresh to settle")

    # Immediately sync live status from local DB (source of truth for is_live)
    try:
        sync_live_status_from_local_db()
        print(f"[{timestamp()}] Initial local DB sync completed")
    except Exception as e:
        print(f"[{timestamp()}] Initial local DB sync error: {e}")

    # Send any queued alerts from startup checks
    await send_queued_alerts()


# Periodic sync: local DB in_progress -> Supabase is_live (every 5 minutes)
@tasks.loop(minutes=2)
async def local_db_sync_loop():
    """Sync in_progress status from local database to Supabase every 2 minutes."""
    try:
        sync_live_status_from_local_db()
    except Exception as e:
        print(f"[{timestamp()}] Local DB sync loop error: {e}")


@local_db_sync_loop.before_loop
async def before_local_sync():
    await bot.wait_until_ready()
    print(f"[{timestamp()}] Local DB sync started (every 2 minutes)")


# ============================================================================
# MAIN
# ============================================================================

def main():
    print(f"[{timestamp()}] Tennis Betting Monitor + Bot starting...")

    if not DISCORD_BOT_TOKEN:
        print("ERROR: No Discord bot token found in credentials.json")
        print("Add: \"discord_bot_token\": \"your-token-here\"")
        return

    if not supabase.is_configured():
        print("ERROR: Supabase not configured")
        return

    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()
