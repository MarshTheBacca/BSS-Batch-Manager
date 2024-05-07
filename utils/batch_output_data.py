from __future__ import annotations

import time
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Callable, Generator, Iterable, Optional, TypeVar

import numpy as np
from matplotlib import pyplot as plt

from .introduce_defects.utils.bss_data import BSSData
from .job import Job
from .validation_utils import confirm
from .other_utils import clean_name

T = TypeVar('T')


def progress_tracker(iterable: Iterable[T]) -> Generator[T]:
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

    def get_radial_distribution(self, refresh: bool = False) -> tuple[np.ndarray, np.ndarray]:
        """
        Gets the radial distribution of the batch

        Args:
            refresh: Whether or not to refresh the data from scratch

        Returns:
            The radii and densities of the batch
        """
        if not refresh:
            try:
                array = np.genfromtxt(self.path.joinpath("raidial_distribution.txt"))
                return array[:, 0], array[:, 1]
            except Exception as e:
                print(f"Error reading file {self.path.joinpath('raidial_distribution.txt')}: {e}")
                print("Computing ring size distribution from scratch")
        radiis = []
        densities = []
        for job in self.iterjobs():
            radial_distribution_path = job.path.joinpath("radial_distribution.txt")
            radii, density = job.bss_data.get_radial_distribution(fixed_ring_center=True, refresh=refresh, path=radial_distribution_path)
            radiis.extend(radii)
            densities.extend(density)
            del job
        radiis = np.array(radiis)
        densities = np.array(densities)
        np.savetxt(self.path.joinpath("raidial_distribution.txt"), np.column_stack((radiis, densities)))
        return radiis, densities

    def plot_radial_distribution(self, refresh: bool = False) -> None:
        """
        Plots the radial distribution of the batch (data for each job will be saved in the job's path)

        Args:
            refresh (bool): Whether or not to refresh the data from scratch
        """
        radiis, densities = self.get_radial_distribution(refresh)

        # Group densities by radius
        density_dict = {}
        for radius, density in zip(radiis, densities):
            if radius not in density_dict:
                density_dict[radius] = []
            density_dict[radius].append(density)

        # Compute mean and standard deviation at each radius
        mean_densities = []
        std_dev_densities = []
        for radius in sorted(density_dict.keys()):
            density_values = density_dict[radius]
            mean_densities.append(np.mean(density_values))
            std_dev_densities.append(np.std(density_values))

        mean_densities = np.array(mean_densities)
        std_dev_densities = np.array(std_dev_densities)

        plt.plot(radiis, densities)
        plt.fill_between(radiis, mean_densities - std_dev_densities, mean_densities + std_dev_densities, alpha=0.2)  # for shaded region
        plt.xlabel("Radius (Bohr Radii)")
        plt.ylabel("Base Node Density")
        plt.title("Radial distribution")
