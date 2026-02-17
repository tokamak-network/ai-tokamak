# Discord Bot Setup Guide

## 1. Create Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** → Enter name (e.g., `AI_Tokamak`)
3. Left menu **Bot** tab → **Reset Token** → Copy token (use as Railway `DISCORD_TOKEN`)

## 2. Enable Privileged Gateway Intents

In the **Privileged Gateway Intents** section at the bottom of the Bot tab, enable the following:

| Intent | Required | Purpose |
|---|---|---|
| **Message Content Intent** | Yes | Read message content (without this, messages come as empty strings) |
| Server Members Intent | No | Not used |
| Presence Intent | No | Not used |

## 3. Generate Bot Invite Link

Configure in the left menu **OAuth2** tab.

### Scopes

| Scope | Required |
|---|---|
| **bot** | Yes |

### Bot Permissions

The bot requires the following permissions to function properly:

| Permission | Required | Purpose |
|---|---|---|
| **View Channels** | Yes | Access monitoring channels |
| **Send Messages** | Yes | Send response messages |
| **Read Message History** | Yes | Check previous conversation context |
| **Mention @everyone, @here, and All Roles** | Yes | Use @everyone in broadcast admin command |
| **Moderate Members** | Yes | Timeout users via admin command |

**Permission Integer**: `1099499294720`

### Invite URL Format

```
https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=1099499294720&scope=bot
```

Replace `YOUR_CLIENT_ID` with the Application ID from **OAuth2** tab or **General Information** tab.

## 4. Invite Bot to Server

1. Open the URL above in a browser
2. Select the server to add the bot to
3. Review permissions and click **Authorize**

## 5. Get Channel ID

1. Enable **Developer Mode** in Discord **Settings** > **Advanced**
2. Right-click the channel to monitor → **Copy Channel ID**
3. Enter in Railway `MONITOR_CHANNEL_IDS` environment variable (comma-separated)

## Checklist

- [ ] Bot Token copied → Set in Railway `DISCORD_TOKEN`
- [ ] **Message Content Intent** enabled
- [ ] Bot Permissions: View Channels, Send Messages, Read Message History, Mention @everyone
- [ ] Bot invited to server
- [ ] Channel ID obtained → Set in Railway `MONITOR_CHANNEL_IDS`
- [ ] (Optional) Admin Channel ID → Set in Railway `ADMIN_CHANNEL_IDS` for admin commands

## 6. Get Admin Channel ID (for Admin Commands)

To enable admin commands:

1. Enable **Developer Mode** in Discord **Settings** > **Advanced**
2. Right-click the channel for admin commands → **Copy Channel ID**
3. Enter in Railway `ADMIN_CHANNEL_IDS` environment variable

> Anyone in the admin channel can execute admin commands. See RAILWAY_DEPLOY.md for available commands.