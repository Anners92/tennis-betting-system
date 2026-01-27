"""
Discord Notifier - Send alerts to Discord via webhook.

Setup:
1. In Discord, right-click a channel → Edit Channel → Integrations → Webhooks
2. Create a webhook, copy the URL
3. Add to credentials.json: "discord_webhook": "https://discord.com/api/webhooks/..."
"""

import json
import urllib.request
import urllib.error
import os
import sys
from typing import Dict, Optional
from datetime import datetime


def get_app_directory() -> str:
    """Get the directory where the app is running from."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        src_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.dirname(src_dir)


def load_webhook_url() -> Optional[str]:
    """Load Discord webhook URL from credentials.json."""
    app_dir = get_app_directory()
    creds_path = os.path.join(app_dir, 'credentials.json')

    if os.path.exists(creds_path):
        try:
            with open(creds_path, 'r') as f:
                creds = json.load(f)
                return creds.get('discord_webhook', '')
        except Exception:
            pass
    return None


class DiscordNotifier:
    """Send notifications to Discord via webhook."""

    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or load_webhook_url()

    def is_configured(self) -> bool:
        """Check if webhook is configured."""
        # Disabled - alerts now handled by local_monitor.py
        return False

    def send_message(self, content: str) -> bool:
        """Send a simple text message."""
        if not self.is_configured():
            return False

        payload = {"content": content}
        return self._post(payload)

    def send_embed(self, title: str, description: str = "", color: int = 0x3498db,
                   fields: list = None, footer: str = None) -> bool:
        """Send a rich embed message."""
        if not self.is_configured():
            return False

        embed = {
            "title": title,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if description:
            embed["description"] = description

        if fields:
            embed["fields"] = fields

        if footer:
            embed["footer"] = {"text": footer}

        payload = {"embeds": [embed]}
        return self._post(payload)

    def send_bet_live_alert(self, bet: Dict) -> bool:
        """Send an alert when a bet goes live."""
        if not self.is_configured():
            return False

        match_desc = bet.get('match_description', 'Unknown Match')
        selection = bet.get('selection', '?')
        odds = bet.get('odds', 0)
        stake = bet.get('stake', 0)
        model = bet.get('model', 'Unknown')
        tournament = bet.get('tournament', '')

        # Blue for all live alerts
        color = 0x3498db

        fields = [
            {"name": "Selection", "value": f"**{selection}**", "inline": True},
            {"name": "Odds", "value": f"**{odds:.2f}**", "inline": True},
            {"name": "Stake", "value": f"**{stake:.1f}u**", "inline": True},
            {"name": "Model", "value": model, "inline": True},
        ]

        if tournament:
            fields.append({"name": "Tournament", "value": tournament, "inline": True})

        return self.send_embed(
            title=f"🎾 LIVE: {match_desc}",
            color=color,
            fields=fields,
            footer="Tennis Betting System"
        )

    def send_bet_result_alert(self, bet: Dict, result: str) -> bool:
        """Send an alert when a bet is settled."""
        if not self.is_configured():
            return False

        match_desc = bet.get('match_description', 'Unknown Match')
        selection = bet.get('selection', '?')
        odds = bet.get('odds', 0)
        stake = bet.get('stake', 0)
        profit_loss = bet.get('profit_loss', 0)

        if result == 'Win':
            emoji = "✅"
            color = 0x22c55e
            pl_str = f"+{profit_loss:.2f}u"
        elif result == 'Loss':
            emoji = "❌"
            color = 0xef4444
            pl_str = f"{profit_loss:.2f}u"
        else:
            emoji = "⚪"
            color = 0x6b7280
            pl_str = "Void"

        fields = [
            {"name": "Selection", "value": selection, "inline": True},
            {"name": "Odds", "value": f"{odds:.2f}", "inline": True},
            {"name": "P/L", "value": f"**{pl_str}**", "inline": True},
        ]

        return self.send_embed(
            title=f"{emoji} {result.upper()}: {match_desc}",
            color=color,
            fields=fields,
            footer="Tennis Betting System"
        )

    def _post(self, payload: Dict) -> bool:
        """POST payload to webhook."""
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'TennisBettingSystem/1.0'
                },
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 204
        except Exception as e:
            print(f"Discord webhook error: {e}")
            return False


# Singleton instance
_notifier = None


def get_notifier() -> DiscordNotifier:
    """Get the singleton Discord notifier instance."""
    global _notifier
    if _notifier is None:
        _notifier = DiscordNotifier()
    return _notifier


def notify_bet_live(bet: Dict) -> bool:
    """Convenience function to notify when a bet goes live."""
    return get_notifier().send_bet_live_alert(bet)


def notify_bet_result(bet: Dict, result: str) -> bool:
    """Convenience function to notify when a bet is settled."""
    return get_notifier().send_bet_result_alert(bet, result)


if __name__ == "__main__":
    # Test the notifier
    notifier = DiscordNotifier()

    if not notifier.is_configured():
        print("Discord webhook not configured!")
        print("\nTo set up:")
        print("1. In Discord: Right-click channel > Edit Channel > Integrations > Webhooks")
        print("2. Create webhook and copy URL")
        print("3. Add to credentials.json:")
        print('   "discord_webhook": "https://discord.com/api/webhooks/..."')
    else:
        print("Discord webhook configured!")
        print("Sending test message...")

        # Test embed
        success = notifier.send_embed(
            title="🎾 Test Alert",
            description="Discord notifications are working!",
            color=0x22c55e,
            fields=[
                {"name": "Status", "value": "Connected", "inline": True},
            ],
            footer="Tennis Betting System"
        )

        if success:
            print("Test message sent successfully!")
        else:
            print("Failed to send test message")
