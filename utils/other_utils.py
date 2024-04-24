import multiprocessing
import subprocess
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Type
from tabulate import tabulate

from .custom_types import (BondSelectionProcess, BSSType, StructureType)
from .var import Var
from .validation_utils import get_valid_int


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


def select_path(path: Path, prompt: str, is_file: bool) -> Path | None:
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
    sorted_paths = sorted(Path.iterdir(path), key=lambda p: p.stat().st_ctime, reverse=True)
    for i, path in enumerate(sorted_paths):
        if (path.is_file() if is_file else path.is_dir()):
            name = path.name
            creation_date = datetime.fromtimestamp(path.stat().st_ctime).strftime('%d/%m/%Y %H:%M:%S')
            path_array.append((i + 1, name, creation_date))
            paths.append(path)
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


def select_network(networks_path: Path, prompt: str) -> Path | None:
    return select_path(networks_path, prompt, is_file=False)


def select_potential(potentials_path: Path, prompt: str) -> Path | None:
    return select_path(potentials_path, prompt, is_file=True)


def select_finished_batch(output_files_path: Path, prompt: str) -> Path | None:
    return select_path(output_files_path, prompt, is_file=False)
