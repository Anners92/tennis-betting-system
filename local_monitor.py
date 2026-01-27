"""
Local Monitor with Discord Bot - Monitors bets and responds to commands.
Commands: !inplay, !pending, !stats
"""

import json
import time
import urllib.request
import urllib.error
import os
import sys
import asyncio
import threading
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

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
            SET result = ?, profit_loss = ?, settled_at = ?
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


def players_match(bet_p1: str, bet_p2: str, market_p1: str, market_p2: str) -> bool:
    bet_p1_last = bet_p1.split()[-1].lower() if bet_p1 else ''
    bet_p2_last = bet_p2.split()[-1].lower() if bet_p2 else ''
    market_p1_last = market_p1.split()[-1].lower() if market_p1 else ''
    market_p2_last = market_p2.split()[-1].lower() if market_p2 else ''
    return (bet_p1_last == market_p1_last and bet_p2_last == market_p2_last) or \
           (bet_p1_last == market_p2_last and bet_p2_last == market_p1_last)


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
    pending = supabase.get_pending_bets()
    markets = betfair.get_inplay_tennis()

    live_bets = []
    for bet in pending:
        market = find_market_for_bet(bet, markets)
        if market:
            live_bets.append(bet)

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


@bot.command(name='pending')
async def cmd_pending(ctx):
    """Show all pending bets."""
    pending = supabase.get_pending_bets()

    if not pending:
        await ctx.send("No pending bets.")
        return

    # Calculate total stake
    total_stake = sum(bet.get('stake', 0) for bet in pending)

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
                    print(f"[{timestamp()}] LIVE: {bet.get('match_description')}")
                    send_live_alert(bet)
                    supabase.mark_live(bet_id, True, market.get('market_id'))

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
                    print(f"[{timestamp()}] Found missed result: {bet.get('match_description')}")
                    # Determine winner from runners
                    runners = result.get('runners', []) if result else []
                    sorted_runners = sorted(runners, key=lambda r: r.get('selectionId', 0))

                    winner_idx = None
                    for i, runner in enumerate(sorted_runners):
                        if runner.get('status') == 'WINNER':
                            winner_idx = i
                            break

                    if winner_idx is not None:
                        match_desc = bet.get('match_description', '')
                        selection = bet.get('selection', '')
                        selection_last = selection.split()[-1].lower() if selection else ''

                        if ' vs ' in match_desc:
                            parts = match_desc.split(' vs ')
                            player1_last = parts[0].strip().split()[-1].lower()
                            player2_last = parts[1].strip().split()[-1].lower()
                            winner_last = player1_last if winner_idx == 0 else player2_last

                            if selection_last == winner_last:
                                bet_result = 'Win'
                                profit = bet.get('stake', 0) * (bet.get('odds', 0) - 1) * 0.95
                            else:
                                bet_result = 'Loss'
                                profit = -bet.get('stake', 0)

                            print(f"[{timestamp()}] MISSED ALERT RECOVERY: {bet.get('match_description')} - {bet_result}")
                            if bet_id not in alerted_results:
                                send_result_alert(bet, bet_result, profit)
                                alerted_results.add(bet_id)
                            supabase.mark_finished(bet_id, bet_result, profit)
                            update_local_db(bet.get('match_description', ''), bet.get('selection', ''), bet_result, profit)
                elif status in ['ACTIVE', 'SUSPENDED', 'OPEN']:
                    # Still live, add to tracking
                    previously_live[bet_id] = {'bet': bet, 'market': {'market_id': market_id, 'selection_ids': {}}}

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
            print(f"[{timestamp()}] Betfair login failed")
            return

    # On startup, find ALL currently live bets and add to previously_live WITHOUT alerting
    # This prevents duplicate alerts when monitor restarts
    print(f"[{timestamp()}] Checking for currently live bets (no alerts on startup)...")
    pending = supabase.get_pending_bets()
    markets = betfair.get_inplay_tennis()

    for bet in pending:
        bet_id = bet.get('id')
        market = find_market_for_bet(bet, markets)

        if market:
            # Bet is currently live - add to tracking WITHOUT alerting
            print(f"[{timestamp()}] Already live (no alert): {bet.get('match_description')}")
            previously_live[bet_id] = {'bet': bet, 'market': market}
            # Update Supabase to mark as live
            supabase.mark_live(bet_id, True, market.get('market_id'))
        elif bet.get('is_live') and bet.get('market_id'):
            # Was marked live but not in current markets - check if finished
            market_id = bet.get('market_id')
            result = betfair.get_market_result(market_id)
            status = result.get('status') if result else None
            print(f"[{timestamp()}] Startup check (was live): {bet.get('match_description')} - Status: {status}")

            if status == 'CLOSED':
                runners = result.get('runners', []) if result else []
                sorted_runners = sorted(runners, key=lambda r: r.get('selectionId', 0))

                winner_idx = None
                for i, runner in enumerate(sorted_runners):
                    if runner.get('status') == 'WINNER':
                        winner_idx = i
                        break

                if winner_idx is not None:
                    match_desc = bet.get('match_description', '')
                    selection = bet.get('selection', '')
                    selection_last = selection.split()[-1].lower() if selection else ''

                    if ' vs ' in match_desc:
                        parts = match_desc.split(' vs ')
                        player1_last = parts[0].strip().split()[-1].lower()
                        player2_last = parts[1].strip().split()[-1].lower()

                        winner_last = player1_last if winner_idx == 0 else player2_last

                        if selection_last == winner_last:
                            bet_result = 'Win'
                            profit = bet.get('stake', 0) * (bet.get('odds', 0) - 1) * 0.95
                        else:
                            bet_result = 'Loss'
                            profit = -bet.get('stake', 0)

                        print(f"[{timestamp()}] FINISHED (startup): {bet.get('match_description')} - {bet_result}")
                        send_result_alert(bet, bet_result, profit)
                        supabase.mark_finished(bet.get('id'), bet_result, profit)
                        update_local_db(bet.get('match_description', ''), bet.get('selection', ''), bet_result, profit)
            elif status in ['ACTIVE', 'SUSPENDED', 'OPEN', None]:
                # Still live, add to tracking
                previously_live[bet_id] = {'bet': bet, 'market': {'market_id': market_id, 'selection_ids': {}}}

    # Send any queued alerts from startup checks
    await send_queued_alerts()


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
