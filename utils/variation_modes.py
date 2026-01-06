from __future__ import annotations

from enum import Enum

import numpy as np

from .custom_types import BondSelectionProcess, BSSType, StructureType
from .validation_utils import get_valid_int


class InvalidThreeNumbers(Exception):
    pass


class OutOfRangeError(Exception):
    pass


class VariationMode(Enum):
    STARTENDSTEP = "Start, End, Step"
    STARTENDNUM = "Start, End, Number of Steps"
    NUMS = "Numbers"
    ANYSTRING = "Any String"
    BOOLEAN = "Boolean"
    BONDSELECTIONPROCESS = "Bond Selection Process"
    STRUCTURETYPE = "Structure Type"

    def get_vary_array(self, lower: float = float("-inf"), upper: float = float("inf"), round_nums: bool = False) -> list[BSSType]:
        handlers = {
            VariationMode.STARTENDSTEP: self._handle_start_end_step,
            VariationMode.STARTENDNUM: self._handle_start_end_num,
            VariationMode.NUMS: self._handle_nums,
            VariationMode.ANYSTRING: self._handle_any_string,
            VariationMode.BOOLEAN: self._handle_boolean,
            VariationMode.BONDSELECTIONPROCESS: self._handle_bond_selection_process,
            VariationMode.STRUCTURETYPE: self._handle_structure_type,
        }
        handler = handlers.get(self)
        if handler:
            return handler(lower, upper, round_nums)
        valid_modes = ", ".join(mode.name for mode in VariationMode)
        raise ValueError(f"Invalid variation mode: {self}. Valid modes are: {valid_modes}")

    def _check_in_range_and_round(self, values: list[int | float], round_nums: bool = False, lower: float = float("-inf"), upper: float = float("inf")) -> list[int | float]:
        if round_nums:
            values = [round(value) for value in values]
        if not all(lower <= value <= upper for value in values):
            raise OutOfRangeError(f"Values not in range: {lower} to {upper}")
        return values

    def _get_3_nums(self, prompt: str) -> tuple[float, float, float]:
        """Gets 3 numbers from the user, separated by commas.

        Args:
            prompt: str: The prompt to display to the user
        Raises:
            InvalidThreeNumbers: If the user does not enter 3 numbers
        Returns:
            tuple[float, float, float]: The 3 numbers entered by the user
        """
        answer = input(prompt).split(",")
        if len(answer) != 3:
            raise InvalidThreeNumbers("Invalid input, ensure 3 numbers are entered")
        try:
            return tuple(map(float, (num.strip() for num in answer)))
        except ValueError:
            raise InvalidThreeNumbers("Invalid input, ensure all values are numbers")

    def _handle_start_end_step(self, lower: float = float("-inf"), upper: float = float("inf"), round_nums: bool = False) -> list[float]:
        while True:
            try:
                start, end, step = self._get_3_nums("Enter start, end, and step separated by commas\n")
            except InvalidThreeNumbers as e:
                print(e)
                continue
            if start == end:
                print("Invalid input, ensure start is not equal to end")
                continue
            if step > end - start:
                print("Invalid input, ensure step is less than end - start")
                continue
            if (start < end and step <= 0) or (start > end and step >= 0):
                print("Invalid input, ensure step is positive for start < end and negative for start > end")
                continue
            try:
                return self._check_in_range_and_round(list(np.arange(start, end, step)), round_nums, lower, upper)
            except OutOfRangeError as e:
                print(e)

    def _handle_start_end_num(self, lower: float = float("-inf"), upper: float = float("inf"), round_nums: bool = False) -> list[float]:
        while True:
            try:
                start, end, num = self._get_3_nums("Enter start, end, and number of steps separated by commas\n")
            except InvalidThreeNumbers as e:
                print(e)
                continue
            if start == end:
                print("Invalid input, ensure start is not equal to end")
                continue
            if int(num) != num:
                print("Invalid input, ensure number of steps is an integer")
                continue
            num = int(num)
            if num < 1:
                print("Invalid input, ensure number of steps is greater than 0")
                continue
            try:
                return self._check_in_range_and_round(list(np.linspace(start, end, num)), round_nums, lower, upper)
            except OutOfRangeError as e:
                print(e)

    def _handle_nums(self, lower: float = float("-inf"), upper: float = float("inf"), round_nums: bool = False) -> list[float]:
        while True:
            answer = input("Enter numbers separated by commas\n")
            try:
                values = [float(value.strip()) for value in answer.split(",")]
            except ValueError:
                print("Invalid input, ensure all values are numbers")
                continue
            if len(values) < 2:
                print("Invalid input, ensure at least 2 numbers are entered")
                continue
            try:
                return self._check_in_range_and_round(values, round_nums, lower, upper)
            except OutOfRangeError as e:
                print(e)

    def _handle_any_string(self, _1, _2, _3) -> list[str]:
        while True:
            answer = input("Enter strings separated by commas\n")
            strings = [string.strip() for string in answer.split(",")]
            for string in strings:
                if not string:
                    break
            else:
                continue
            return strings

    def _handle_boolean(self, _1, _2, _3) -> list[bool]:
        return [True, False]

    def _handle_bond_selection_process(self, _1, _2, _3) -> list[BondSelectionProcess]:
        return self._handle_enum_selection(BondSelectionProcess)

    def _handle_structure_type(self, _1, _2, _3) -> list[StructureType]:
        return self._handle_enum_selection(StructureType)

    def _handle_enum_selection(self, enum_class: type[Enum]) -> list[Enum]:
        selected_values = dict.fromkeys(enum_class.__members__.values(), False)
        confirm_num = len(enum_class) + 1
        while True:
            prompt: str = "Please select the values you would like to add to your vary array\n"
            counter: int = 0
            for mode, selected in selected_values.items():
                counter += 1
                if selected:
                    prompt += f"[*] {counter}) {mode.value}\n"
                    continue
                prompt += f"[ ] {counter}) {mode.value}\n"
            prompt += f"{confirm_num}) Confirm\n"
            option = get_valid_int(prompt, 1, confirm_num)
            if option == confirm_num:
                vary_array = [mode for mode, selected in selected_values.items() if selected]
                if len(vary_array) < 2:
                    print("Please select at least 2 values")
                    continue
                return vary_array
            selected_values[list(selected_values.keys())[option - 1]] = not selected_values[list(selected_values.keys())[option - 1]]
