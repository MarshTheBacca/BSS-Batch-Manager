import numpy as np
import os
from copy import deepcopy
from zipfile import ZipFile
from .other_utils import find_char_indexes, clean_name
from .validation_utils import valid_int, valid_triple, valid_csv
from .array_utils import import_2D

dashes = "--------------------------------------------------"
program_type_constants = {"netmc": {"template_file_name": "netmc_template.csv",
                                    "file_name": "netmc.inpt"},
                          "netmc_pores": {"template_file_name": "netmc_pores_template.csv",
                                          "file_name": "netmc.inpt"},
                          "triangle_raft": {"template_file_name": "triangle_raft_template.csv",
                                            "file_name": "mx2.inpt"}}

modes = {"ses": "Start, End, Step", "sen": "Start, End, Number of Steps",
         "nums": "Num1, Num2...", "any_string": "Any String",
         "selected_strings": "Selected Strings", "bool": "Boolean, 0 or 1"}


class Config:
    def __init__(self, prog_type):
        self.type = prog_type
        self.csv_file = f'common_files/{program_type_constants[prog_type]["template_file_name"]}'
        self.file_name = program_type_constants[prog_type]["file_name"]
        self.import_config()

    def import_config(self):
        def convert_config_array(array):
            return_array = []
            for i in range(0, len(array)):
                array[i].append(None)
                array[i] = [None if element == "None" else True if element == "True" else False
                            if element == "False" else element for element in array[i]]
                if array[i][6]:
                    if ";" in array[i][6]:
                        array[i][6] = array[i][6].split(";")
                if array[i][7]:
                    if ";" in array[i][7]:
                        array[i][7] = array[i][7].split(";")
                if "dual" in array[i][5]:
                    first_num, second_num = extract_dual(array[i][1])
                    second_line = [array[i][0], second_num, array[i][2], array[i][3],
                                   array[i][4], array[i][5], array[i][6][1], array[i][7][1], True]
                    array[i][1], array[i][6], array[i][7], array[i][8] = first_num, array[i][6][0], array[i][7][0], False
                    return_array.extend([array[i], second_line])
                else:
                    return_array.append(array[i])
            return return_array

        def extract_dual(string):
            space_indexes = find_char_indexes(string, " ")
            first_num = string[0:space_indexes[0]]
            second_num = string[space_indexes[-1] + 1:]
            return first_num, second_num

        array = import_2D(self.csv_file, (0,))
        array = convert_config_array(array)
        self.variables = []
        self.fillers = []
        for row in array:
            if row[2]:
                self.variables.append(Config.Var(row[0], row[1], row[3], row[4], row[5], row[6], row[7], row[8]))
            else:
                self.fillers.append(Config.Filler(row[0], row[1]))

    def export_config_string(self):
        combined = sorted(self.variables + self.fillers)
        string = ""
        for element in combined:
            if element.isinstance(Config.Filler):
                string += element.string + "\n"
            elif element.isinstance(Config.Var):
                if element.type in ("int", "float", "str", "bool"):
                    if element.valid_func == float:
                        string += str(round(element.value, 5)) + "\t\t" + element.name + "\n"
                    else:
                        string += str(element.value) + "\t\t" + element.name + "\n"
                elif element.type == "int/str":
                    string += element.value_str + str(element.value) + "\t\t" + element.name + "\n"
                elif element.type in ("dual int", "dual float", "dual bool"):
                    if not element.is_second:
                        if element.valid_func == float:
                            string += str(round(element.value, 5)) + "\t"
                        else:
                            string += str(element.value) + "\t"
                    else:
                        if element.valid_str == float:
                            string += str(round(element.value, 5)) + "\t" + element.comb_name + "\n"
                        else:
                            string += str(element.value) + "\t" + element.comb_name + "\n"
        return string.expandtabs(8)

    def generate_batch(self, cvas, var_indexes, save_path, batch_name):
        meshgrid = np.array(np.meshgrid(*cvas)).T.reshape(-1, len(cvas))
        temp_config = deepcopy(self)
        changing_vars = [temp_config.variables[i] for i in var_indexes]
        with ZipFile(f"{os.path.join(save_path, batch_name)}.zip", "x") as batch_zip:
            for i, array in enumerate(meshgrid):
                job_name = ""
                for k, value in enumerate(array):
                    if changing_vars[k].valid_func == int:
                        changing_vars[k].value = int(value)
                        job_name += f"{changing_vars[k].name}_{int(value)}__"
                    else:
                        changing_vars[k].value = value
                        job_name += f"{changing_vars[k].name}_{round(value, 3)}__"
                job_name = clean_name(job_name[:-2])
                if self.type == "netmc":
                    temp_config.variables[0].value = job_name
                elif self.type == "triangle_raft":
                    temp_config.variables[1].value = f"./output_files/{job_name}"
                config_string = temp_config.export_config_string()
                batch_zip.writestr(os.path.join(job_name, self.file_name), config_string)

    def table(self):
        return [[var.value, var.name, var.type, var.allowed_values_string] for var in self.variables if var.relevant], [i for i in range(0, len(self.variables)) if self.variables[i].relevant]

    class Var:
        def __init__(self, line, value, relevant, name, var_type, indiv_name, allowed_values, is_second):
            self.line = int(line)
            if var_type == "int/str":
                self.value, self.value_str, self.valid_func = Config.Var.convert_value(value, var_type)
            else:
                self.value, self.valid_func = Config.Var.convert_value(value, var_type)
            if indiv_name:
                self.name = indiv_name
                self.comb_name = name
            else:
                self.name = name
            self.is_second = is_second
            self.relevant = relevant
            self.type = var_type
            self.allowed_values, self.allowed_values_string, self.modes = Config.Var.allowed(allowed_values, var_type, self.valid_func)

        def convert_value(value, var_type):
            if var_type == "str":
                return value, None
            elif var_type in ("int", "dual int", "bool", "dual bool"):
                return int(value), int
            elif var_type in ("float", "dual float"):
                return float(value), float
            elif var_type == "int/str":
                value_str = value[:find_char_indexes(value, "/")[-1] + 1]
                value = int(value[find_char_indexes(value, "/")[-1] + 1:])
                return value, value_str, int

        def allowed(allowed_values, var_type, valid_func):
            def lower_upper(string, valid_func):
                if allowed_values:
                    if ">" in string:
                        try:
                            lower = valid_func(string[string.index(">") + 1:])
                        except ValueError:
                            lower = valid_func(string[string.index(">") + 1:string.index("<")])
                    else:
                        lower = float("-inf")
                    if "<" in string:
                        upper = valid_func(string[string.index("<") + 1:])
                    else:
                        upper = float("inf")
                else:
                    lower = float("-inf")
                    upper = float("inf")
                return lower, upper

            if var_type == "str":
                if allowed_values.isinstance(list):
                    allowed_values_string = ""
                    for string in allowed_values:
                        allowed_values_string += string + ", "
                    return allowed_values, allowed_values_string[:-2], ["selected_strings"]
                elif allowed_values:
                    return None, allowed_values, ["selected_strings"]
                else:
                    return None, "Any string", ["any_string"]
            elif var_type in ("int", "float", "dual int", "dual float", "int/str"):
                if allowed_values:
                    lower, upper = lower_upper(allowed_values, valid_func)
                    return [lower, upper], f"lower: {lower}\tupper: {upper}", ["ses", "sen", "nums"]
                else:
                    return None, "Any number", ["ses", "sen", "nums"]
            elif var_type in ("bool", "dual bool"):
                return [0, 1], "0 or 1", ["bool"]

        def get_cva(self):
            string = ""
            exit_num = len(self.modes) + 1
            for i, mode in enumerate(self.modes):
                string += str(i + 1) + ") " + modes[mode] + "\n"
            print(f"{string}{exit_num}) Exit\n")
            option = valid_int("How would you like to vary this variable?\n", 1, exit_num)
            if option == exit_num:
                return False, None
            mode = self.modes[option - 1]
            if mode == "ses":
                while True:
                    prompt = "Enter your start, end, step string in the form: s,e,s\n"
                    is_valid, triple = valid_triple(prompt, self.allowed_values[0], self.allowed_values[1], self.valid_func, "ses")
                    if is_valid:
                        break
                if self.valid_func == int:
                    return True, np.int_(np.round_(np.arange(triple[0], triple[1] + triple[2], triple[2])))
                else:
                    return True, np.arange(triple[0], triple[1] + triple[2], triple[2])
            elif mode == "sen":
                while True:
                    prompt = "Enter your start, end, number of steps string in the form: s,e,n\n"
                    is_valid, triple = valid_triple(prompt, self.allowed_values[0], self.allowed_values[1], self.valid_func, "sen")
                    if triple == "exit":
                        return False, None
                    if is_valid:
                        break
                if self.valid_func == int:
                    cva = np.round(np.linspace(triple[0], triple[1], triple[2]), 0)
                    print(f"The increment will be roughly: {round(cva[1] - cva[0], 0)}")
                else:
                    cva = np.round(np.linspace(triple[0], triple[1], triple[2]), 5)
                    print(f"The increment will be: {round(cva[1] - cva[0], 5)}")
                if self.valid_func == int:
                    return True, np.int_(np.round_(cva))
                else:
                    return True, cva
            elif mode in ("nums", "any_string", "selected_strings"):
                if mode == "nums":
                    prompt = "Enter your numbers in the form: Num1,Num2,...\n"
                    lower = self.allowed_values[0]
                    upper = self.allowed_values[1]
                    valid_func = self.valid_func
                    allowed_values = None
                elif mode == "any_string":
                    prompt = "Enter your strings in the form: Str1,Str2,..."
                    lower, upper, valid_func, allowed_values = None, None, None, None
                elif mode == "selected_strings":
                    prompt = "Enter your strings in the form: Str1,Str2,..."
                    lower, upper, valid_func, allowed_values = None, None, None, self.allowed_values
                while True:
                    is_valid, csv = valid_csv(prompt, mode, lower, upper, valid_func, allowed_values)
                    if csv == "exit":
                        return False, None
                    elif is_valid and self.valid_func == int:
                        return True, np.int_(np.round_(np.array(csv)))
                    elif is_valid:
                        return True, csv
            elif mode == "bool":
                return True, [0, 1]

        def __str__(self):
            if self.type in ("str", "bool", "dual bool"):
                return f"{self.line}\t\t{self.name}\t\t{self.value}\t\t{self.type}\t\t{self.accepted}"
            elif self.type in ("int", "float", "dual int", "dual float", "int/str"):
                return f"{self.line}\t\t{self.name}\t\t{self.value}\t\t{self.type}\t\t{self.lower}\t\t{self.upper}"

        def __lt__(self, other):
            if self.line == other.line:
                if self.is_second:
                    return False
            else:
                return self.line < other.line

    class Filler:
        def __init__(self, line, string):
            self.line = int(line)
            if string == "dashes":
                self.string = dashes
            else:
                self.string = string

        def __str__(self):
            return f"{self.line}\t\t{self.string}"

        def __lt__(self, other):
            return self.line < other.line
