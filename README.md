# AI_Tokamak

A Discord bot for blockchain/crypto community interaction

## Features

- Channel monitoring and AI-powered conversation responses
- LLM-based intelligent agent with tool support
- Session-based conversation history management

## Installation

```bash
# Using uv
uv sync

# Using pip
pip install -e .
```

## Configuration

Copy `config.example.json` to `config.json` and fill in the required values.

```bash
cp config.example.json config.json
```

Key settings:
- `discord.token`: Discord bot token
- `discord.monitor_channel_ids`: List of channel IDs to monitor
- `providers.openrouter.api_key`: OpenRouter API key (or use anthropic/openai)

## Usage

```bash
# Run the bot
tokamak run

# Test Discord connection
tokamak test-discord
```

## Deployment

### Railway Deployment

Deploy to Railway with environment variables (recommended for production):

1. Push your code to GitHub
2. Create a new Railway project and connect your repo
3. Set required environment variables:
   - `DISCORD_TOKEN`: Your Discord bot token
   - `OPENROUTER_API_KEY`: Your OpenRouter API key
   - `MONITOR_CHANNEL_IDS`: Comma-separated channel IDs (e.g., `123456,789012`)
4. Railway will automatically deploy using `railway.toml` configuration

See [RAILWAY_DEPLOY.md](./RAILWAY_DEPLOY.md) for detailed deployment instructions.

## License

MIT
