from collections import deque
from pathlib import Path
from typing import Generator, Optional, Iterable, Callable, TypeVar
import time
from functools import wraps
from matplotlib import pyplot as plt

RELATIVE_ENERGY = -29400 / 392  # Energy of a perfect network (E_h / node)

T = TypeVar('T')


def progress_tracker(iterable: Iterable[T], total: int) -> Generator[T, None, None]:
    """
    Writes progress to the console as the iterable is processed.

    Args:
        iterable: The iterable to process.
        total: The total number of items in the iterable.

    Returns:
        The processed iterable.
    """
    start = time.time()
    for i, item in enumerate(iterable, start=1):
        yield item
        if total < 10 or i % (total // 10) == 0 or i == total:
            elapsed_time = time.time() - start
            print(f'Processed {i}/{total} items ({i / total * 100:.0f}%). Elapsed time: {elapsed_time:.2f} seconds.')


def get_last_energy(job_path: Path) -> float | None:
    try:
        with job_path.joinpath("output_files", "bss_stats.csv").open() as file:
            last_lines = deque(file, maxlen=4)
        energy = float(last_lines[0].split(",")[2])
        return energy
    except Exception as e:
        print(f"Error reading BSS output data from {job_path}: {e}")
        return None


def get_num_nodes(job_path: Path) -> int | None:
    with job_path.parent.parent.joinpath("initial_network", "base_network_info.txt").open() as file:
        for line in file:
            if "Number of nodes" in line:
                return int(line.split(":")[1])
    return None


def process_jobs(job_list: list[tuple[Path, int]]) -> Generator[tuple[float, int], None, None]:
    errored_job_file = Path(__file__).parent.parent.joinpath("errored_jobs.txt")
    with errored_job_file.open("w") as file:  # Clear the file
        for job_path, pore_size in job_list:
            num_nodes = get_num_nodes(job_path)
            energy = get_last_energy(job_path)
            if energy is not None and num_nodes is not None:
                yield energy / num_nodes - RELATIVE_ENERGY, pore_size
            else:
                file.write(str(job_path) + "\n")


def get_energy_vs_pore_size(job_list: list[tuple[Path, int]], refresh: bool = False) -> tuple[list[float], list[int]]:
    existing_data_path = Path(__file__).parent.parent.joinpath("thesis_results", "energy_vs_pore.txt")
    if not refresh and existing_data_path.exists():
        try:
            with open(existing_data_path) as existing_file:
                pore_sizes, energies = zip(*[line.split(",") for line in existing_file])
            return list(map(float, energies)), list(map(int, pore_sizes))
        except (ValueError, PermissionError, FileExistsError) as e:
            print("Error reading existing data file: ", e)
    print("Generating data from scratch")
    job_generator = progress_tracker(process_jobs(job_list), len(job_list))
    energies, pore_sizes = zip(*list(job_generator))
    try:
        with open(existing_data_path, "w") as file:
            for energy, pore_size in zip(energies, pore_sizes):
                file.write(f"{pore_size},{energy}\n")
    except (IOError, PermissionError) as e:
        print("Error writing data to file: ", e)
    return list(energies), list(pore_sizes)


def plot_energy_vs_pore_size(job_list: list[tuple[Path, int]], refresh: bool = False) -> None:
    energies, pore_sizes = get_energy_vs_pore_size(job_list, refresh)
    _, ax = plt.subplots()
    ax.scatter(pore_sizes, energies)
    ax.set_xlabel("Pore Size")
    ax.set_ylabel("Energy per Node (Hartrees)")
    ax.set_title("Energy vs. Pore Size")
    plt.show()
