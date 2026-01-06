from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from matplotlib import pyplot as plt

from .bss_input_data import BSSInputData
from .bss_output_data import BSSOutputData
from .introduce_defects.utils.bss_data import BSSData
from .other_utils import clean_name

if TYPE_CHECKING:
    from pathlib import Path

    from .var import Var


@dataclass
class Job:
    name: str
    path: Path
    bss_data: BSSData
    bss_input_data: BSSInputData
    bss_output_data: BSSOutputData
    changing_vars: set[Var]

    def __post_init__(self) -> None:
        self.energy = self.bss_output_data.energies[-1]
        self.changing_vars_dict = {var.name: var.value for var in self.changing_vars}

    @staticmethod
    def from_files(path: Path, fixed_rings_path: Path | None = None) -> Job:
        """Creates a Job object

        Args:
            path: Path to the job folder
            fixed_rings_path: Optional path to the fixed_rings.txt file, usually from the initial network
        """
        bss_input_data = BSSInputData.from_file(path.joinpath("bss_parameters.txt"))
        changing_vars_names = ["_".join(splice.split("_")[:-1]) for splice in path.name.split("__")]
        changing_vars = {var for var in bss_input_data.variables if var.short_name in changing_vars_names or var.name in changing_vars_names}
        name = ""
        for var in changing_vars:
            name += f"{var.name}_{var.value}__"
        name = name[:-2]
        bss_data = BSSData.from_files(path.joinpath("output_files"), fixed_rings_path)
        bss_output_data = BSSOutputData(path.joinpath("output_files", "bss_stats.csv"))
        return Job(name, path, bss_data, bss_input_data, bss_output_data, changing_vars)

    def create_image(self, output_path: Path | None = None, title: str | None = None) -> None:
        if output_path is None:
            output_path = self.path.joinpath("network.svg")
        if title is None:
            title = self.name
        _, max_ring_size = self.bss_data.get_ring_size_limits()
        self.bss_data.draw_graph_pretty(draw_dimensions=True, title=clean_name(title), threshold_size=max_ring_size)
        plt.savefig(output_path)
        plt.clf()
