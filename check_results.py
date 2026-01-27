"""
One-time check of all pending bets to see if any have finished.
Sends Discord alerts for any settled matches.
"""

import json
import urllib.request
import urllib.error
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional


# Load credentials
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
DISCORD_WEBHOOK = CREDS.get('discord_webhook', '')


class BetfairClient:
    LOGIN_URL = "https://identitysso.betfair.com/api/login"
    API_URL = "https://api.betfair.com/exchange/betting/rest/v1.0/"

    def __init__(self):
        self.session_token = None
        self.app_key = BETFAIR_APP_KEY

    def login(self) -> bool:
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
                    print("Betfair login successful")
                    return True
        except Exception as e:
            print(f"Betfair login error: {e}")
        return False

    def api_request(self, endpoint: str, params: dict) -> Optional[dict]:
        if not self.session_token:
            if not self.login():
                return None
        headers = {
            'X-Application': self.app_key,
            'X-Authentication': self.session_token,
            'Content-Type': 'application/json'
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
        except Exception as e:
            print(f"API error: {e}")
        return None

    def search_markets(self, player1: str, player2: str) -> List[Dict]:
        """Search for markets by player names."""
        # Try to find by text query
        params = {
            "filter": {
                "eventTypeIds": ["2"],
                "marketTypeCodes": ["MATCH_ODDS"],
                "textQuery": player1.split()[-1]  # Search by last name
            },
            "marketProjection": ["RUNNER_DESCRIPTION", "EVENT"],
            "maxResults": "100"
        }
        result = self.api_request("listMarketCatalogue", params)
        if not result:
            return []

        markets = []
        p1_last = player1.split()[-1].lower()
        p2_last = player2.split()[-1].lower()

        for market in result:
            runners = market.get('runners', [])
            if len(runners) == 2:
                r1 = runners[0].get('runnerName', '').lower()
                r2 = runners[1].get('runnerName', '').lower()
                if (p1_last in r1 or p1_last in r2) and (p2_last in r1 or p2_last in r2):
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

    def get_market_book(self, market_id: str) -> Optional[Dict]:
        params = {
            "marketIds": [market_id],
            "priceProjection": {"priceData": ["EX_BEST_OFFERS"]}
        }
        result = self.api_request("listMarketBook", params)
        if result and len(result) > 0:
            return result[0]
        return None


def send_discord_alert(bet: Dict, result: str, profit_loss: float):
    if not DISCORD_WEBHOOK:
        return

    if result == 'Win':
        color = 0x22c55e
        pl_str = f"+{profit_loss:.2f}u"
    else:
        color = 0xef4444
        pl_str = f"{profit_loss:.2f}u"

    payload = {
        "embeds": [{
            "title": f"{result.upper()}: {bet.get('match_description', 'Unknown')}",
            "color": color,
            "fields": [
                {"name": "Selection", "value": bet.get('selection', '?'), "inline": True},
                {"name": "Odds", "value": f"{bet.get('odds', 0):.2f}", "inline": True},
                {"name": "P/L", "value": f"**{pl_str}**", "inline": True},
            ],
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "Tennis Betting Monitor - Results Check"}
        }]
    }

    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            DISCORD_WEBHOOK,
            data=data,
            headers={'Content-Type': 'application/json', 'User-Agent': 'TennisBettingMonitor/1.0'},
            method='POST'
        )
        urllib.request.urlopen(req, timeout=10)
        print(f"  Discord alert sent!")
    except Exception as e:
        print(f"  Discord error: {e}")


def update_supabase(bet_id: int, result: str, profit_loss: float):
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }
    data = {
        'result': result,
        'profit_loss': profit_loss,
        'is_live': False,
        'finished_at': datetime.utcnow().isoformat()
    }
    try:
        body = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/pending_bets?id=eq.{bet_id}",
            data=body,
            headers=headers,
            method='PATCH'
        )
        urllib.request.urlopen(req, timeout=10)
        print(f"  Supabase updated!")
    except Exception as e:
        print(f"  Supabase error: {e}")


def get_pending_bets() -> List[Dict]:
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json'
    }
    try:
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/pending_bets?result=is.null&order=match_date.asc",
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error getting bets: {e}")
    return []


def main():
    print("=" * 60)
    print("CHECKING ALL PENDING BETS FOR RESULTS")
    print("=" * 60)

    betfair = BetfairClient()
    if not betfair.login():
        print("Failed to login to Betfair")
        return

    pending = get_pending_bets()
    print(f"\nFound {len(pending)} pending bets to check\n")

    settled_count = 0

    for bet in pending:
        match_desc = bet.get('match_description', '')
        print(f"Checking: {match_desc}")

        if ' vs ' not in match_desc:
            print("  Skipping - invalid format")
            continue

        parts = match_desc.split(' vs ')
        player1 = parts[0].strip()
        player2 = parts[1].strip()

        # Search for the market
        markets = betfair.search_markets(player1, player2)

        if not markets:
            print("  No market found on Betfair")
            continue

        market = markets[0]
        print(f"  Found market: {market.get('event_name')}")

        # Check market status
        book = betfair.get_market_book(market['market_id'])
        if not book:
            print("  Could not get market book")
            continue

        status = book.get('status')
        print(f"  Market status: {status}")

        if status == 'CLOSED':
            # Find winner
            runners = book.get('runners', [])
            selection_ids = market.get('selection_ids', {})

            winner_name = None
            for runner in runners:
                if runner.get('status') == 'WINNER':
                    sel_id = runner.get('selectionId')
                    for name, sid in selection_ids.items():
                        if sid == sel_id:
                            winner_name = name
                            break
                    break

            if winner_name:
                selection = bet.get('selection', '')
                selection_last = selection.split()[-1].lower()
                winner_last = winner_name.split()[-1].lower()

                if selection_last == winner_last:
                    result = 'Win'
                    odds = bet.get('odds', 0)
                    stake = bet.get('stake', 0)
                    profit = stake * (odds - 1) * 0.95
                else:
                    result = 'Loss'
                    profit = -bet.get('stake', 0)

                print(f"  RESULT: {result} (Winner: {winner_name})")
                print(f"  P/L: {profit:.2f}u")

                # Send Discord alert
                send_discord_alert(bet, result, profit)

                # Update Supabase
                update_supabase(bet.get('id'), result, profit)

                settled_count += 1
            else:
                print("  Could not determine winner")
        elif status == 'ACTIVE' or status == 'SUSPENDED':
            print("  Match still in progress or suspended")
        else:
            print(f"  Unknown status: {status}")

        print()

    print("=" * 60)
    print(f"DONE! Settled {settled_count} bets")
    print("=" * 60)


if __name__ == "__main__":
    main()
