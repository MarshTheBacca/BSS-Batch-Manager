from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from .job import Job
from (..Introduce - Defects.utils.bss_data) import BSSData


@dataclass
class BatchOutputData:
    name: str
    path: Path
    initial_network: BSSData
    jobs: list[Job] = field(default_factory=list)
    run_number: Optional[int] = None

    @staticmethod
    def from_files(path: Path) -> BatchOutputData:
        name = path.parent.name
        run_number = int(path.name[4:])
        return BatchOutputData(name, path, run_number)
