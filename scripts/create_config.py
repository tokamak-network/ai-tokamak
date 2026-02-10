#!/usr/bin/env python3
"""Create config.json from environment variables for Railway deployment."""

import json
import os
import sys


def main():
    """Generate config.json from environment variables."""
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

    # Optional settings
    agent_model = os.environ.get("AGENT_MODEL", "qwen3-235b")
    conversation_timeout = int(os.environ.get("CONVERSATION_TIMEOUT_SECONDS", "300"))
    max_messages = int(os.environ.get("MAX_MESSAGES", "100"))

    # Build config
    config = {
        "discord": {
            "token": discord_token,
            "monitor_channel_ids": monitor_channel_ids,
            "allow_guilds": [],
            "conversation_timeout_seconds": conversation_timeout
        },
        "session": {
            "max_messages": max_messages
        },
        "providers": {
            "openrouter": {
                "api_key": openrouter_api_key
            }
        },
        "agent": {
            "model": agent_model,
            "enable_korean_review": True,
            "korean_review_model": None
        }
    }

    # Write config.json
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)

    print("✓ config.json created successfully from environment variables")
    print(f"  - Discord token: {'*' * 8}{discord_token[-4:]}")
    print(f"  - Monitor channels: {monitor_channel_ids}")
    print(f"  - Agent model: {agent_model}")



if __name__ == "__main__":
    main()
