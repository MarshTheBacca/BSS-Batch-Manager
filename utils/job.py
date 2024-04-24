from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from .bss_input_data import BSSInputData


@dataclass
class Job:
    name: str
    path: Path
    bss_input_data: BSSInputData
