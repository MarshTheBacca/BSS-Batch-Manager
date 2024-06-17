import datetime
import itertools
import multiprocessing
import subprocess
import time
from enum import Enum
from pathlib import Path
from typing import Any, Generator, Iterable, Optional, Type, TypeVar
from scipy.optimize import fsolve

import numpy as np
from tabulate import tabulate

from .custom_types import BondSelectionProcess, BSSType, StructureType
from .validation_utils import get_valid_int, get_valid_str
from .var import Var

T = TypeVar('T')


def find_char_indexes(string: str, target_char: str, invert: bool = False) -> list[int]:
    """
    Finds the indexes of all occurrences of the target character in the string
    Args:
        string: The string to be searched
        target_char: The character to be found
        invert: Whether or not to invert the search
    Returns:
        A list of the indexes of the target character in the string
    """
    return [i for i, char in enumerate(string) if (char == target_char) is not invert]


def clean_name(string: str, conversions: dict[str, str] = {"(": "", ")": "", "^": "pow", " ": "_"}) -> str:
    """
    Converts all occurrences of characters in the conversions dictionary to their corresponding value in the string
    Args:
        string: The string to be cleaned
        conversions: The dictionary of characters to be converted
    Returns:
        The cleaned string
    """
    return "".join(conversions.get(char, char) for char in string)


def background_process(command_array: tuple[str, ...] | list[str], silent: bool = True) -> None:
    """
    Starts a background process with the given command array that does not terminate when the parent process does
    Args:
        command_array: The command array to be run
        silent: Whether or not to suppress output from the process
    """
    process = multiprocessing.Process(target=child_process, args=[command_array, silent])
    process.daemon = True
    process.start()


