from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple, TextIO, Optional, Type, Any
from pathlib import Path
from enum import Enum
from tabulate import tabulate
from abc import ABC, abstractmethod
from .validation_utils import get_valid_int
import numpy as np

OUTPUT_FILE_TITLE = "LAMMPS-NetMC input file"
DASHES = "--------------------------------------------------"


class StructureType(Enum):
    GRAPHENE = "Graphene"
    SILICENE = "Silicene"
    TRIANGLERAFT = "TriangleRaft"
    BILAYER = "Bilayer"
    BORONNITRIDE = "BoronNitride"


class BondSelectionProcess(Enum):
    RANDOM = "Random"
    WEIGHTED = "Weighted"


class VariationMode(Enum):
    STARTSTEPEND = "Start, Step, End"
    STARTENDNUM = "Start, End, Number of Steps"
    NUMS = "Numbers"
    CERTAINSTRINGS = "Certain Strings"
    ANYSTRING = "Any String"
    BOOLEAN = "Boolean"

    def get_vary_array(self, certain_strings: Optional[list[str]] = None) -> list[int | float | str | bool | StructureType | BondSelectionProcess] | None:
        handlers = {VariationMode.STARTSTEPEND: self._handle_start_step_end,
                    VariationMode.STARTENDNUM: self._handle_start_end_num,
                    VariationMode.NUMS: self._handle_nums,
                    VariationMode.CERTAINSTRINGS: self._handle_certain_strings,
                    VariationMode.ANYSTRING: self._handle_any_string,
                    VariationMode.BOOLEAN: self._handle_boolean}
        handler = handlers.get(self)
        if handler:
            return handler(certain_strings)
        else:
            raise ValueError(f"Invalid variation mode: {self}")

    def _handle_start_step_end(self, _) -> list[float]:
        while True:
            answer = input("Enter start, step, and end values separated by commas\n")
            try:
                start, step, end = answer.split(",")
                start, step, end = float(start), float(step), float(end)
                if (start < end and step <= 0) or (start > end and step >= 0):
                    raise ValueError
                break
            except ValueError:
                print("Invalid input, ensure step is positive for start < end and negative for start > end")
        return list(np.arange(start, end, step))

    def _handle_start_end_num(self, _) -> list[float]:
        while True:
            answer = input("Enter start, end, and number of steps separated by commas\n")
            try:
                start, end, num = answer.split(",")
                start, end, num = float(start), float(end), int(num)
                break
            except ValueError:
                print("Invalid input")
        return list(np.linspace(start, end, num))

    def _handle_nums(self, _) -> list[float]:
        while True:
            answer = input("Enter numbers separated by commas\n")
            try:
                return [float(num) for num in answer.split(",")]
            except ValueError:
                print("Invalid input")

    def _handle_certain_strings(self, certain_strings: list[str]) -> list[str]:
        print(f"Allowed strings: {', '.join(certain_strings)}")
        while True:
            answer = input("Enter strings separated by commas\n")
            strings = [string.strip() for string in answer.split(",")]
            for string in strings:
                if not string or string not in certain_strings:
                    print(f"Invalid string {string}")
                    break
            else:
                return strings

    def _handle_any_string(self, _) -> list[str]:
        while True:
            answer = input("Enter strings separated by commas\n")
            strings = [string.strip() for string in answer.split(",")]
            for string in strings:
                if not string:
                    break
            else:
                continue
            return strings

    def _handle_boolean(self, _) -> list[bool]:
        return [True, False]


def string_to_value(value: str, expected_type: Type[Any]) -> int | float | str | bool | StructureType | BondSelectionProcess:
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
    else:
        raise TypeError(f"Invalid expected type when trying to convert {value} to {expected_type.__name__}")


def value_to_string(value: int | float | str | bool | StructureType | BondSelectionProcess) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    elif isinstance(value, Enum):
        return str(value.value)
    else:
        return str(value)


