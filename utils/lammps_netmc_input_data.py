from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple, TextIO, Type, Any
from pathlib import Path
from enum import Enum
import os
from tabulate import tabulate

from zipfile import ZipFile
from itertools import product
from copy import deepcopy
import tempfile


from .validation_utils import get_valid_int, get_valid_str
from .other_utils import clean_name
from .var import Var, IntVar, FloatVar, StrVar, BoolVar, StructureTypeVar, BondSelectionVar
from .custom_types import StructureType, BondSelectionProcess

from .variation_modes import VariationMode

OUTPUT_FILE_TITLE = "LAMMPS-NetMC input file"
DASHES = "--------------------------------------------------"


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
                                                      (IntVar(name="Number of rings", lower=4),
                                                       IntVar(name="Minimum ring size", lower=3),
                                                       IntVar(name="Maximum ring size"),
                                                       BoolVar(name="Enable fixed rings", variation_modes=[VariationMode.BOOLEAN], is_table_relevant=False)))
            minimisation_protocols_section = read_section(input_file, "Minimisation Protocols",
                                                          (BoolVar(name="Enable OpenMPI", variation_modes=[VariationMode.BOOLEAN], is_table_relevant=False),
                                                           StructureTypeVar(name="Structure type", is_table_relevant=True)))
            monte_carlo_process_section = read_section(input_file, "Monte Carlo Process",
                                                       (IntVar(name="Random seed"),
                                                        BondSelectionVar(name="Bond selection process", is_table_relevant=True),
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

    def _generate_job_name(self, changing_vars: list[Var],
                           array: list[int | float | str | bool | StructureType | BondSelectionProcess]):
        job_name = ""
        for k, value in enumerate(array):
            job_name += f"{changing_vars[k].name}_{value_to_string(value)}__"
            changing_vars[k].value = value
        return clean_name(job_name[:-2])

    def _export_job_to_zip(self, temp_data: LAMMPSNetMCInputData,
                           batch_zip: ZipFile, job_name: str) -> None:
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_data.export(Path(temp_file.name))
            batch_zip.write(temp_file.name, arcname=Path(job_name).joinpath("netmc.inpt"))
            os.remove(temp_file.name)

    def generate_batch(self, vary_arrays: list[list[int | float | str | bool | StructureType | BondSelectionProcess]],
                       var_indexes: list[int],
                       save_path: Path) -> None:
        meshgrid = list(product(*vary_arrays))
        batch_name = get_valid_str("Enter a name for the batch ('c' to cancel)\n", forbidden_chars=[" ", "/", r"\\"],
                                   lower=1, upper=20)
        if batch_name == "c":
            return
        temp_data: LAMMPSNetMCInputData = deepcopy(self)
        changing_vars = [temp_data.table_relevant_variables[i] for i in var_indexes]
        with ZipFile(save_path.joinpath(f"{batch_name}.zip"), "x") as batch_zip:
            for array in meshgrid:
                job_name = self._generate_job_name(changing_vars, array)
                temp_data.variables[1].value = job_name
                self._export_job_to_zip(temp_data, batch_zip, job_name)

    def __repr__(self) -> str:
        string = "LAMMPSNetMCInputData:\n"
        for field_name, field_value in vars(self).items():
            string += f"                 {field_name}: {field_value}\n"
        return string


@dataclass
class Section:
    title: str
    variables: list[Var] = field(default_factory=list)

    def add_var(self, variable: Var) -> None:
        if not isinstance(variable, Var):
            raise ValueError(f"Invalid type for variable: {type(variable)}")
        self.variables.append(variable)
