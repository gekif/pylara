"""
Config - Loads and provides access to configuration files.
Inspired by Laravel's Config facade.
"""

import os
import json
from typing import Any


class Config:
    """Loads JSON config files from the config directory."""

    def __init__(self, config_path: str):
        self._path = config_path
        self._cache: dict = {}

    def _load(self, file: str) -> dict:
        if file in self._cache:
            return self._cache[file]
        full = os.path.join(self._path, f"{file}.json")
        if os.path.exists(full):
            with open(full) as f:
                self._cache[file] = json.load(f)
        else:
            self._cache[file] = {}
        return self._cache[file]

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a config value using dot notation.
        Example: config.get('database.default')
        """
        parts = key.split(".")
        data = self._load(parts[0])
        for part in parts[1:]:
            if isinstance(data, dict):
                data = data.get(part)
            else:
                return default
            if data is None:
                return default
        return data if data is not None else default

    def set(self, key: str, value: Any):
        """Override a config value at runtime."""
        parts = key.split(".")
        data = self._load(parts[0])
        ref = data
        for part in parts[1:-1]:
            ref = ref.setdefault(part, {})
        ref[parts[-1]] = value

    def all(self, file: str) -> dict:
        return self._load(file)
