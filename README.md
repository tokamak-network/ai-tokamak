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

## License

MIT
