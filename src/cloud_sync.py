"""
Cloud Sync - Sync pending bets to Supabase for cloud monitoring.

Setup:
1. Create free account at https://supabase.com
2. Create new project
3. Go to Settings > API > Get your URL and anon key
4. Add to credentials.json:
   "supabase_url": "https://xxxxx.supabase.co"
   "supabase_key": "your-anon-key"
5. Run this file once to create the table: python src/cloud_sync.py --setup
"""

import json
import urllib.request
import urllib.error
import os
import sys
from typing import Dict, List, Optional
from datetime import datetime


def get_app_directory() -> str:
    """Get the directory where the app is running from."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        src_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.dirname(src_dir)


def load_supabase_config() -> Dict[str, str]:
    """Load Supabase config from credentials.json."""
    app_dir = get_app_directory()
    creds_path = os.path.join(app_dir, 'credentials.json')

    if os.path.exists(creds_path):
        try:
            with open(creds_path, 'r') as f:
                creds = json.load(f)
                return {
                    'url': creds.get('supabase_url', ''),
                    'key': creds.get('supabase_key', '')
                }
        except Exception:
            pass
    return {'url': '', 'key': ''}


class CloudSync:
    """Sync bets to Supabase cloud database."""

    def __init__(self, url: str = None, key: str = None):
        config = load_supabase_config()
        self.url = url or config.get('url', '')
        self.key = key or config.get('key', '')
        self.headers = {
            'apikey': self.key,
            'Authorization': f'Bearer {self.key}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }

    def is_configured(self) -> bool:
        """Check if Supabase is configured."""
        return bool(self.url and self.key and 'supabase.co' in self.url)

    def _request(self, endpoint: str, method: str = 'GET', data: Dict = None, upsert: bool = False) -> Optional[Dict]:
        """Make request to Supabase REST API."""
        if not self.is_configured():
            return None

        url = f"{self.url}/rest/v1/{endpoint}"

        try:
            body = json.dumps(data).encode('utf-8') if data else None
            headers = self.headers.copy()
            if upsert:
                # For upserts, need resolution=merge-duplicates to update existing rows
                headers['Prefer'] = 'return=representation,resolution=merge-duplicates'
            req = urllib.request.Request(url, data=body, headers=headers, method=method)

            with urllib.request.urlopen(req, timeout=10) as response:
                response_data = response.read().decode('utf-8')
                if response_data:
                    return json.loads(response_data)
                return {}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            print(f"Supabase error {e.code}: {error_body}")
            return None
        except Exception as e:
            print(f"Supabase request error: {e}")
            return None

    def sync_bet(self, bet: Dict) -> bool:
        """Sync a single bet to Supabase (upsert)."""
        if not self.is_configured():
            return False

        # Prepare bet data for cloud
        cloud_bet = {
            'id': bet.get('id'),
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
            'updated_at': datetime.utcnow().isoformat()
        }

        # Upsert (insert or update)
        result = self._request(
            'pending_bets?on_conflict=id',
            method='POST',
            data=cloud_bet,
            upsert=True
        )

        return result is not None

    def sync_all_pending(self, bets: List[Dict]) -> int:
        """Sync all pending bets to Supabase."""
        if not self.is_configured():
            return 0

        synced = 0
        for bet in bets:
            if self.sync_bet(bet):
                synced += 1
        return synced

    def remove_bet(self, bet_id: int) -> bool:
        """Remove a bet from cloud (when settled)."""
        if not self.is_configured():
            return False

        result = self._request(f'pending_bets?id=eq.{bet_id}', method='DELETE')
        return result is not None

    def get_pending_bets(self) -> List[Dict]:
        """Get all pending bets from cloud."""
        if not self.is_configured():
            return []

        result = self._request('pending_bets?result=is.null&order=match_date.asc')
        return result if isinstance(result, list) else []

    def mark_bet_live(self, bet_id: int, is_live: bool) -> bool:
        """Mark a bet as currently live."""
        if not self.is_configured():
            return False

        result = self._request(
            f'pending_bets?id=eq.{bet_id}',
            method='PATCH',
            data={'is_live': is_live, 'updated_at': datetime.utcnow().isoformat()}
        )
        return result is not None

    def mark_bet_finished(self, bet_id: int, result: str, profit_loss: float) -> bool:
        """Mark a bet as finished with result."""
        if not self.is_configured():
            return False

        update_result = self._request(
            f'pending_bets?id=eq.{bet_id}',
            method='PATCH',
            data={
                'result': result,
                'profit_loss': profit_loss,
                'is_live': False,
                'finished_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
        )
        return update_result is not None


# Singleton instance
_cloud_sync = None


def get_cloud_sync() -> CloudSync:
    """Get the singleton CloudSync instance."""
    global _cloud_sync
    if _cloud_sync is None:
        _cloud_sync = CloudSync()
    return _cloud_sync


def sync_bet_to_cloud(bet: Dict) -> bool:
    """Convenience function to sync a bet."""
    return get_cloud_sync().sync_bet(bet)


def remove_bet_from_cloud(bet_id: int) -> bool:
    """Convenience function to remove a bet."""
    return get_cloud_sync().remove_bet(bet_id)


# SQL to create the table (run in Supabase SQL editor)
SETUP_SQL = """
-- Create pending_bets table
CREATE TABLE IF NOT EXISTS pending_bets (
    id INTEGER PRIMARY KEY,
    match_date TEXT,
    tournament TEXT,
    match_description TEXT,
    selection TEXT,
    odds REAL,
    stake REAL,
    model TEXT,
    our_probability REAL,
    result TEXT,
    profit_loss REAL,
    is_live BOOLEAN DEFAULT FALSE,
    market_id TEXT,
    finished_at TEXT,
    updated_at TEXT,
    created_at TEXT DEFAULT NOW()
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_pending_bets_result ON pending_bets(result);
CREATE INDEX IF NOT EXISTS idx_pending_bets_is_live ON pending_bets(is_live);

-- Enable Row Level Security (optional but recommended)
ALTER TABLE pending_bets ENABLE ROW LEVEL SECURITY;

-- Allow all operations for authenticated users (using anon key)
CREATE POLICY "Allow all operations" ON pending_bets
    FOR ALL
    USING (true)
    WITH CHECK (true);
"""


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Cloud Sync for Tennis Betting')
    parser.add_argument('--setup', action='store_true', help='Print SQL to set up Supabase table')
    parser.add_argument('--test', action='store_true', help='Test the connection')
    parser.add_argument('--sync', action='store_true', help='Sync all pending bets now')
    args = parser.parse_args()

    if args.setup:
        print("Run this SQL in your Supabase SQL Editor:")
        print("=" * 50)
        print(SETUP_SQL)
        print("=" * 50)
        print("\nThen add to credentials.json:")
        print('  "supabase_url": "https://xxxxx.supabase.co",')
        print('  "supabase_key": "your-anon-key"')

    elif args.test:
        sync = CloudSync()
        if not sync.is_configured():
            print("Supabase not configured!")
            print("\nAdd to credentials.json:")
            print('  "supabase_url": "https://xxxxx.supabase.co",')
            print('  "supabase_key": "your-anon-key"')
        else:
            print("Supabase configured!")
            print(f"URL: {sync.url}")
            # Try to fetch bets
            bets = sync.get_pending_bets()
            print(f"Pending bets in cloud: {len(bets)}")

    elif args.sync:
        sync = CloudSync()
        if not sync.is_configured():
            print("Supabase not configured!")
        else:
            # Import database and sync all pending
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from database import db
            pending = db.get_pending_bets()
            print(f"Found {len(pending)} pending bets locally")
            synced = sync.sync_all_pending(pending)
            print(f"Synced {synced} bets to cloud")

    else:
        parser.print_help()
