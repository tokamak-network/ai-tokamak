"""CLI entry point for tokamak."""

import asyncio

import typer
from loguru import logger

app = typer.Typer(
    name="tokamak",
    help="Discord blockchain/crypto news bot",
    no_args_is_help=True,
)


@app.command()
def run(
    config_path: str = typer.Option("config.json", "--config", "-c", help="Config file path"),
    data_dir: str = typer.Option("data", "--data", "-d", help="Data directory path"),
):
    """Run the bot."""
    from pathlib import Path
    from tokamak.app import TokamakApp
    from tokamak.config import load_config_or_exit

    config = load_config_or_exit(config_path)
    logger.info(f"Loaded config from {config_path}")

    bot = TokamakApp(config=config, data_dir=Path(data_dir))

    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise SystemExit(1)


@app.command("test-discord")
def test_discord(
    config_path: str = typer.Option("config.json", "--config", "-c", help="Config file path"),
    message: str = typer.Option("🤖 Tokamak 봇 테스트 메시지입니다!", "--message", "-m", help="Test message to send"),
):
    """Test Discord connection by sending a test message."""
    import discord
    from discord import Intents
    from tokamak.config import load_config_or_exit

    config = load_config_or_exit(config_path)

    async def _test():
        intents = Intents.default()
        client = discord.Client(intents=intents)

        @client.event
        async def on_ready():
            logger.info(f"Logged in as {client.user}")

            # Get first monitored channel
            channel_id = config.discord.monitor_channel_ids[0] if config.discord.monitor_channel_ids else None
            if not channel_id:
                logger.error("No monitor channels configured")
                await client.close()
                return

            channel = client.get_channel(channel_id)
            if not channel:
                try:
                    channel = await client.fetch_channel(channel_id)
                except Exception as e:
                    logger.error(f"Failed to fetch channel: {e}")
                    await client.close()
                    return

            if not channel:
                logger.error(f"Channel {channel_id} not found")
                await client.close()
                return

            # Send test message
            try:
                await channel.send(message)
                logger.info(f"✓ Test message sent to #{channel.name}")
            except Exception as e:
                logger.error(f"Failed to send message: {e}")

            await client.close()

        logger.info("Connecting to Discord...")
        await client.start(config.discord.token)

    asyncio.run(_test())


@app.command("generate-response")
def generate_response(
    question: str = typer.Argument(..., help="Question to ask the bot"),
    config_path: str = typer.Option("config.json", "--config", "-c", help="Config file path"),
    data_dir: str = typer.Option("data", "--data", "-d", help="Data directory path"),
):
    """Generate a response with Korean review applied."""
    from pathlib import Path
    from tokamak.app import TokamakApp
    from tokamak.config import load_config_or_exit
    from tokamak.session import Session

    config = load_config_or_exit(config_path)
    
    async def _generate():
        # Initialize app components
        bot = TokamakApp(config=config, data_dir=Path(data_dir))
        
        # Create temporary session
        session = Session(key="cli:cli")
        
        # Generate response
        logger.info(f"Question: {question}")
        logger.info("Generating response...")
        
        response = await bot.agent.run(session, question)
        
        if not response:
            logger.error("Failed to generate response")
            return
        
        # Display response
        print("\n" + "="*60)
        print(response)
        print("="*60)
        print(f"\nCharacter count: {len(response)}/2000")
    
    asyncio.run(_generate())


@app.command("show-system-prompt")
def show_system_prompt(
    config_path: str = typer.Option("config.json", "--config", "-c", help="Config file path"),
    data_dir: str = typer.Option("data", "--data", "-d", help="Data directory path"),
):
    """Display the system prompt used by the agent."""
    from pathlib import Path
    from tokamak.app import TokamakApp
    from tokamak.config import load_config_or_exit

    config = load_config_or_exit(config_path)
    
    # Initialize app to get system prompt
    bot = TokamakApp(config=config, data_dir=Path(data_dir))
    system_prompt = bot.agent.system_prompt
    
    # Print only the system prompt (no decorations)
    print(system_prompt)


if __name__ == "__main__":
    app()
