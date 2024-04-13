from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from tabulate import tabulate


from .other_utils import string_to_value, value_to_string
from .validation_utils import get_valid_int
from .var import BondSelectionVar, BoolVar, FloatVar, IntVar, Var
from .variation_modes import VariationMode

OUTPUT_FILE_TITLE = "Bond Switch Simulator input file"
DASHES = "--------------------------------------------------"


def read_section(input_file: TextIO, title: str, types: tuple[Var, ...]) -> Section:
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


def write_section(output_file: TextIO, section_title: str, section_dict: dict[str: BSSType]) -> None:
    output_file.write(f"{section_title}\n")
    for key, value in section_dict.items():
        output_file.write(f"{value_to_string(value):<30}{key}\n")
    output_file.write(f"{DASHES}\n")


@dataclass
class BSSInputData:
    sections: list[Section] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.variables = [var for section in self.sections for var in section.variables]
        self.table_relevant_variables = [var for var in self.variables if var.is_table_relevant]

    @staticmethod
    def from_file(path: Path) -> BSSInputData:
        with open(path, "r") as input_file:
            input_file.readline()
            network_restrictions_section = read_section(input_file, "Network Restrictions",
                                                        (IntVar(name="Minimum ring size", lower=3),
                                                         IntVar(name="Maximum ring size"),
                                                         FloatVar(name="Max bond length", lower=0),
                                                         FloatVar(name="Max bond angle", lower=0, upper=360),
                                                         BoolVar(name="Enable fixed rings", variation_modes=[VariationMode.BOOLEAN], is_table_relevant=False)))
            bond_selection_process_section = read_section(input_file, "Bond Selection Process",
                                                          (IntVar(name="Random seed"),
                                                           BondSelectionVar(name="Bond selection process", is_table_relevant=True),
                                                           FloatVar(name="Weighted decay")))
            temperature_schedule_section = read_section(input_file, "Temperature Schedule",
                                                        (FloatVar(name="Thermalising temperature"),
                                                         FloatVar(name="Annealing start temperature"),
                                                         FloatVar(name="Annealing end temperature"),
                                                         IntVar(name="Annealing steps", lower=0),
                                                         IntVar(name="Thermalising steps", lower=0)))
            analysis_section = read_section(input_file, "Analysis",
                                            (IntVar(name="Analysis write interval", lower=0, is_table_relevant=False),
                                             BoolVar(name="Write movie file", variation_modes=[VariationMode.BOOLEAN], is_table_relevant=False)))
            return BSSInputData([network_restrictions_section, bond_selection_process_section,
                                 temperature_schedule_section, analysis_section])

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
        while True:
            self.table_print()
            num_vars = len(self.variables)
            option = get_valid_int(f"Which property would you like to edit? ({num_vars + 1} to exit)\n", 1, num_vars + 1)
            if option == num_vars + 1:
                return
            self.variables[option - 1].set_value_interactive()

    def __repr__(self) -> str:
        string = "BSSInputData:\n"
        for field_name, field_value in vars(self).items():
            string += f"                 {field_name}: {field_value}\n"
        return string


@ dataclass
class Section:
    title: str
    variables: list[Var] = field(default_factory=list)

    def add_var(self, variable: Var) -> None:
        if not isinstance(variable, Var):
            raise ValueError(f"Invalid type for variable: {type(variable)}")
        self.variables.append(variable)

    def __repr__(self) -> str:
        string = f"Section: {self.title}\n"
        for variable in self.variables:
            string += f"    {variable}\n"
        return string
