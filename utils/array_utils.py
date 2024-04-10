import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .batch import Batch


def import_2d(path: Path, del_indexes: Optional[tuple[int, ...]] = None,
              remove_blanks: bool = True) -> list[list[str]]:
    """
    Reads a CSV file and returns a 2D list of the data

    Args:
        path (Path): The path to the CSV file
        del_indexes (Optional[tuple[int, ...]]): A tuple of indexes to delete. Defaults to None.
        if using negative indexes, please list them last, eg:
        [0,4,6,100,999,-20,-15,-2,-1]. Make sure that any positive index is not higher than a very negative index

        remove_blanks (bool, optional): If True, removes blank lines from the file. Defaults to True.
    """
    with open(path, "r") as file:
        string = file.read()
    if string.strip() == "":
        return []
    temp, final = string.split("\n"), []
    for line in temp:
        if line != "":
            final.append(line.split(","))
        elif not remove_blanks:
            final.append([])
    if del_indexes is not None:
        for i in range(len(del_indexes) - 1, -1, -1):
            del (final[del_indexes[i]])
    return final


def export_2d(path: Path, array: list | tuple, col_types: Optional[tuple[int]] = None,
              date_format: str = "%Y-%m-%d", datetime_format: str = "%Y-%m-%d %H:%M:%S.%f %Z") -> None:
    length = len(array)
    width = len(array[0])  # assuming all rows are of the same length
    string = ""
    if col_types is None:
        col_types = ["str"] * width
    for i in range(0, length):
        for x in range(0, width):
            if col_types[x] == "str":
                string += array[i][x]
            elif col_types[x] == "date":
                string += array[i][x].strftime(date_format)
            elif col_types[x] == "int":
                string += str(array[i][x])
            elif col_types[x] == "datetime":
                string += array[i][x].strftime(datetime_format)
            string += deliminator(length, width, i, x)
    with open(path, "w+") as file:
        file.write(string)


def deliminator(length: int, width: int, row_index: int, col_index: int,
                delims: list = [",", "\n"]) -> str:
    if col_index < width - 1:
        return delims[0]
    elif row_index < length - 1:
        return delims[1]
    return ""


def export_batches(path: Path, batches: list) -> None:
    array = []
    for batch in batches:
        array.extend(batch.convert_to_export_array())
    export_2d(path, array, col_types=["str", "str", "datetime"], datetime_format="%Y %a %d %b %H:%M:%S %Z")


def import_batches(batch_log_path: Path, output_path: Path, batches_path: Path = Path.cwd().joinpath("batches")) -> list[Batch]:
    batch_paths = [batch for batch in batches_path.iterdir() if batch.name.endswith(".zip")]
    # batches = [[batch, path, [run_times], prog_type],..]]
    batch_log = import_2d(batch_log_path)
    if not batch_log:
        return [Batch(path.name[:4], path, []) for path in batch_paths]
    if batch_history:
        batch_history = converter(batch_history, data_types=("str", "str", "datetime"), datetime_format="%Y %a %d %b %H:%M:%S %Z")
        for log in batch_history:
            batch_names = [batch[0] for batch in batches]
            if log[0] not in batch_names:
                batches.append([log[0], "deleted", [log[2]], log[1]])
            else:
                batches[batch_names.index(log[0])][2].append(log[2])
    return [Batch(*(batch + [Path(output_path)])) for batch in batches]


def converter(raw_data: list[list[str]], data_types: Optional[list[str] | tuple[str, ...]] = None,
              wanted_cols: Optional[list[int] | tuple[int, ...]] = None,
              date_format: str = "%Y-%m-%d", datetime_format: str = "%Y-%m-%d %H:%M:%S.%f %Z",
              time_zone: timezone = timezone.utc) -> list:
    if wanted_cols is None:
        wanted_cols = list(range(0, len(raw_data[0])))
    if data_types is None:
        data_types = ["str"] * len(raw_data[0])
    database = []
    for i in range(0, len(raw_data)):
        database.append([])
        for k in range(0, len(raw_data[i])):
            if k in wanted_cols:
                if data_types[k] == "date":
                    database[i].append(datetime.strptime(raw_data[i][k], date_format).date())
                elif data_types[k] == "str":
                    database[i].append(str(raw_data[i][k]))
                elif data_types[k] == "int":
                    database[i].append(int(raw_data[i][k]))
                elif data_types[k] == "float":
                    try:
                        database[i].append(float(raw_data[i][k]))
                    except ValueError:
                        database[i].append(0)
                elif data_types[k] == "datetime":
                    database[i].append(datetime.strptime(raw_data[i][k], datetime_format).replace(tzinfo=time_zone))
                else:
                    print("Unknown datatype detected")
    return database


def remove_blanks(array: list[list]) -> list[list]:
    """
    Removes all empty lists from the input list
    Args:
        array: The list to be cleaned
    Returns:
        The cleaned list
    """
    return [element for element in array if element != []]


def get_options(config_path: Path) -> dict:
    """
    Reads a config file and returns user-defined options, with default values if not specified

    Args:
        config_path (Path): The path to the config file
    Returns:
        A dictionary of the options
    """
    default_mappings = {"os.get_login": os.getlogin(), "None": None}
    config = import_2d(config_path, del_indexes=(0,))
    return {option[0]: option[2] if option[2] else default_mappings.get(option[1]) for option in config}
