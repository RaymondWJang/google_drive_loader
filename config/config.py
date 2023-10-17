from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path
from yaml import safe_load


@dataclass
class CONFIG:
    SCOPES: List[str]
    SERVICE_ACCOUNT_FILE: Path

    @classmethod
    def load(cls):
        with open("config/config.yaml") as f:
            return cls(**safe_load(f))
