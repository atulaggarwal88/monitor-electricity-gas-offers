"""
Notifiers package for energy monitoring application.
"""

from src.notifiers.slack_notifier import (
    load_seen_deals,
    save_seen_deals,
    send_slack_top_deal,
    send_slack_top_summary,
)

__all__ = [
    "load_seen_deals",
    "save_seen_deals",
    "send_slack_top_deal",
    "send_slack_top_summary",
]