def child_process(command_array: tuple[str, ...] | list[str], silent: bool = True) -> None:
    """
    Processes the command array in a new session
    Args:
        command_array: The command array to be run
        silent: Whether or not to suppress output from the process
    """
    if silent:
        subprocess.Popen(command_array, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(command_array, start_new_session=True)


def string_to_value(value: str, expected_type: Type[Any]) -> BSSType:
    """
    Converts a string to a value of the expected type
    Args:
        value: The value to be converted
        expected_type: The expected type of the value
    Returns:
        The converted value
    Raises:
        TypeError if an unknown expected type is given
        ValueError if the string fails to be converted to the expected type
    """
    if expected_type == int:
        return int(value)
    elif expected_type == float:
        return float(value)
    elif expected_type == bool:
        return value.lower() == "true"
    elif expected_type == StructureType:
        return StructureType(value)
    elif expected_type == BondSelectionProcess:
        return BondSelectionProcess(value)
    elif expected_type == str:
        return value
    raise TypeError(f"Invalid expected type when trying to convert {value} to {expected_type.__name__}")


def value_to_string(value: BSSType) -> str:
    """
    Converts a value to a string
    Args:
        value: The value to be converted
    Returns:
        The converted value as a string
    """
    if isinstance(value, bool):
        return str(value).lower()
    elif isinstance(value, Enum):
        return str(value.value)
    else:
        return str(value)


def generate_job_name(changing_vars: list[Var], array: list[BSSType]) -> str:
    """
    Generates a job name by concatenating each variable name with its given value

    Args:
        changing_vars: The list of variables that are being changed
        array: The list of values that the variables are being set to
    Returns:
        The generated job name
    """
    job_name = ""
    for k, value in enumerate(array):
        job_name += f"{changing_vars[k].short_name}_{value_to_string(value)}__"
        changing_vars[k].value = value
    return clean_name(job_name[:-2])


def select_path(path: Path, prompt: str, is_file: bool, secondary_path: Optional[Path] = None) -> Path | None:
    """
    Select a path to load from the given directory
    Args:
        path: directory to search for paths
        is_file: if True, search for files, else search for directories
    Returns:
        the path of the file/directory to load or None if the user cancels
    """
    path_array = []
    paths = []
    primary_paths = Path.iterdir(path)
    if secondary_path is not None:
        secondary_paths = Path.iterdir(secondary_path)
    else:
        secondary_paths = []
    all_paths = itertools.chain(primary_paths, secondary_paths)
    sorted_paths = sorted(all_paths, key=lambda p: p.stat().st_ctime, reverse=True)
    count = 1
    for path in sorted_paths:
        if (path.is_file() if is_file else path.is_dir()):
            name = path.name
            creation_date = datetime.datetime.fromtimestamp(path.stat().st_ctime).strftime('%d/%m/%Y %H:%M:%S')
            path_array.append((count, name, creation_date))
            paths.append(path)
            count += 1
    if not path_array:
        print(f"No {'files' if is_file else 'directories'} found in {path}")
        return None
    exit_num = len(path_array) + 1
    print(tabulate(path_array, headers=["Number", "Name", "Creation Date"], tablefmt="fancy_grid"))
    prompt += f" ({exit_num} to exit):\n"
    option = get_valid_int(prompt, 1, exit_num)
    if option == exit_num:
        return None
    return paths[option - 1]


def select_network(networks_path: Path, prompt: str, secondary_path: Optional[Path] = None) -> Path | None:
    return select_path(networks_path, prompt, False, secondary_path)


def select_potential(potentials_path: Path, prompt: str) -> Path | None:
    return select_path(potentials_path, prompt, True)


def select_finished_batch(output_files_path: Path, prompt: str) -> Path | None:
    return select_path(output_files_path, prompt, False)


def get_batch_name(batches_path: Path) -> str | None:
    """
    Ask the user for a name for the batch

    Args:
        batches_path: the path to the batches directory
    Returns:
        the name of the batch
    Raises:
        UserCancelledError: if the user cancels entering a batch name
    """
    while True:
        batch_name = get_valid_str("Enter a name for the batch ('c' to cancel)\n", forbidden_chars=[" ", "/", r"\\"],
                                   lower=1, upper=40)
        if batch_name == "c":
            return None
        if batch_name[0].isdigit():
            print("Batch names cannot start with a number, please try again")
            continue
        if batches_path.joinpath(f"{batch_name}.zip").exists():
            print("A batch with that name already exists, please try again")
            continue
        try:
            batches_path.joinpath(batch_name).mkdir()
            return batch_name
        except FileExistsError:
            print("A batch with that name already exists, please try again")


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
            print(f'Processed {i}/{total} items ({i / total * 100:.0f}%). Elapsed time: {datetime.timedelta(seconds=elapsed_time)}')


def get_polygon_area_estimate(num_sides: int, side_length: float) -> float:
    """
    Estimates the area of a polygon with the given number of sides and side length using the formula for the area of a regular polygon

    Args:
        num_sides: The number of sides of the polygon
        side_length: The length of each side of the polygon
    Returns:
        The estimated area of the polygon
    """
    return (num_sides * side_length ** 2) / (4 * np.tan(np.pi / num_sides))


def clockwise_order_coords(coords: list[np.ndarray]) -> list[np.ndarray]:
    """
    Orders the coordinates of a polygon in clockwise order around the center of the polygon

    Args:
        coords: The coordinates of the polygon
    Returns:
        The coordinates of the polygon in clockwise order
    """
    coords = np.array(coords)
    num_coords = len(coords)
    if num_coords < 3:
        return coords
    center = np.mean(coords, axis=0)
    angles = np.arctan2(coords[:, 1] - center[1], coords[:, 0] - center[0])
    return coords[np.argsort(angles)]


def get_polygon_area(coords: list[np.ndarray]) -> float:
    """
    Calculates the area of a polygon with the given coordinates using the Shoelace formula
    also known as Gauss's area formula or the surveyor's formula

    Args:
        coords: The coordinates of the polygon
    Returns:
        The area of the polygon
    """
    num_coords = len(coords)
    if num_coords < 3:
        return 0
    coords = clockwise_order_coords(coords)
    area = 0
    for i in range(num_coords):
        j = (i + 1) % num_coords
        area += coords[i][0] * coords[j][1]
        area -= coords[j][0] * coords[i][1]
    return abs(area) / 2


def dict_to_string(dictionary: dict, deliminator: str = ";", pair_deliminator: str = ":") -> str:
    """
    Converts a dictionary to a string with deliminators, be sure not to have strings with the deliminators included in themselves!

    Args:
        dictionary (dict): the dictionary to convert
        deliminator (str): the deliminator between key, value pairs
        pair_deliminator (str): the deliminator between keys and values
    """
    return deliminator.join(f"{key}{pair_deliminator}{value}" for key, value in dictionary.items())
