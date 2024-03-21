from enum import Enum


class StructureType(Enum):
    GRAPHENE = "Graphene"
    SILICENE = "Silicene"
    TRIANGLERAFT = "TriangleRaft"
    BILAYER = "Bilayer"
    BORONNITRIDE = "BoronNitride"


class BondSelectionProcess(Enum):
    RANDOM = "Random"
    WEIGHTED = "Weighted"
