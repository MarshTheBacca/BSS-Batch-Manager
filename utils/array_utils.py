from datetime import datetime, timezone
from pathlib import Path
from os import scandir, getlogin
from .batch import Batch
from .other_utils import get_ip


def import_2D(path: Path, del_indexes: list = None, remove_blanks: bool = True) -> list:
    # if using negative indexes, please list them last. For example:
    # [0,4,6,100,999,-20,-15,-2,-1]
    # -1 is the highest index, equivilent to len(array)-1
    # Make sure that any positive index is not higher than a very negative index
    with open(path, "r") as file:
        string = file.read()
    if string.strip() == "":
        return None
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


def export_2D(path: Path, array: list, col_types: list = None,
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
        array.extend(batch.convert_to_export_array(timezone.utc))
    export_2D(path, array, col_types=["str", "str", "datetime"], datetime_format="%Y %a %d %b %H:%M:%S %Z")


def import_batches(batch_history_path: Path, output_path: Path, batches_path: Path = Path.cwd().joinpath("batches")) -> list:
    programs = [prog.name for prog in scandir(batches_path) if prog.is_dir()]
    batches = []
    for prog in programs:
        prog_batches = [batch.name[:-4] for batch in scandir(batches_path.joinpath(prog)) if batch.name.endswith(".zip")]
        #               0      1        2           3
        # batches = [[batch, path, [run_times], prog_type],..]]
        batches.extend([[batch, batches_path.joinpath(prog, f"{batch}.zip"), [], prog] for batch in prog_batches])
    batch_history = import_2D(batch_history_path)
    if batch_history:
        batch_history = converter(batch_history, data_types=("str", "str", "datetime"), datetime_format="%Y %a %d %b %H:%M:%S %Z")
        for log in batch_history:
            batch_names = [batch[0] for batch in batches]
            if log[0] not in batch_names:
                batches.append([log[0], "deleted", [log[2]], log[1]])
            else:
                batches[batch_names.index(log[0])][2].append(log[2])
    # batches = [[name, path, run_times, type]]
    batches = [Batch(*(batch + [Path(output_path)])) for batch in batches]
    return batches


def batch_table(batches: list, prog_type: str, t_zone: timezone) -> list:
    table = []
    batches.sort(reverse=True)
    # date_batches = list(filter(lambda batch: isinstance(batch.last_ran, datetime), batches))
    # date_batches.sort(key = lambda batch: batch.last_ran, reverse = True)
    # none_batches = list(filter(lambda batch: type(batch.last_ran) == None, batches))
    # batches = date_batches + none_batches
    for batch in batches:
        if batch.type == prog_type and batch.path != "deleted":
            table.append(batch.convert_to_array(t_zone))
    return table


def converter(raw_data: list, data_types: list = None, wanted_cols: list = None,
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


def remove_blanks(array: list) -> list:
    return_array = [element for element in array if element != []]
    return return_array


def get_config_options(config_path: Path, indexes: list, cwd: Path) -> list:
    default_mappings = {"get_ip": get_ip(), "os.get_login": getlogin(), "None": None, "get_output_path": cwd.joinpath("output_files")}
    config = import_2D(config_path, del_indexes=(0,))
    return_list = []
    for i in indexes:
        if config[i][1]:
            return_list.append(config[i][1])
        else:
            return_list.append(default_mappings[config[i][2]])
    return return_list


def print_table(array: list, headers: tuple | list, max_col_lengths: tuple | list = None,
                num_lines: int = None, num_offset: int = 0, dims: int = 2) -> None:
    if num_lines is None:
        num_lines = len(array)
    if max_col_lengths is None:
        max_col_lengths = [999 for element in array[0]]
    max_lengths = [len(header) for header in headers]
    if dims == 2:
        for row in array:
            for i, ele in enumerate(row, 0):
                ele_tab = str(ele) + "\t"
                ele_length = len(ele_tab.expandtabs(4))
                if ele_length >= max_col_lengths[i]:
                    max_lengths[i] = max_col_lengths[i] + 2
                elif max_lengths[i] < ele_length:
                    max_lengths[i] = ele_length
        string = "Number\t"
        shift = [0 for element in array[0]]
        for i, header in enumerate(headers, 0):
            diff = max_lengths[i] - len(header)
            if diff == 0:
                shift[i] = 2
                diff = 2
            string += header + " " * diff
        string += "\n" + "=" * len(string.expandtabs(4)) + "\n"
        for i in range(0, num_lines):
            num_string = str(i + 1 + num_offset) + ")\t\t"
            line = num_string
            for k in range(0, len(array[i])):
                breakout = 0
                diff = max_lengths[k] - len(str(array[i][k]))
                col_string = str(array[i][k]) + " " * (diff + shift[k])
                if len(col_string) > max_col_lengths[k]:
                    line = num_string
                    row = array[i]
                    while True:
                        wrap = [0 for element in row]
                        for z, element in enumerate(row):
                            if len(str(element)) > max_col_lengths[z]:
                                wrap[z] = 1
                        cropped_row = ["" for element in row]
                        for z, element in enumerate(row):
                            if wrap[z] == 1:
                                snip = element[:max_col_lengths[z]]
                                line += snip + " " * (max_lengths[z] - len(snip))
                                cropped_row[z] = element[max_col_lengths[z]:]
                            else:
                                line += str(element) + " " * (max_lengths[z] - len(str(element)))
                        if cropped_row == ["" for element in row]:
                            breakout = 1
                            break
                        line += "\n" + len(num_string.expandtabs(4)) * " "
                        row = cropped_row

                else:
                    line += col_string
                if breakout == 1:
                    break
            string += line + "\n"
        print(string)
    elif dims == 1:
        string = "Number\t" + str(headers)
        max_length = 0
        element_lengths = []
        for element in array:
            element_lengths.append(len(str(element)))
        max_length = max(element_lengths)
        if max_length > max_col_lengths[0]:
            max_length = max_col_lengths[0]
        string += "\n" + "=" * (max_length + len(("Number\t").expandtabs(4))) + "\n"
        for i, element in enumerate(array):
            element_string = str(element)
            num_string = str(i + 1 + num_offset) + ")\t\t"
            element_length = element_lengths[i]
            line = num_string
            if element_length > max_col_lengths[0]:
                while True:
                    snip = element_string[:max_col_lengths[0]]
                    snop = element_string[max_col_lengths[0]:]
                    line += snip + "\n"
                    if snop == "":
                        break
                    else:
                        element_string = snop
                    line += " " * len(num_string.expandtabs(4))
            else:
                line += str(element) + "\n"
            string += line
        print(string)
    else:
        print("Error: Function can only handle 1D and 2D arrays")