def read_section(input_file: TextIO, title: str, types: Tuple[Var, ...]) -> Section:
    # Skip the section title and dash separator
    for _ in range(2):
        input_file.readline()
    try:
        section = Section(title=title)
        for var in types:
            var.set_value(string_to_value(input_file.readline().split()[0], var.expected_type))
            section.add_var(var)
        return section
    except ValueError as e:
        raise ValueError(f"Error reading section {title}: {e}")


def write_section(output_file: TextIO, section_title: str, section_dict: dict[str: int | float | str | bool | StructureType | BondSelectionProcess]) -> None:
    output_file.write(f"{section_title}\n")
    for key, value in section_dict.items():
        output_file.write(f"{value_to_string(value):<30}{key}\n")
    output_file.write(f"{DASHES}\n")


@dataclass
class LAMMPSNetMCInputData:
    sections: list[Section] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.variables = [var for section in self.sections for var in section.variables]
        self.table_relevant_variables = [var for var in self.variables if var.is_table_relevant]

    @staticmethod
    def from_file(path: Path) -> LAMMPSNetMCInputData:
        with open(path, "r") as input_file:
            input_file.readline()
            io_section = read_section(input_file, "I/O",
                                      (StrVar(name="Output folder", is_table_relevant=False),
                                       StrVar(name="Output prefix", is_table_relevant=False),
                                       StrVar(name="Input folder", is_table_relevant=False),
                                       StrVar(name="Input prefix", is_table_relevant=False),
                                       BoolVar(name="Create network from scratch", variation_modes=[VariationMode.BOOLEAN], is_table_relevant=False)))
            network_properties_section = read_section(input_file, "Network Properties",
                                                      (IntVar(name="Number of rings"),
                                                       IntVar(name="Minimum ring size"),
                                                       IntVar(name="Maximum ring size"),
                                                       BoolVar(name="Enable fixed rings", variation_modes=[VariationMode.BOOLEAN], is_table_relevant=False)))
            minimisation_protocols_section = read_section(input_file, "Minimisation Protocols",
                                                          (BoolVar(name="Enable OpenMPI", variation_modes=[VariationMode.BOOLEAN], is_table_relevant=False),
                                                           StructureTypeVar(name="Structure type", is_table_relevant=False)))
            monte_carlo_process_section = read_section(input_file, "Monte Carlo Process",
                                                       (IntVar(name="Random seed"),
                                                        BondSelectionVar(name="Bond selection process", is_table_relevant=False),
                                                        FloatVar(name="Weighted decay")))
            monte_carlo_energy_search_section = read_section(input_file, "Monte Carlo Energy Search",
                                                             (FloatVar(name="Thermalising temperature"),
                                                              FloatVar(name="Annealing start temperature"),
                                                              FloatVar(name="Annealing end temperature"),
                                                              IntVar(name="Annealing steps", lower=0),
                                                              IntVar(name="Thermalising steps", lower=0)))
            potential_model_section = read_section(input_file, "Potential Model",
                                                   (FloatVar(name="Max bond length", lower=0),
                                                    FloatVar(name="Max bond angle", lower=0, upper=360)))
            analysis_section = read_section(input_file, "Analysis Section",
                                            (IntVar(name="Analysis write interval", lower=0, is_table_relevant=False),
                                             BoolVar(name="Write movie file", variation_modes=[VariationMode.BOOLEAN], is_table_relevant=False),))
            return LAMMPSNetMCInputData([io_section, network_properties_section,
                                         minimisation_protocols_section, monte_carlo_process_section,
                                         monte_carlo_energy_search_section, potential_model_section,
                                         analysis_section])

    def export(self, path: Path) -> None:
        with open(path, "w+") as output_file:
            output_file.write(f"{OUTPUT_FILE_TITLE}\n")
            output_file.write(f"{DASHES}\n")
            for section in self.sections:
                output_file.write(f"{section.title}\n")
                for var in section.variables:
                    output_file.write(f"{value_to_string(var.value):<30}{var.name}\n")
                output_file.write(f"{DASHES}\n")

    def table_print(self, relevant_only: bool = False) -> None:
        if not relevant_only:
            array = [[i, var.name, value_to_string(var.value)] for i, var in enumerate(self.variables, start=1)]
        else:
            array = [[i, var.name, value_to_string(var.value)] for i, var in enumerate(self.table_relevant_variables, start=1)]
        print(tabulate(array, headers=["#", "Property", "Value"], tablefmt="fancy_grid"))

    def edit_value_interactive(self) -> None:
        self.table_print()
        num_vars = len(self.variables)
        option = get_valid_int(f"Which property would you like to edit? ({num_vars + 1} to exit)\n", 1, num_vars + 1)
        if option == num_vars + 1:
            return
        self.variables[option - 1].set_value_interactive()

    def __repr__(self) -> str:
        string = f"LAMMPSNetMCInputData: output_folder: {self.output_folder}\n"
        for field_name, field_value in vars(self).items():
            string += f"                 {field_name}: {field_value}\n"
        return string


