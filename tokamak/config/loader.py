"""Configuration loader."""

import json
from pathlib import Path

from tokamak.config.schema import Config


def load_config(path: str | Path = "config.json") -> Config:
    """
    Load configuration from a JSON file.

    Args:
        path: Path to the config file (default: config.json)

    Returns:
        Config object

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValidationError: If config is invalid
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            f"Copy config.example.json to {path} and fill in your settings."
        )

    with open(path) as f:
        data = json.load(f)

    return Config.model_validate(data)


def load_config_or_exit(path: str | Path = "config.json") -> Config:
    """
    Load configuration, printing error and exiting on failure.

    Args:
        path: Path to the config file

    Returns:
        Config object
    """
    from loguru import logger

    try:
        return load_config(path)
    except FileNotFoundError as e:
        logger.error(str(e))
        raise SystemExit(1)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        raise SystemExit(1)
