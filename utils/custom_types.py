from enum import Enum

RELATIVE_ENERGY: float = -29400 / 392  # Energy of a perfect hexagonal network using harmonic graphene potential (E_h / node)
RELATIVE_ENTROPY: float = 0  # Entropy of the ring size distribution of a perfect hexagonal network using harmonic graphene potential per node
# There is no ring distorder as p(6) = 1. therefore S = - sum_k (p_k log(p_k)) = - 1 * log(1) = 0
RELATIVE_PEARSONS: float = 0


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
