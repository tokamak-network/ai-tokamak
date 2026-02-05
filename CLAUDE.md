# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI_Tokamak is a Discord bot for blockchain/crypto community interaction that provides:
- Channel monitoring and AI-powered conversation responses
- LLM-based intelligent agent with tool support (web_fetch)
- Session-based conversation history management

The bot is built around a modular architecture with event-driven communication between components.

## Development Setup

```bash
# Install dependencies using uv (preferred)
uv sync

# Or using pip
pip install -e .

# Install dev dependencies
uv sync --extra dev
# or: pip install -e ".[dev]"
```

## Configuration

Copy `config.example.json` to `config.json` and configure:
- `discord.token`: Discord bot token
- `discord.monitor_channel_ids`: List of channel IDs for conversation monitoring
- `providers.openrouter.api_key`: OpenRouter API key (or use anthropic/openai provider)
- `agent.model`: LLM model identifier (e.g., "qwen3-235b", "anthropic/claude-sonnet-4")

## Common Commands

```bash
# Run the bot
tokamak run

# Test Discord connection (sends a test message to first monitored channel)
tokamak test-discord

# All commands accept --config and --data flags
tokamak run --config config.json --data data
```

## Code Quality

```bash
# Lint and format code
ruff check tokamak/
ruff format tokamak/

# Run tests (once test suite is created)
pytest
```

## Architecture

### Core Components

1. **TokamakApp** (`tokamak/app.py`): Main orchestrator that initializes and connects all components.

2. **AgentLoop** (`tokamak/agent/loop.py`): AI agent with tool-calling support. Maintains conversation history and executes tools based on LLM decisions.

3. **MessageBus** (`tokamak/bus/`): Event-driven message queue for decoupled communication between components. Enables async message dispatch between channels (Discord) and the agent.

4. **DiscordChannel** (`tokamak/channels/discord.py`): Discord integration that handles:
   - Incoming messages from monitored channels
   - Session management per user/channel
   - Response probability for non-mention messages

5. **SessionManager** (`tokamak/session/`): In-memory conversation history management per user/channel. Sessions store message history for LLM context and automatically trim old messages.

6. **ToolRegistry** (`tokamak/agent/tools/`): Manages agent tools (web_fetch) that the LLM can invoke.

7. **SkillsLoader** (`tokamak/agent/skills.py`): Dynamically loads skill definitions (prompt templates) from the workspace.

### Data Flow

**Conversation Flow**:
1. DiscordChannel receives message from monitored channel
2. SessionManager retrieves/creates session for user
3. Message added to session history
4. AgentLoop runs with session context and available tools
5. LLM may call tools (web_fetch) during response generation
6. Response sent back via MessageBus → DiscordChannel

### Key Design Patterns

- **Provider Pattern**: `providers/base.py` defines LLMProvider interface; `openai_provider.py` implements OpenAI-compatible API support (works with OpenRouter, Anthropic, OpenAI).
- **Tool Pattern**: Tools inherit from `BaseTool` and define JSON schemas for function calling. The agent loop converts tool calls to/from OpenAI function call format.
- **Event Bus**: Components communicate via MessageBus rather than direct coupling. Outbound messages are subscribed to by channels.
- **Configuration**: Pydantic-based config schema (`config/schema.py`) with validation.

## Important Context

- This project migrated essential code from the `nanobot` project (located at `~/Projects/nanobot`). Reference that codebase for similar patterns.
- The bot is specialized for Tokamak Network (blockchain project) with Korean language support in the system prompt.
- Session storage is in-memory only (resets on restart) - no persistence layer.
- Agent system prompt is defined in `tokamak/agent/loop.py` (SYSTEM_PROMPT constant).

## Development Guidelines

- Keep code simple and avoid over-engineering (per global CLAUDE.md)
- Don't modularize code that doesn't repeat
- Reference nanobot project code when implementing similar features
- All async operations use Python's asyncio
- Use loguru for logging (already imported as `logger`)
