from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt

TRUE_FALSE_MAP = {"true": True, "false": False}


@dataclass
class BSSOutputData:
    file_path: Path

    def __post_init__(self) -> None:
        self.steps: list[int] = []
        self.temperatures: list[float] = []
        self.energies: list[float] = []
        self.entropies: list[float] = []
        self.pearson_coeffs: list[float] = []
        self.aboav_weaires: list[float] = []
        self.ring_sizes: list[dict] = []
        with open(self.file_path, "r") as file:
            for _ in range(4):
                file.readline()
            lines = file.readlines()
        for line in lines[:-3]:
            line = line.split(",")
            self.steps.append(int(line[0]))
            self.temperatures.append(float(line[1]))
            self.energies.append(float(line[2]))
            self.entropies.append(float(line[3]))
            self.pearson_coeffs.append(float(line[4]))
            self.aboav_weaires.append(float(line[5]))
            self.ring_sizes.append({int(ring_size): float(proportion) for ring_size, proportion in (pair.split(":") for pair in line[6].split(";"))})
        misc_stats = lines[-1].split(",")
        self.num_steps: int = int(misc_stats[0])
        self.num_accepted: int = int(misc_stats[1])
        self.num_failed_angle_checks: int = int(misc_stats[2])
        self.num_failed_bond_length_checks: int = int(misc_stats[3])
        self.num_failed_energy_checks: int = int(misc_stats[4])
        self.acceptance_rate: float = float(misc_stats[5])
        self.total_run_time: float = float(misc_stats[6])
        self.average_time_per_step: float = float(misc_stats[7])
        self.consistent: bool = TRUE_FALSE_MAP[misc_stats[8].rstrip().lower()]

    def summarise(self) -> None:
        print("Number of steps:", self.num_steps)
        print("Number of accepted steps:", self.num_accepted)
        print("Number of failed angle checks:", self.num_failed_angle_checks)
        print("Number of failed bond length checks:", self.num_failed_bond_length_checks)
        print("Number of failed energy checks:", self.num_failed_energy_checks)
        print("Acceptance rate:", self.acceptance_rate)
        print(f"Total run time: {self.total_run_time} s")
        print(f"Average time per step: {self.average_time_per_step} us")

    def plot_energy(self) -> None:
        plt.plot(self.steps, self.energies)
        plt.title("Energy per Step")
        plt.xlabel("Step")
        plt.ylabel("Energy (Hartrees)")
        plt.show()

    def plot_temperature(self, log: bool = False) -> None:
        if log:
            plt.semilogy(self.steps, self.temperatures)
        else:
            plt.plot(self.steps, self.temperatures)
        plt.title("Temperature per Step")
        plt.xlabel("Step")
        plt.ylabel("Temperature (au)")
        plt.show()

    def plot_entropy(self) -> None:
        plt.plot(self.steps, self.entropies)
        plt.title("Entropy change over time")
        plt.xlabel("Step")
        plt.ylabel("Entropy (Hartrees Temperature^-1)")
        plt.show()

    def plot_pearsons_coeffs(self) -> None:
        plt.plot(self.steps, self.pearson_coeffs)
        plt.ylim(-1, 1)
        plt.title("Pearson's Correlation Coefficient per Step")
        plt.xlabel("Step")
        plt.ylabel("Pearson's Correlation Coefficient")
        plt.show()

    def plot_aboav_weaire(self) -> None:
        plt.plot(self.steps, self.aboav_weaires)
        plt.title("Aboav-Weaire Parameter Change per Step")
        plt.xlabel("Step")
        plt.ylabel("Aboav-Weaire Parameter")
        plt.show()

    def plot_ring_sizes(self) -> None:
        # Get all unique ring sizes across all steps
        all_ring_sizes = sorted(set(k for d in self.ring_sizes for k in d.keys()))

        # Create a 2D list where each sublist represents a ring size over time
        ring_sizes_transposed = [[step.get(ring_size, 0) for step in self.ring_sizes] for ring_size in all_ring_sizes]

        # Filter out ring sizes that are always zero
        ring_sizes_filtered = [ring for ring in ring_sizes_transposed if sum(ring) > 0]

        # Create labels for the ring sizes
        ring_labels = ['Ring Size ' + str(ring_size) for ring_size, ring in zip(all_ring_sizes, ring_sizes_transposed) if sum(ring) > 0]

        plt.stackplot(self.steps, *ring_sizes_filtered, labels=ring_labels)
        plt.title('Proportion of Ring Sizes per Step')
        plt.xlabel('Step')
        plt.ylabel('Proportion')

        # Set the limits of the x-axis and y-axis
        plt.gca().set_xlim([0, max(self.steps)])
        plt.gca().set_ylim([0, 1])

        # Place the legend outside of the plot
        plt.legend(loc='upper left', bbox_to_anchor=(1, 1))
        plt.tight_layout()
        plt.show()

    # def plot_ring_areas(self) -> None:
    #     ring_areas = [area for areas in self.ring_areas for area in areas]
    #     steps = [step for step, areas in enumerate(self.ring_areas) for _ in areas]

    #     plt.hist2d(steps, ring_areas, bins=[len(self.steps), round(max(ring_areas)-min(ring_areas)+1)], cmap='plasma')
    #     plt.colorbar(label='Frequency')
    #     plt.title("Ring Area Distribution per Step")
    #     plt.xlabel("Step")
    #     plt.ylabel("Ring Area (Bohr Radii^2)")
    #     plt.show()

    # def plot_check_ring_areas(self, max_area: Optional[float]) -> None:
    #     plt.xlim([0, max(self.steps)])
    #     plt.ylim([0, max([sum(areas) for areas in self.ring_areas])])
    #     if max_area is not None:
    #         plt.plot(self.steps, [max_area for _ in self.steps], 'k--')
    #     plt.plot(self.steps, [sum(areas) for areas in self.ring_areas])
    #     plt.title("Total Ring Area per Step")
    #     plt.xlabel("Step")
    #     plt.ylabel("Total Ring Area (Bohr Radii^2)")
    #     plt.show()