@dataclass
class Section:
    title: str
    variables: list[Var] = field(default_factory=list)

    def add_var(self, variable: Var) -> None:
        self.variables.append(variable)


@dataclass
class Var(ABC):
    name: str
    value: Optional[int | float | str | bool | StructureType | BondSelectionProcess] = None
    is_table_relevant: bool = True
    variation_modes: list[VariationMode] = field(default_factory=list)
    certain_strings: Optional[list[str]] = None

    def __post_init__(self):
        if self.value is not None and not isinstance(self.value, (int, float, str, bool, StructureType, BondSelectionProcess)):
            raise ValueError(f"Invalid type for variable {self.name}: {type(self.value)}")

    @abstractmethod
    def set_value(self, value: int | float | str | bool | StructureType | BondSelectionProcess) -> None:
        pass

    @abstractmethod
    def set_value_interactive(self) -> None:
        pass

    def get_vary_array(self) -> list[int | float | str | bool | StructureType | BondSelectionProcess] | None:
        prompt: str = "How would you like to vary this variable?\n"
        for i, mode in enumerate(self.variation_modes, start=1):
            prompt += f"{i}) {mode.value}\n"
        prompt += f"{len(self.variation_modes) + 1}) Cancel\n"
        selection = get_valid_int(prompt, 1, len(self.variation_modes) + 1)
        if selection == len(self.variation_modes):
            return None
        return self.variation_modes[selection - 1].get_vary_array(self.certain_strings)


@dataclass
class IntVar(Var):
    lower: int | float = float("-inf")
    upper: int | float = float("inf")
    variation_modes: list[VariationMode] = field(default_factory=lambda: [VariationMode.STARTENDNUM,
                                                                          VariationMode.STARTSTEPEND,
                                                                          VariationMode.NUMS])

    def __post_init__(self):
        self.expected_type = int

    def set_value(self, value: int) -> None:
        if not isinstance(value, int):
            raise ValueError(f"Value {value} not an integer")
        if not self.lower <= value <= self.upper:
            raise ValueError(f"Value {value} not in range {self.lower} to {self.upper}")
        self.value = value

    def set_value_interactive(self) -> None:
        new_value = get_valid_int(f"Enter new value for {self.name} ({self.lower} to {self.upper}, 'c' to cancel): ", self.lower, self.upper, "c")
        if new_value is not None:
            self.set_value(new_value)


@dataclass
class FloatVar(Var):
    lower: int | float = float("-inf")
    upper: int | float = float("inf")
    variation_modes: list[VariationMode] = field(default_factory=lambda: [VariationMode.STARTENDNUM,
                                                                          VariationMode.STARTSTEPEND,
                                                                          VariationMode.NUMS])

    def __post_init__(self):
        self.expected_type = float

    def set_value(self, value: float) -> None:
        if not isinstance(value, float):
            raise ValueError(f"Value {value} not a float")
        if not self.lower <= value <= self.upper:
            raise ValueError(f"Value {value} not in range {self.lower} to {self.upper}")
        self.value = value

    def set_value_interactive(self) -> None:
        while True:
            new_value = input(f"Enter new value for {self.name} ({self.lower} to {self.upper}, 'c' to cancel): ")
            if new_value == "c":
                return
            try:
                new_value = float(new_value)
            except ValueError:
                print("Invalid float")
                continue
            if self.lower <= new_value <= self.upper:
                self.set_value(new_value)
                break
            print(f"Value {new_value} not in range {self.lower} to {self.upper}")


