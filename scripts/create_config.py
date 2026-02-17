#!/usr/bin/env python3
"""Create config.json from environment variables for Railway deployment."""

import json
import os
import sys


def main():
    """Generate config.json from environment variables."""
    # Debug: show which required env vars are present
    required_vars = ["DISCORD_TOKEN", "OPENROUTER_API_KEY", "MONITOR_CHANNEL_IDS"]
    for var in required_vars:
        present = "✓" if os.environ.get(var) else "✗"
        print(f"  {present} {var}")

    # Required environment variables
    discord_token = os.environ.get("DISCORD_TOKEN", "")
    if not discord_token:
        print("❌ Error: DISCORD_TOKEN environment variable is required", file=sys.stderr)
        sys.exit(1)

    openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not openrouter_api_key:
        print("❌ Error: OPENROUTER_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    # Parse monitor channel IDs
    monitor_channel_ids_str = os.environ.get("MONITOR_CHANNEL_IDS", "")
    monitor_channel_ids = []
    if monitor_channel_ids_str:
        try:
            monitor_channel_ids = [
                int(x.strip())
                for x in monitor_channel_ids_str.split(",")
                if x.strip()
            ]
        except ValueError as e:
            print(f"❌ Error parsing MONITOR_CHANNEL_IDS: {e}", file=sys.stderr)
            sys.exit(1)

    if not monitor_channel_ids:
        print("⚠️  Warning: MONITOR_CHANNEL_IDS is empty. Bot will not monitor any channels.")

    # Parse allow guild IDs
    allow_guilds_str = os.environ.get("ALLOW_GUILDS", "")
    allow_guilds = []
    if allow_guilds_str:
        try:
            allow_guilds = [
                int(x.strip())
                for x in allow_guilds_str.split(",")
                if x.strip()
            ]
        except ValueError as e:
            print(f"❌ Error parsing ALLOW_GUILDS: {e}", file=sys.stderr)
            sys.exit(1)

    # Optional settings
    agent_model = os.environ.get("AGENT_MODEL", "qwen3-235b")
    openrouter_api_base = os.environ.get("OPENROUTER_API_BASE", "")
    conversation_timeout = int(os.environ.get("CONVERSATION_TIMEOUT_SECONDS", "300"))
    max_messages = int(os.environ.get("MAX_MESSAGES", "100"))

    news_feed_enabled = os.environ.get("NEWS_FEED_ENABLED", "false").lower() == "true"
    news_feed_interval = int(os.environ.get("NEWS_FEED_INTERVAL_SECONDS", "300"))
    news_korean_channel = os.environ.get("NEWS_KOREAN_CHANNEL_ID", "")
    news_english_channel = os.environ.get("NEWS_ENGLISH_CHANNEL_ID", "")
    news_sources_str = os.environ.get("NEWS_SOURCES", "")
    news_max_per_fetch = int(os.environ.get("NEWS_MAX_PER_FETCH", "15"))

    # Admin settings
    admin_channel_ids_str = os.environ.get("ADMIN_CHANNEL_IDS", "")
    admin_command_prefix = os.environ.get("ADMIN_COMMAND_PREFIX", "!")

    admin_channel_ids = []
    if admin_channel_ids_str:
        try:
            admin_channel_ids = [
                int(x.strip())
                for x in admin_channel_ids_str.split(",")
                if x.strip()
            ]
        except ValueError as e:
            print(f"❌ Error parsing ADMIN_CHANNEL_IDS: {e}", file=sys.stderr)
            sys.exit(1)

    news_sources = []
    if news_sources_str:
        news_sources = [s.strip() for s in news_sources_str.split(",") if s.strip()]

    # Build config
    config = {
        "discord": {
            "token": discord_token,
            "monitor_channel_ids": monitor_channel_ids,
            "allow_guilds": allow_guilds,
            "conversation_timeout_seconds": conversation_timeout
        },
        "session": {
            "max_messages": max_messages
        },
        "providers": {
            "openrouter": {
                "api_key": openrouter_api_key,
            **({"api_base": openrouter_api_base} if openrouter_api_base else {})
            }
        },
        "agent": {
            "model": agent_model,
            "enable_korean_review": True,
            "korean_review_model": None
        },
        "news_feed": {
            "enabled": news_feed_enabled,
            "interval_seconds": news_feed_interval,
            "news_sources": news_sources if news_sources else [
                "https://www.coindesk.com/arc/outboundfeeds/rss/"
            ],
            "korean_channel_id": int(news_korean_channel) if news_korean_channel else None,
            "english_channel_id": int(news_english_channel) if news_english_channel else None,
            "max_news_per_fetch": news_max_per_fetch,
            "summary_model": None
        },
        "admin": {
            "admin_channel_ids": admin_channel_ids,
            "command_prefix": admin_command_prefix
        }
    }

    # Write config.json
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)

    print("✓ config.json created successfully from environment variables")
    print(f"  - Discord token: {'*' * 8}{discord_token[-4:]}")
    print(f"  - Monitor channels: {monitor_channel_ids}")
    print(f"  - Allow guilds: {allow_guilds or 'all'}")
    print(f"  - Agent model: {agent_model}")
    if news_feed_enabled:
        print(f"  - News feed: enabled (interval: {news_feed_interval}s)")
        if news_korean_channel:
            print(f"    - Korean channel: {news_korean_channel}")
        if news_english_channel:
            print(f"    - English channel: {news_english_channel}")



if __name__ == "__main__":
    main()
