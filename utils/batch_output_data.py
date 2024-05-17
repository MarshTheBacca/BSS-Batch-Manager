from __future__ import annotations

import itertools
import time
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Callable, Generator, Iterable, Optional, TypeVar

import numpy as np
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

from .introduce_defects.utils.bss_data import BSSData
from .job import Job
from .other_utils import clean_name
from .validation_utils import confirm
from .bss_output_data import BSSOutputData

T = TypeVar('T')

RELATIVE_ENERGY = -29400 / 392  # Energy of a perfect network (E_h / node)


def progress_tracker(iterable: Iterable[T]) -> Generator[T, None, None]:
    total = len(iterable)
    start = time.time()

    for i, item in enumerate(iterable, start=1):
        yield item
        if total < 10 or i % (total // 10) == 0 or i == total:
            elapsed_time = time.time() - start
            print(f'Processed {i}/{total} items ({i / total * 100:.0f}%). Elapsed time: {elapsed_time:.2f} seconds.')


def track_progress(func: Callable[..., Iterable[T]]) -> Callable[..., list[T]]:
    @wraps(func)
    def wrapper(*args, **kwargs) -> list[T]:
        result = func(*args, **kwargs)
        if isinstance(result, (list, set, tuple, dict, str, Path)):
            return list(progress_tracker(result))
        else:
            return result
    return wrapper


@track_progress
def get_files(path: Path) -> list[Path]:
    return list(path.iterdir())


@dataclass
class BatchOutputData:
    name: str
    path: Path
    initial_network: BSSData
    run_number: Optional[int] = None

    def __post_init__(self) -> None:
        self.jobs_path = self.path.joinpath("jobs")

    @staticmethod
    def from_files(path: Path) -> BatchOutputData:
        name = path.parent.name
        run_number = int(path.name[4:])
        initial_network = BSSData.from_files(path.joinpath("initial_network"))
        return BatchOutputData(name, path, initial_network, run_number)

    def iterjobs(self, track_progress: bool = True) -> Generator[Job, None, None]:
        """
        Iterates over all jobs in the batch

        Args:
            track_progress: Whether or not to print progress updates in 10% increments

        Yields:
            The next job in the batch
        """
        job_paths = list(self.jobs_path.iterdir())
        if track_progress:
            job_paths = progress_tracker(job_paths)
        for job_path in job_paths:
            yield Job.from_files(job_path, self.path.joinpath("initial_network", "fixed_rings.txt"))

    def get_any_job(self) -> Job:
        """
        Gets any job in the batch
        """
        return next(self.iterjobs(False))

    def create_images(self, save_path: Optional[Path] = None, seed_skip: bool = False, refresh: bool = False) -> None:
        """
        Creates an image of each job in the batch, skipping networks that have already had an image created
        and have not been updated since the image creation

        Args:
            save_path: The path to save the images (defaults to batch_output_path/images)
            seed_skip: Whether or not the function will only create an image once per set of seeds
            refresh: deletes all existing images instead of skipping remaking them
        """
        if save_path is None:
            save_path = self.path.joinpath("images")
        if refresh and save_path.exists() and confirm("Are you sure you want to delete all existing images? (y/n)\n"):
            print("Removing all existing images ...")
            for image in save_path.iterdir():
                if image.suffix == ".svg":
                    image.unlink()
        save_path.mkdir(exist_ok=True)
        existing_images = {image.stem: image for image in save_path.iterdir() if image.suffix == ".svg"}
        covered_sections = set()
        for job in self.iterjobs():
            non_seed_vars = frozenset(var for var in job.changing_vars if var.name != "Random seed")
            if seed_skip and non_seed_vars in covered_sections:
                continue
            covered_sections.add(non_seed_vars)
            image = existing_images.get(job.name)
            network_path = job.path.joinpath("output_files")
            if image and image.stat().st_mtime > max(file.stat().st_mtime for file in network_path.glob('**/*') if file.is_file()):
                continue
            job.create_image(save_path.joinpath(f"{clean_name(job.name)}.svg"))

    def get_radial_distributions(self, refresh: bool = False) -> tuple[np.ndarray, np.ndarray]:
        """
        Gets the radial distribution of the batch

        Args:
            refresh: Whether or not to refresh the data from scratch

        Returns:
            The radii (1D array as they're all the same) and densities (2D array) of the batch
        """
        if not refresh:
            try:
                array = np.genfromtxt(self.path.joinpath("raidial_distribution.txt"))
                return array[:, 0], array[:, 1:]
            except Exception as e:
                print(f"Error reading file {self.path.joinpath('raidial_distribution.txt')}: {e}")
                print("Computing ring size distribution from scratch")
        average_bond_length = self.get_any_job().bss_data.get_bond_length_info(refresh)[0]
        densities = []
        for job in self.iterjobs():
            _, density = job.bss_data.get_radial_distribution(fixed_ring_center=True, refresh=refresh, bin_size=average_bond_length / 10)
            densities.append(density)
            del job
        # Assume densities is a list of 1D arrays of different lengths
        max_length = max(len(density) for density in densities)
        padded_densities = [np.pad(density, (0, max_length - len(density))) for density in densities]

        # Now you can stack them into a 2D array
        densities_array = np.column_stack(padded_densities)
        radii = np.arange(0, max_length) * average_bond_length
        np.savetxt(self.path.joinpath("raidial_distribution.txt"), np.column_stack((radii, densities_array)))
        return radii, densities_array

    def plot_radial_distribution(self, refresh: bool = False) -> None:
        """
        Plots the radial distribution of the batch (data for each job will be saved in the job's path)

        Args:
            refresh (bool): Whether or not to refresh the data from scratch
        """
        radii, densities = self.get_radial_distributions(refresh)
        mean_densities = np.mean(densities, axis=1)
        std_dev_densities = np.std(densities, axis=1)

        _, ax = plt.subplots()
        ax.plot(radii, mean_densities)
        ax.fill_between(radii, mean_densities - std_dev_densities, mean_densities + std_dev_densities, alpha=0.2)  # for shaded region
        ax.set_xlabel("Radius (Bohr Radii)")
        ax.set_ylabel("Base Node Density")
        ax.set_title("Radial distribution")
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.xaxis.set_ticks_position('bottom')
        ax.yaxis.set_ticks_position('left')
        ax.set_xlim(left=0)
        ax.set_ylim(bottom=0)

    def get_ring_size_distribution(self, fixed_ring_center: bool = True,
                                   refresh: bool = False, bin_size: Optional[float] = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        # Try to get existing data to save computation time
        info_path = self.path.joinpath("ring_size_distribution.txt")
        if not refresh:
            try:
                array = np.genfromtxt(info_path)
                return array[:, 0], array[:, 1], array[:, 2]
            except Exception as e:
                print(f"Error reading file {info_path}: {e}")
                print("Computing ring size distribution from scratch")
        # Bin size is the length of each radius bin
        if bin_size is None:
            bin_size = self.get_any_job().bss_data.get_bond_length_estimate() / 10

        ring_distribution = np.concatenate([job.bss_data.get_ring_size_distances(fixed_ring_center) for job in self.iterjobs()])
        # Sort the nodes by distance
        ring_distribution = ring_distribution[ring_distribution[:, 0].argsort()]

        # Bin the distances
        distances, ring_sizes = zip(*ring_distribution)
        bins = np.arange(min(distances), max(distances), bin_size)
        bin_indices = np.digitize(distances, bins)

        # Group the nodes by bin and calculate the average ring size for each bin
        radii = []
        avg_ring_sizes = []
        std_dev_ring_sizes = []
        for bin_index, group in itertools.groupby(zip(bin_indices, ring_sizes), key=lambda x: x[0]):
            ring_sizes = [x[1] for x in group]
            avg_ring_size = np.mean(ring_sizes)
            std_dev_ring_size = np.std(ring_sizes)
            radii.append(bins[bin_index - 1] + bin_size / 2)  # use the center of the bin as the radius
            avg_ring_sizes.append(avg_ring_size)
            std_dev_ring_sizes.append(std_dev_ring_size)
        try:
            np.savetxt(info_path, np.column_stack((radii, avg_ring_sizes, std_dev_ring_sizes)))
        except Exception as e:
            print(f"Error writing file {info_path}: {e}")
            print("Data not saved")
        return np.array(radii), np.array(avg_ring_sizes), np.array(std_dev_ring_sizes)

    def plot_ring_size_distribution(self, fixed_ring_center: bool = True, refresh: bool = False) -> None:
        """
        Plots the ring size distribution of the batch (data for each job will be saved in the job's path)

        Args:
            fixed_ring_center: Whether or not to use the fixed ring center
            refresh: Whether or not to refresh the data from scratch
        """
        radii, avg_ring_sizes, std_dev_ring_sizes = self.get_ring_size_distribution(fixed_ring_center, refresh)
        _, ax = plt.subplots()
        ax.plot(radii, avg_ring_sizes)
        ax.fill_between(radii, avg_ring_sizes - std_dev_ring_sizes, avg_ring_sizes + std_dev_ring_sizes, alpha=0.2)  # for shaded region
        ax.set_xlabel("Radius (Bohr Radii)")
        ax.set_ylabel("Average Ring Size")
        ax.set_title("Ring size distribution")
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.xaxis.set_ticks_position('bottom')
        ax.yaxis.set_ticks_position('left')
        ax.set_xlim(left=0)
        ax.set_ylim(bottom=0)

    def plot_energy_vs_temperatures(self):
        """
        Plots the energy of the jobs as a function of the annealing and thermalising temperatures
        """
        annealing_temps = []
        thermalising_temps = []
        energies = []
        for job in self.iterjobs():
            annealing_temps.append(job.changing_vars_dict["Annealing end temperature"])
            thermalising_temps.append(job.changing_vars_dict["Thermalising temperature"])
            energies.append(job.energy)

        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        scatter = ax.scatter(annealing_temps, thermalising_temps, energies, c=energies, cmap='viridis')
        ax.set_xlabel("Annealing Temperature")
        ax.set_ylabel("Thermalising Temperature")
        ax.set_zlabel("Energy")
        ax.set_title("Energy vs. Annealing and Thermalising Temperatures")
        fig.colorbar(scatter, ax=ax, label='Energy')

        plt.show()