@dataclass
class BoolVar(Var):
    def __post_init__(self):
        self.expected_type = bool

    def set_value(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise ValueError(f"Value {value} not a boolean")
        self.value = value

    def set_value_interactive(self) -> None:
        options = {"true": True, "false": False}
        while True:
            new_value = input(f"Enter new value for {self.name} (true or false, 'c' to cancel): ").lower()
            if new_value == "c":
                return
            elif new_value in options:
                self.set_value(options[new_value])
                break
            print("Invalid input")

    def get_vary_array(self) -> list[bool]:
        return [True, False]


@dataclass
class StrVar(Var):
    variation_modes: list[VariationMode] = field(default_factory=lambda: [VariationMode.ANYSTRING])
    certain_strings: Optional[list[str]] = None

    def __post_init__(self):
        if VariationMode.CERTAINSTRINGS in self.variation_modes and self.certain_strings is None:
            raise ValueError(f"Var {self.name} has CERTAINSTRINGS variation mode but no certain strings given")
        self.expected_type = str

    def set_value(self, value: str) -> None:
        if not isinstance(value, str):
            raise ValueError(f"Value {value} not a string")
        self.value = value

    def set_value_interactive(self) -> None:
        prompt = f"Enter new value for {self.name} ('c' to cancel)\n"
        if VariationMode.CERTAINSTRINGS in self.variation_modes:
            prompt = f"Enter new value for {self.name}, choose from: "
            for string in self.certain_strings:
                prompt += f"{string}, "
            prompt = prompt[:-2] + " ('c' to cancel)\n"
        while True:
            new_value = input(prompt)
            if new_value != "c":
                if VariationMode.CERTAINSTRINGS in self.variation_modes and new_value not in self.certain_strings:
                    print(f"Value {new_value} not in list of allowed strings.")
                    continue
                self.set_value(new_value)
                break
            break


@dataclass
class BondSelectionVar(Var):
    def __post_init__(self):
        self.expected_type = BondSelectionProcess

    def set_value(self, value: BondSelectionProcess) -> None:
        if not isinstance(value, BondSelectionProcess):
            raise ValueError(f"Value {value} not a BondSelectionProcess")
        self.value = value

    def set_value_interactive(self) -> None:
        options = {"Random": BondSelectionProcess.RANDOM,
                   "Weighted": BondSelectionProcess.WEIGHTED}
        while True:
            new_value = input(f"Enter new value for {self.name} (Random or Weighted, 'c' to cancel)\n")
            if new_value in options:
                self.set_value(options[new_value])
                break
            elif new_value == "c":
                break
            print("Invalid input")

    def get_vary_array(self) -> list[BondSelectionProcess]:
        return [BondSelectionProcess.RANDOM, BondSelectionProcess.WEIGHTED]


@dataclass
class StructureTypeVar(Var):
    def __post_init__(self):
        self.expected_type = StructureType

    def set_value(self, value: StructureType) -> None:
        if not isinstance(value, StructureType):
            raise ValueError(f"Value {value} not a StructureType")
        self.value = value

    def set_value_interactive(self) -> None:
        options = {"Graphene": StructureType.GRAPHENE,
                   "Silicene": StructureType.SILICENE,
                   "TriangleRaft": StructureType.TRIANGLERAFT,
                   "Bilayer": StructureType.BILAYER,
                   "BoronNitride": StructureType.BORONNITRIDE}
        while True:
            new_value = input(f"Enter new value for {self.name} (Graphene, Silicene, TriangleRaft, Bilayer, BoronNitride, 'c' to cancel)\n")
            if new_value in options:
                self.set_value(options[new_value])
                break
            elif new_value == "c":
                break
            print("Invalid input")
