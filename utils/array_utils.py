import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


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


def deliminator(length: int, width: int, row_index: int, col_index: int,
                delims: list = [",", "\n"]) -> str:
    """
    Gets the appropriate deliminator for a given row and column

    Args:
        length: The length of the array
        width: The width of the array
        row_index: The index of the current row
        col_index: The index of the current column
        delims: The deliminators to use. Defaults to [",", "\n"].
    Returns:
        The deliminator
    """
    if col_index < width - 1:
        return delims[0]
    elif row_index < length - 1:
        return delims[1]
    return ""


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


def converter(raw_data: list[list[str]], data_types: Optional[list[str] | tuple[str, ...]] = None,
              wanted_cols: Optional[list[int] | tuple[int, ...]] = None,
              date_format: str = "%Y-%m-%d", datetime_format: str = "%Y-%m-%d %H:%M:%S.%f %Z",
              time_zone: timezone = timezone.utc) -> list:
    """
    Converts columns of data to the specified data types

    Args:
        raw_data: The data to be converted
        data_types: The types of data in each column. Defaults to None.
        wanted_cols: The columns to convert. Defaults to None.
        date_format: The format of the date columns. Defaults to "%Y-%m-%d".
        datetime_format: The format of the datetime columns. Defaults to "%Y-%m-%d %H:%M:%S.%f %Z".
        time_zone: The timezone to use for datetime columns. Defaults to timezone.utc.
    Returns:
        The converted data
    """
    if wanted_cols is None:
        wanted_cols = list(range(0, len(raw_data[0])))
    if data_types is None:
        data_types = ["str"] * len(raw_data[0])

    def convert(value, data_type):
        try:
            if data_type == "date":
                return datetime.strptime(value, date_format).date()
            elif data_type == "str":
                return str(value)
            elif data_type == "int":
                return int(value)
            elif data_type == "float":
                return float(value)
            elif data_type == "datetime":
                return datetime.strptime(value, datetime_format).replace(tzinfo=time_zone)
            else:
                print("Unknown datatype detected")
                return value
        except ValueError:
            print(f"Error converting value {value} to {data_type}")
            return value

    return [[convert(value, data_type) for value, data_type in zip(row, data_types) if i in wanted_cols] for i, row in enumerate(raw_data)]


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
    if all(len(line) == len(config[0]) for line in config):
        return {option[0]: option[2] if option[2] else default_mappings.get(option[1]) for option in config}
    raise RuntimeError("Could not load config (did you miss a comma?)")
