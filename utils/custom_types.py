from enum import Enum
from typing import Type


class StructureType(Enum):
    GRAPHENE = "Graphene"
    SILICENE = "Silicene"
    TRIANGLERAFT = "TriangleRaft"
    BILAYER = "Bilayer"
    BORONNITRIDE = "BoronNitride"


class BondSelectionProcess(Enum):
    RANDOM = "Random"
    WEIGHTED = "Weighted"


BSSType = int | float | str | bool | StructureType | BondSelectionProcess
