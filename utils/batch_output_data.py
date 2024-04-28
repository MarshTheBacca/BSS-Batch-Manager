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

    def iterjobs(self) -> Generator[Job, None, None]:
        for job_path in self.jobs_path.iterdir():
            yield Job.from_files(job_path)

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

    def plot_radial_distribution(self, jobs: list[Job], num_bins: int = 1000) -> None:
        radii = np.linspace(0, np.linalg.norm(self.initial_network.dimensions[1] - self.initial_network.dimensions[0]) / 2, num_bins)
        densities = []
        for job in jobs:
            _, density = job.bss_data.get_radial_distribution(num_bins)
            densities.append(density)
        mean_density = np.mean(densities, axis=0)
        plt.plot(radii, mean_density)
