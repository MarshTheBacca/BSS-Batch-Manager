from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Type, Any
from abc import ABC, abstractmethod
from .variation_modes import VariationMode
from .validation_utils import get_valid_int
from .custom_types import StructureType, BondSelectionProcess


@dataclass
class Var(ABC):
    name: str
    value: Optional[int | float | str | bool | StructureType | BondSelectionProcess] = None
    is_table_relevant: bool = True
    variation_modes: list[VariationMode] = field(default_factory=list)
    certain_strings: Optional[list[str]] = None
    lower: float | int = float("-inf")
    upper: float | int = float("inf")
    round_nums: bool = False
    expected_type: Type[Any] = None

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
        exit_num = len(self.variation_modes) + 1
        prompt += f"{exit_num}) Cancel\n"
        selection = get_valid_int(prompt, 1, exit_num)
        if selection == exit_num:
            return None
        return self.variation_modes[selection - 1].get_vary_array(self.lower, self.upper, self.round_nums)


@dataclass
class IntVar(Var):
    variation_modes: list[VariationMode] = field(default_factory=lambda: [VariationMode.STARTENDNUM,
                                                                          VariationMode.STARTENDSTEP,
                                                                          VariationMode.NUMS])

    def __post_init__(self):
        self.round_nums = True
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
    variation_modes: list[VariationMode] = field(default_factory=lambda: [VariationMode.STARTENDNUM,
                                                                          VariationMode.STARTENDSTEP,
                                                                          VariationMode.NUMS])

    def __post_init__(self):
        self.round_nums = False
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


@dataclass
class StrVar(Var):
    variation_modes: list[VariationMode] = field(default_factory=lambda: [VariationMode.ANYSTRING])

    def __post_init__(self):
        self.expected_type = str

    def set_value(self, value: str) -> None:
        if not isinstance(value, str):
            raise ValueError(f"Value {value} not a string")
        self.value = value

    def set_value_interactive(self) -> None:
        prompt: str = f"Enter new value for {self.name} ('c' to cancel)\n"
        new_value = input(prompt)
        if new_value != "c":
            self.set_value(new_value)


@dataclass
class BondSelectionVar(Var):
    def __post_init__(self):
        self.expected_type = BondSelectionProcess
        self.variation_modes = [VariationMode.BONDSELECTIONPROCESS]

    def set_value(self, value: BondSelectionProcess) -> None:
        if not isinstance(value, BondSelectionProcess):
            raise ValueError(f"Value {value} not a BondSelectionProcess")
        self.value = value

    def set_value_interactive(self) -> None:
        option = get_valid_int("Which bond selection process would you like to set?\n"
                               "1) Random\n2) Weighted\n3) Exit\n", 1, 3)
        if option == 3:
            return
        self.set_value(list(BondSelectionProcess)[option - 1])


@dataclass
class StructureTypeVar(Var):
    def __post_init__(self):
        self.expected_type = StructureType
        self.variation_modes = [VariationMode.STRUCTURETYPE]

    def set_value(self, value: StructureType) -> None:
        if not isinstance(value, StructureType):
            raise ValueError(f"Value {value} not a StructureType")
        self.value = value

    def set_value_interactive(self) -> None:
        option = get_valid_int("Which structure type would you like to set?\n1) Graphene\n"
                               "2) Silicene\n3) TriangleRaft\n4) Bilayer\n"
                               "5) BoronNitride\n6) Exit\n", 1, 6)
        if option == 6:
            return
        self.set_value(StructureType(list(StructureType)[option - 1]))
