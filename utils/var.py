from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, override

from .custom_types import BondSelectionProcess, BSSType, StructureType
from .validation_utils import get_valid_int
from .variation_modes import VariationMode


@dataclass
class Var(ABC):
    name: str
    value: BSSType | None = None
    is_table_relevant: bool = True
    variation_modes: list[VariationMode] = field(default_factory=list)
    expected_type: Any = None

    def __post_init__(self) -> None:
        if self.value is not None and not isinstance(self.value, (int, float, str, bool, StructureType, BondSelectionProcess)):
            raise ValueError(f"Invalid type for variable {self.name}: {type(self.value)}")
        self.short_name = "_".join([word[:4] for word in self.name.split()])

    @abstractmethod
    def set_value(self, value: BSSType) -> None:
        pass

    @abstractmethod
    def set_value_interactive(self) -> None:
        pass

    def get_vary_array(self) -> list[BSSType] | None:
        prompt: str = "How would you like to vary this variable?\n"
        for i, mode in enumerate(self.variation_modes, start=1):
            prompt += f"{i}) {mode.value}\n"
        exit_num = len(self.variation_modes) + 1
        prompt += f"{exit_num}) Cancel\n"
        selection = get_valid_int(prompt, 1, exit_num)
        if selection is None or selection == exit_num:
            return None
        return self.variation_modes[selection - 1].get_vary_array(self.lower, self.upper, self.round_nums)

    def __eq__(self, other) -> bool:
        """Checks if two Var objects are equal based on their names."""
        if isinstance(other, Var):
            return self.name == other.name
        return False

    def __hash__(self) -> int:
        return hash(self.name)


@dataclass
class IntVar(Var):
    lower: float | int = float("-inf")
    upper: float | int = float("inf")
    variation_modes: list[VariationMode] = field(default_factory=lambda: [VariationMode.STARTENDNUM, VariationMode.STARTENDSTEP, VariationMode.NUMS])

    def __post_init__(self):
        super().__post_init__()
        self.round_nums = True
        self.expected_type = int

    @override
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

    def __hash__(self) -> int:
        return hash(self.name)


@dataclass
class FloatVar(Var):
    lower: float | int = float("-inf")
    upper: float | int = float("inf")
    variation_modes: list[VariationMode] = field(default_factory=lambda: [VariationMode.STARTENDNUM, VariationMode.STARTENDSTEP, VariationMode.NUMS])

    def __post_init__(self) -> None:
        super().__post_init__()
        self.round_nums = False
        self.expected_type = float

    @override
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

    def __hash__(self) -> int:
        return hash(self.name)


@dataclass
class BoolVar(Var):
    def __post_init__(self):
        super().__post_init__()
        self.expected_type = bool
        self.variation_modes = [VariationMode.BOOLEAN]

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
            if new_value in options:
                self.set_value(options[new_value])
                break
            print("Invalid input")

    def __hash__(self) -> int:
        return hash(self.name)


@dataclass
class BondSelectionVar(Var):
    def __post_init__(self):
        super().__post_init__()
        self.expected_type = BondSelectionProcess
        self.variation_modes = [VariationMode.BONDSELECTIONPROCESS]

    def set_value(self, value: BondSelectionProcess) -> None:
        if not isinstance(value, BondSelectionProcess):
            raise ValueError(f"Value {value} not a BondSelectionProcess")
        self.value = value

    def set_value_interactive(self) -> None:
        option = get_valid_int("Which bond selection process would you like to set?\n1) Random\n2) Weighted\n3) Exit\n", 1, 3)
        if option == 3:
            return
        self.set_value(list(BondSelectionProcess)[option - 1])

    def __hash__(self) -> int:
        return hash(self.name)


@dataclass
class StructureTypeVar(Var):
    def __post_init__(self):
        super().__post_init__()
        self.expected_type = StructureType
        self.variation_modes = [VariationMode.STRUCTURETYPE]

    def set_value(self, value: StructureType) -> None:
        if not isinstance(value, StructureType):
            raise ValueError(f"Value {value} not a StructureType")
        self.value = value

    def set_value_interactive(self) -> None:
        option = get_valid_int("Which structure type would you like to set?\n1) Graphene\n2) Silicene\n3) TriangleRaft\n4) Bilayer\n5) BoronNitride\n6) Exit\n", 1, 6)
        if option == 6:
            return
        self.set_value(StructureType(list(StructureType)[option - 1]))

    def __hash__(self) -> int:
        return hash(self.name)
