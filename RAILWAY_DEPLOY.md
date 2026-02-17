# Railway Deployment Guide

## Prerequisites

Prepare the following items before deployment.

| Item | Source |
|---|---|
| Discord Bot Token | https://discord.com/developers/applications → Bot tab → Token |
| OpenRouter API Key | https://openrouter.ai/keys |
| Monitoring Channel ID | Right-click Discord channel → Copy Channel ID |
| Server (Guild) ID (optional) | Right-click Discord server name → Copy Server ID |

> Enable **Developer Mode** in Discord **Settings** > **Advanced** to copy channel/server IDs.

## Deployment Steps

1. Push code to GitHub
2. Create a [Railway](https://railway.app) project → Connect GitHub repo
3. Set environment variables in **Variables** tab (see table below)
4. Automatic deployment starts (auto-redeploys on every push)

## Environment Variables

### Required

| Variable | Description | Example |
|---|---|---|
| `DISCORD_TOKEN` | Discord bot token | `MTIzNDU2Nzg5...` |
| `OPENROUTER_API_KEY` | OpenRouter API key | `sk-or-v1-abc...` |
| `MONITOR_CHANNEL_IDS` | Channel IDs for bot to monitor (comma-separated) | `123456789,987654321` |

### Optional

| Variable | Description | Default |
|---|---|---|
| `ALLOW_GUILDS` | Server IDs where bot operates (comma-separated). Empty = all servers | _(empty = all servers)_ |
| `AGENT_MODEL` | LLM model identifier | `qwen3-235b` |
| `OPENROUTER_API_BASE` | API endpoint URL. Set for other OpenAI-compatible servers (LiteLLM, vLLM, etc.) | _(OpenRouter default)_ |
| `CONVERSATION_TIMEOUT_SECONDS` | Conversation timeout (seconds). Conversation ends after this time from last message | `300` |
| `MAX_MESSAGES` | Maximum messages to store per session | `100` |
| `LOG_LEVEL` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |

### News Feed (Optional)

| Variable | Description | Default |
|---|---|---|
| `NEWS_FEED_ENABLED` | Enable news feed feature | `false` |
| `NEWS_FEED_INTERVAL_SECONDS` | News fetch interval (seconds) | `300` (5 min) |
| `NEWS_KOREAN_CHANNEL_ID` | Discord channel ID for Korean summaries | _(none)_ |
| `NEWS_ENGLISH_CHANNEL_ID` | Discord channel ID for English summaries | _(none)_ |
| `NEWS_SOURCES` | RSS feed URLs (comma-separated) | CoinDesk RSS |
| `NEWS_MAX_PER_FETCH` | Maximum news items to process per fetch | `15` |

> To enable news feed, set `NEWS_FEED_ENABLED=true` and specify at least one channel ID.

### Admin Commands (Optional)

| Variable | Description | Default |
|---|---|---|
| `ADMIN_CHANNEL_IDS` | Channel IDs where admin commands are accepted (comma-separated) | _(empty = no admin commands)_ |

> To enable admin commands, set `ADMIN_CHANNEL_IDS` with the channel ID(s) where admins can execute commands.

## Admin Commands

If `ADMIN_CHANNEL_IDS` is configured, anyone in those channels can use natural language commands processed by LLM:

### Available Actions

| Action | Example Request |
|---|---|
| Search user | "Find user 'John'" |
| Search channel | "Search for 'announcements' channel" |
| Timeout user | "Timeout user 'John' for 1 hour" |
| Remove timeout | "Remove timeout from 'John'" |
| Send message to channel | "Send 'Hello' to 'announcements' channel" |
| Check bot status | "What's the bot status?" |
| List active sessions | "Show me active sessions" |
| Clear session | "Clear session discord:123:456" |

### How It Works

1. Send a natural language message in the admin channel
2. LLM analyzes your request and calls appropriate tools
3. Results are returned as natural language response

> You can reference users/channels by name (no need to look up IDs). The system will search by display name, username, or nickname.

## How It Works

```
git push origin main
    ↓
Railway detects push → Nixpacks build (Python 3.11)
    ↓
python scripts/create_config.py  (env vars → config.json)
    ↓
tokamak run  (bot starts)
```

- Build settings are defined in `railway.toml`
- Up to 10 automatic restarts on failure
- SIGTERM on deploy/restart → graceful shutdown handled

## Viewing Logs

Railway dashboard → **Deployments** → Select deployment → **Logs** tab

On successful startup, you'll see:

```
✓ config.json created successfully from environment variables
INFO     | Starting Tokamak bot...
INFO     | Discord bot logged in as AI_Tokamak#1234
```

Set `LOG_LEVEL` to `DEBUG` for debugging.

## Local Testing

Test locally before deploying to Railway:

```bash
export DISCORD_TOKEN="your_token"
export OPENROUTER_API_KEY="your_key"
export MONITOR_CHANNEL_IDS="123456789"

python scripts/create_config.py && tokamak run
```

## Troubleshooting

| Symptom | Check |
|---|---|
| Bot won't start | Check Railway logs for missing environment variable errors |
| Channel not monitored | Verify `MONITOR_CHANNEL_IDS` format, check bot's channel access permissions |
| No response on specific server | Verify server ID is included in `ALLOW_GUILDS` |
| Conversation reset after redeploy | Normal behavior (sessions are in-memory, reset on redeploy) |

## Notes

- `config.json` is in `.gitignore` and won't be committed to GitHub
- API keys are only stored in Railway environment variables, never in code
- Session data is in-memory, so conversation history resets on redeployment