from __future__ import annotations

import copy
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import gridspec
from matplotlib.colors import ListedColormap

from .bss_output_data import BSSOutputData
from .custom_types import RELATIVE_ENERGY, BSSType
from .introduce_defects.utils.bss_data import BSSData
from .introduce_defects.utils.other_utils import (calculate_angles_around_node,
                                                  pbc_vector)
from .other_utils import (dict_to_string, get_polygon_area,
                          get_polygon_area_estimate, string_to_value)
from .plotting_utils import (add_colourbar_2, arrowed_spines, format_axes,
                             get_ring_colours_4, remove_axes)
from .var import BondSelectionVar, BoolVar, FloatVar, IntVar, Var

short_name_to_var: dict[str: Var] = {"Mini_ring_size": IntVar(name="Minimum ring size", lower=3),
                                     "Maxi_ring_size": IntVar(name="Maximum ring size"),
                                     "Max_bond_leng": FloatVar(name="Max bond length", lower=0),
                                     "Max_bond_angl": FloatVar(name="Max bond angle", lower=0, upper=360),
                                     "Enab_fixe_ring": BoolVar(name="Enable fixed rings", is_table_relevant=False),
                                     "Rand_seed": IntVar(name="Random seed"),
                                     "Bond_sele_proc": BondSelectionVar(name="Bond selection process", is_table_relevant=True),
                                     "Weig_deca": FloatVar(name="Weighted decay"),
                                     "Ther_temp": FloatVar(name="Thermalising temperature"),
                                     "Anne_star_temp": FloatVar(name="Annealing start temperature"),
                                     "Anne_end_temp": FloatVar(name="Annealing end temperature"),
                                     "Anne_step": IntVar(name="Annealing steps", lower=0),
                                     "Ther_step": IntVar(name="Thermalising steps", lower=0),
                                     "Anal_writ_inte": IntVar(name="Analysis write interval", lower=0, is_table_relevant=False),
                                     "Writ_movi_file": BoolVar(name="Write movie file", is_table_relevant=False)}
SIDE_LENGTH: float = 2.1580672


def convert_dictionary_column(series: pd.Series, deliminator_1: str = ";", deliminator_2: str = ":") -> pd.Series:
    """
    Converts a series of strings to a series of dictionaries of integers to floats
    """
    return series.apply(lambda x: {int(item.split(deliminator_2)[0]): float(item.split(deliminator_2)[1]) for item in x.split(deliminator_1)})


def get_last_data_line(job_path: Path) -> list[str]:
    """
    Gets the last line of the bss_stats.csv file in the output_files directory of the job

    Args:
        job_path: the path to the job directory

    Returns:
        the last line of the bss_stats.csv file as a list of strings
    """
    with job_path.joinpath("output_files", "bss_stats.csv").open() as file:
        last_lines = deque(file, maxlen=4)
    return last_lines[0].strip().split(",")


def get_info_data(path: Path) -> tuple[int, np.ndarray]:
    """
    Reads the dimensions from a BSS info file (num nodes is not necessary)

    Args:
        path: the path to the info file

    Raises:
        FileNotFoundError: if the info file does not exist
        TypeError: if the xhi and yhi values are not floats
        IndexError: if the xhi and yhi values are not present in the file

    Returns:
        the number of nodes and dimensions of the system
    """
    with open(path, "r") as info_file:
        num_nodes = int(info_file.readline().strip().split(":")[1])
        xhi = info_file.readline().strip().split()[1]  # Get the xhi value
        yhi = info_file.readline().strip().split()[1]  # Get the yhi value
    return num_nodes, np.array([[0, 0], [float(xhi), float(yhi)]])


def get_changing_vars(job_path: Path) -> list[Var]:
    """
    Parses the job name to get the changing variables as Var objects

    Args:
        job_path: the path to the job directory

    Raises:
        TypeError: if an unknown short name is found

    Returns:
        a list of Var objects with the changing variables set
    """
    changing_vars_dict = {pair.rsplit("_", 1)[0]: pair.rsplit("_", 1)[1] for pair in job_path.name.split("__")}
    changing_vars = []
    try:
        for short_name, string_value in changing_vars_dict.items():
            var: Var = copy.deepcopy(short_name_to_var.get(short_name, None))
            if var is None:
                raise TypeError(f"Unidentified short name {short_name}")
            var.set_value(string_to_value(string_value, var.expected_type))
            changing_vars.append(var)
    except Exception as e:
        print("Error parsing job name for job {job_path.name} in batch {job_path.parent.name}:")
        print(e)
        raise
    return changing_vars


def get_changing_vars_dict(changing_vars: list[Var]) -> dict[str, BSSType]:
    """
    Converts changing vars into a dictionary

    Args:
        changing_vars: the list of changing variables

    Returns:
        a dictionary with the variable names as keys and the values as values
    """
    return {var.name: var.value for var in changing_vars}


def get_ring_size_distribution(string: str, deliminator: str = ";", pair_deliminator: str = ":") -> dict[int, float]:
    """
    Converts a dictionary string with deliminators ; and : into a dictionary with integers keys and float values

    Args:
        string (str): the string to parse
        deliminator (str): the deliminator between key, value pairs
        pair_deliminator (str): the deliminator between keys and values

    Raises:
        ValueError if unable to convert key, value pairs into integers and floats
    """
    return {int(key): float(value) for item in string.split(deliminator) for key, value in [item.split(pair_deliminator)]}


def get_fixed_ring_coords(job_path: Path) -> tuple[list[np.ndarray], int]:
    """
    Gets the coordinates of the base nodes of a fixed ring in a job

    Args:
        job_path: the path to the job directory

    Returns:
        a list of numpy arrays with the x and y coordinates of the base nodes of the fixed ring
    """
    with job_path.parents[1].joinpath("initial_network", "fixed_rings.txt").open() as file:
        fixed_ring_id = int(file.readline().strip())
    with job_path.joinpath("output_files", "dual_network_dual_connections.txt").open() as file:
        # get the fixed_ring_id"th line from the file
        for _ in range(fixed_ring_id):
            file.readline()
        base_node_ids = [int(node_id) for node_id in file.readline().strip().split()]
    counter = 0
    fixed_ring_coords = []
    with job_path.joinpath("output_files", "base_network_coords.txt").open() as file:
        for line in file:
            if counter in base_node_ids:
                x, y = line.strip().split()
                fixed_ring_coords.append(np.array([float(x), float(y)]))
            counter += 1
    return fixed_ring_coords, fixed_ring_id


def get_num_rings(job_path: Path) -> int:
    """
    Gets the number of rings in a job

    Args:
        job_path: the path to the job directory

    Returns:
        the number of rings in the job
    """
    with job_path.joinpath("output_files", "dual_network_info.txt").open() as info_file:
        return int(info_file.readline().strip().split(":")[1])


def array_2d_to_string(array: np.ndarray, deliminator_1: str = ";", deliminator_2: str = ":") -> str:
    """
    Converts a 2D numpy array to a string with deliminators, be sure not to have strings with the deliminators included in themselves!

    Args:
        array (np.ndarray): the array to convert
        deliminator_1 (str): the deliminator between rows
        deliminator_2 (str): the deliminator between columns
    """
    return deliminator_1.join(deliminator_2.join(str(value) for value in row) for row in array)


def string_to_2d_array(string: str, deliminator_1: str = ";", deliminator_2: str = ":") -> np.ndarray:
    """
    Converts a string with deliminators into a 2D numpy array

    Args:
        string (str): the string to parse
        deliminator_1 (str): the deliminator between rows
        deliminator_2 (str): the deliminator between columns

    Raises:
        ValueError if unable to convert key, value pairs into integers and floats
    """
    return np.array([[float(value) for value in row.split(deliminator_2)] for row in string.split(deliminator_1)])


def read_adjacencies(path: Path) -> list[list[int]]:
    """
    Reads a connections file and returns a 2D array of adjacencies indexed by node
    """
    with path.open() as file:
        return [list(map(int, line.strip().split())) for line in file]


def get_ring_areas(ring_coords: np.ndarray, ring_adjacencies: list[list[int]], dimensions: np.ndarray, exlucde_ids: set[int]) -> np.ndarray:
    """
    Gets the areas of the rings in the network without making a BSSData object
    """
    ring_areas = []
    for node, neighbours in enumerate(ring_adjacencies):
        if node in exlucde_ids:
            continue
        neighbour_coords = np.array([pbc_vector(ring_coords[node], ring_coords[neighbour], dimensions) for neighbour in neighbours])
        ring_areas.append(get_polygon_area(neighbour_coords))
    return np.array(ring_areas)


def get_ring_area_variance(ring_coords: np.ndarray, ring_adjacencies: list[list[int]], dimensions: np.ndarray, exlucde_ids: set[int]) -> float:
    """
    Gets the variance of the areas of the rings in the network without making a BSSData object
    """
    return np.var(get_ring_areas(ring_coords, ring_adjacencies, dimensions, exlucde_ids))


def get_angles(node_coords: np.ndarray, adjacencies: list[list[int]], dimensions: np.ndarray) -> np.ndarray:
    """
    Gets the bond angles of the network without making a BSSData object
    """
    # Estimate the total number of angles
    total_angles = sum(len(neighbours) for neighbours in adjacencies)
    bond_angles = np.empty(total_angles, dtype=float)
    angle_idx = 0
    for node, neighbours in enumerate(adjacencies):
        neighbour_coords = np.array([pbc_vector(node_coords[node], node_coords[neighbour], dimensions) for neighbour in neighbours])
        angles = calculate_angles_around_node(np.array([0, 0]), neighbour_coords)
        bond_angles[angle_idx:angle_idx + len(angles)] = angles
        angle_idx += len(angles)
    return bond_angles


def get_angle_variance(node_coords: np.ndarray, adjacencies: list[list[int]], dimensions: np.ndarray) -> float:
    """
    Gets the variance of the bond angles of the network without making a BSSData object
    """
    return np.var(get_angles(node_coords, adjacencies, dimensions))


def get_bond_lengths(node_coords: np.ndarray, adjacencies: list[list[int]], dimensions: np.ndarray) -> np.ndarray:
    """
    Gets the bond lengths of the network without making a BSSData object
    """
    return np.array([np.linalg.norm(pbc_vector(node_coords[node], node_coords[neighbour], dimensions))
                    for node, neighbours in enumerate(adjacencies)
                    for neighbour in neighbours])


def get_bond_length_variance(node_coords: np.ndarray, adjacencies: list[list[int]], dimensions: np.ndarray) -> float:
    """
    Gets the varience of bond lengths of the network without making a BSSData object
    """
    return np.var(get_bond_lengths(node_coords, adjacencies, dimensions))


def get_assortativity(adjacencies: list[list[int]]) -> np.ndarray:
    """
    Gets a list of all ring sizes(x) and the ring size of their connection(y) in the dual network without creating a BSSData object
    """
    array = []
    for node, neighbours in enumerate(adjacencies):
        for neighbour in neighbours:
            array.append([len(neighbours), len(adjacencies[neighbour])])
    return np.array(array)


def get_pearsons_fast(adjacencies: list[list[int]]) -> float:
    """
    Gets the pearsons correlation coefficient of the ring network without creating a BSSData object
    """
    assortativity_distribution = get_assortativity(adjacencies)
    pearsons_coeff = np.corrcoef(assortativity_distribution[:, 0], assortativity_distribution[:, 1])[0, 1]
    if pearsons_coeff < -1 or pearsons_coeff > 1:
        raise ValueError(f"Out of range pearsons correlation coefficient: {pearsons_coeff}")
    return pearsons_coeff


def get_ring_size_info(adjacencies: list[list[int]], exclude_ids: set[int]) -> tuple[float, float]:
    """
    Gets the variance and p6 value for the ring sizes
    """
    ring_sizes = np.array([len(neighbours) for node, neighbours in enumerate(adjacencies) if node not in exclude_ids])
    return np.var(ring_sizes), np.mean(ring_sizes == 6)


def get_ring_entropy_fast(job_path: Path) -> float:
    """
    Gets the Shannon entropy of the ring sizes in the network without creating a BSSData object
    """
    ring_node_adjacencies = read_adjacencies(job_path.joinpath("output_files", "dual_network_connections.txt"))
    ring_sizes = np.array([len(neighbours) for neighbours in ring_node_adjacencies])

    # Calculate frequencies of each ring size
    unique, counts = np.unique(ring_sizes, return_counts=True)

    # Calculate probabilities
    probabilities = counts / counts.sum()

    # Calculate Shannon entropy
    entropy = -np.sum(probabilities * np.log(probabilities))
    return entropy


def get_disorder_info(job_path: Path, dimensions: np.ndarray, fixed_ring_ids: set[int]) -> tuple[float, float, float, float, float, float]:
    """
    Gets bond length variance, angle variance, ring area variance, ring size variance,
    pearsons correlation coefficient and p6 value of the network without creating a BSSData object
    """
    base_node_coords = pd.read_csv(job_path.joinpath("output_files", "base_network_coords.txt"), sep=r"\s+", header=None).values
    base_node_adjacency = read_adjacencies(job_path.joinpath("output_files", "base_network_connections.txt"))
    dual_node_coords = pd.read_csv(job_path.joinpath("output_files", "dual_network_coords.txt"), sep=r"\s+", header=None).values
    dual_node_connections = read_adjacencies(job_path.joinpath("output_files", "dual_network_connections.txt"))
    bond_length_variance = get_bond_length_variance(base_node_coords, base_node_adjacency, dimensions)
    angle_variance = get_angle_variance(base_node_coords, base_node_adjacency, dimensions)
    ring_area_variance = get_ring_area_variance(dual_node_coords, dual_node_connections, dimensions, set())
    pearsons = get_pearsons_fast(dual_node_connections)
    ring_size_varience, p6 = get_ring_size_info(dual_node_connections, set())
    return bond_length_variance, angle_variance, ring_area_variance, ring_size_varience, pearsons, p6


def get_summary_info_line(stats_path: Path) -> list[str]:
    """
    Gets the last line of the bss_stats.csv file in the output_files directory of the job

    Args:
        job_path: the path to the job directory

    Returns:
        the last line of the bss_stats.csv file as a list of strings
    """
    with stats_path.open() as file:
        last_line = deque(file, maxlen=1)
    return last_line[0].strip().split(",")


def get_summary_info(job_path: Path) -> tuple[int, int, int, int, int, float, float, float, bool]:
    """
    Reads the summary information from the bss_stats.csv file in the output_files directory of the job
    """
    stats_path = job_path.joinpath("output_files", "bss_stats.csv")
    summary_data = get_summary_info_line(stats_path)
    num_attempted = int(summary_data[0])
    num_accepted = int(summary_data[1])
    num_failed_angle_checks = int(summary_data[2])
    num_failed_bond_length_checks = int(summary_data[3])
    num_failed_energy_checks = int(summary_data[4])
    acceptance_rate = float(summary_data[5])
    total_run_time = float(summary_data[6])
    average_time_per_step = float(summary_data[7])
    consistent = summary_data[8].lower() == "true"
    return (num_attempted, num_accepted, num_failed_angle_checks, num_failed_bond_length_checks,
            num_failed_energy_checks, acceptance_rate, total_run_time, average_time_per_step, consistent)


@ dataclass
class ResultEntry:
    path: Path  # Path to the job folder
    changing_vars: dict[str, BSSType]  # Changing var names and their corresponding value, so not Var objects.
    pore_size: int  # Extracted from the job directory name
    pore_distance: float  # Average of the height and width of the boundary
    energy: float  # Final energy of system
    entropy: float  # Final entropy of system
    num_nodes: int  # Number of nodes in system
    num_rings: int  # Number of rings in system
    dimensions: np.ndarray  # Dimensions of the system
    ring_area: float  # Assumes edges do not cross over one another
    ring_area_estimate: float  # Independent of node positions, so can can be used to quantify ring area from pore size discretely
    bond_length_variance: float
    angle_variance: float
    ring_area_variance: float
    ring_size_variance: float
    pearsons: float  # Final Pearsons correlation coefficient of system
    p6: float  # Proportion of rings with 6 nodes
    aboave_weaire: float  # Not yet implemented from the simulation it seems (always 0)
    num_attemped_switches: int
    num_accepted_switches: int
    num_failed_angle_checks: int
    num_failed_bond_length_checks: int
    num_failed_energy_checks: int
    acceptance_rate: float
    total_run_time: float
    average_time_per_step: float
    consistent: bool

    def __post_init__(self) -> None:
        self.pore_concentration = 1 / self.num_rings
        self.area = np.prod(self.dimensions[:, 1] - self.dimensions[:, 0])
        self.batch_name = self.path.parents[2].name
        self.initial_num_rings = int(self.batch_name.split("_")[1])
        self.relative_energy = self.energy / self.num_nodes - RELATIVE_ENERGY

    @ staticmethod
    def from_path(job_path: Path) -> ResultEntry:
        last_data_line = get_last_data_line(job_path)
        num_nodes, dimensions = get_info_data(job_path.joinpath("output_files", "base_network_info.txt"))
        pore_size = int(job_path.parents[2].name.split("_")[3])
        pore_distance = np.average((dimensions[1] - dimensions[0]))
        changing_vars = get_changing_vars_dict(get_changing_vars(job_path))
        fixed_ring_coords, ring_id = get_fixed_ring_coords(job_path)
        ring_area = get_polygon_area(fixed_ring_coords)
        ring_area_estimate = get_polygon_area_estimate(pore_size, SIDE_LENGTH)
        num_rings = get_num_rings(job_path)
        (bond_length_variance, angle_variance, ring_area_variance,
         ring_size_variance, pearsons, p6) = get_disorder_info(job_path, dimensions, {ring_id})
        (num_attempted_switches, num_accepted_switches, num_failed_angle_checks, num_failed_bond_length_checks,
         num_failed_energy_checks, acceptance_rate, total_run_time, average_time_per_step, consistent) = get_summary_info(job_path)

        return ResultEntry(job_path, changing_vars,  # path, changing vars
                           pore_size, pore_distance,  # pore size, pore distance
                           float(last_data_line[2]), float(last_data_line[3]),  # energy, entropy
                           num_nodes, num_rings,  # num nodes, num rings
                           dimensions,  # dimensions
                           ring_area, ring_area_estimate,  # ring area, ring area estimate
                           bond_length_variance, angle_variance,  # bond length variance, angle variance
                           ring_area_variance, ring_size_variance,  # ring area variance, ring size variance
                           pearsons, p6, float(last_data_line[5]),  # pearsons, aboave weaire
                           num_attempted_switches, num_accepted_switches,  # num attempted switches, num accepted switches
                           num_failed_angle_checks, num_failed_bond_length_checks,  # num failed angle checks, num failed bond length checks
                           num_failed_energy_checks, acceptance_rate,  # num failed energy checks, acceptance rate
                           total_run_time, average_time_per_step,  # total run time, average time per step
                           consistent)  # consistent

    @ staticmethod
    def from_string(string: str) -> ResultEntry:
        data = string.split(",")
        changing_vars = get_changing_vars_dict(get_changing_vars(Path(data[0])))
        dimensions = string_to_2d_array(data[7])
        return ResultEntry(Path(data[0]), changing_vars,         # path, changing vars
                           int(data[1]), float(data[2]),         # pore size, pore distance
                           float(data[3]), float(data[4]),       # energy, entropy
                           int(data[5]), int(data[6]),           # num nodes, num rings
                           dimensions,                           # dimensions
                           float(data[8]), float(data[9]),       # ring area, ring area estimate
                           float(data[10]), float(data[11]),     # bond length variance, angle variance
                           float(data[12]), float(data[13]),     # ring area variance, ring size variance
                           float(data[14]), float(data[15]), float(data[16]),  # pearsons, p6, aboave weaire
                           int(data[17]), int(data[18]),          # num attempted switches, num accepted switches
                           int(data[19]), int(data[20]),          # num failed angle checks, num failed bond length checks
                           int(data[21]), float(data[22]),        # num failed energy checks, acceptance rate
                           float(data[23]), float(data[24]),      # total run time, average time per step
                           data[25].lower() == "true")            # consistent

    def plot_ring_sizes(self, smoothing: int = 20) -> None:
        smoothing = 1 if smoothing < 1 else smoothing
        bss_output_data = BSSOutputData(self.path.joinpath("output_files", "bss_stats.csv"))
        all_ring_sizes = sorted(set(ring_size for distribution in bss_output_data.ring_sizes
                                    for ring_size in distribution.keys()))
        data = [[distribution.get(ring_size, 0) for distribution in bss_output_data.ring_sizes] for ring_size in range(1, all_ring_sizes[-1] + 1)]

        # Apply a moving average to the data
        data = [pd.Series(d).rolling(window=smoothing, min_periods=1).mean().tolist() for d in data]
        ring_colours = get_ring_colours_4()
        extended_ring_colours = ring_colours + [ring_colours[-1]] * (all_ring_sizes[-1] - len(ring_colours))

        # Create a new colormap with a color for each unique ring size
        extended_cmap = ListedColormap(extended_ring_colours)
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        format_axes(ax, "Ring Size", "Proportion", 0, max(bss_output_data.steps), 0, 1)
        ax.stackplot(bss_output_data.steps, *data, colors=extended_cmap.colors, edgecolor="none", antialiased=False)

        # Create a colorbar
        add_colourbar_2(plt.subplot(gs[1]), ListedColormap(ring_colours[2:]), "\nRing Sizes", 3, len(ring_colours))
        print(f"Last distribution: {bss_output_data.ring_sizes[-1]}")

    def get_stats_data_fast(self, indexes: list[int]) -> tuple[pd.Series, ...]:
        df = pd.read_csv(self.path.joinpath("output_files", "bss_stats.csv"), skiprows=3, skipfooter=4, usecols=indexes, engine="python")
        return tuple(df.iloc[:, i] for i in range(df.shape[1]))

    def get_entropy_data_fast(self, smoothing: int = 20) -> tuple[pd.Series, pd.Series]:
        smoothing = 1 if smoothing < 1 else smoothing
        steps, entropies = self.get_stats_data_fast([0, 3])  # steps and entropy are columns 0 and 3 respectively
        entropies = entropies.rolling(window=smoothing, min_periods=1).mean()
        return steps, entropies

    def plot_entropy(self, smoothing: int = 20) -> None:
        steps, entropies = self.get_entropy_data_fast(smoothing)
        ax = plt.gca()
        ax.plot(steps, entropies)
        format_axes(ax, "Step", "Ring Size Shannon Entropy", 0, max(steps), 0, None)
        remove_axes(ax)
        arrowed_spines(ax)

    def get_pearsons_data_fast(self, smoothing: int = 20) -> tuple[pd.Series, pd.Series]:
        smoothing = 1 if smoothing < 1 else smoothing
        steps, entropies = self.get_stats_data_fast([0, 4])  # steps and pearsons are columns 0 and 4 respectively
        entropies = entropies.rolling(window=smoothing, min_periods=1).mean()
        return steps, entropies

    def plot_pearsons(self, smoothing: int = 20) -> None:
        steps, pearsons = self.get_pearsons_data_fast(smoothing)
        ax = plt.gca()
        ax.plot(steps, pearsons)
        format_axes(ax, "Step", "Pearson's Correlation Coefficient", 0, max(steps), -1, 1)
        remove_axes(ax)
        arrowed_spines(ax)

    def plot_bond_length_distribution(self, num_bins: Optional[int] = None) -> None:
        """
        Plots the distribution of bond lengths in the system
        """
        num_bins = "auto" if num_bins is None else num_bins
        base_node_coords = pd.read_csv(self.path.joinpath("output_files", "base_network_coords.txt"), sep=r"\s+", header=None).values
        base_node_adjacency = read_adjacencies(self.path.joinpath("output_files", "base_network_connections.txt"))
        bond_lengths = get_bond_lengths(base_node_coords, base_node_adjacency, self.dimensions)
        ax = plt.gca()
        ax.hist(bond_lengths, bins=num_bins, density=True)
        format_axes(ax, r"Bond Length ($\mathdefault{a_0}$)", "Probability Density", 0, None, 0, None)
        remove_axes(ax)
        arrowed_spines(ax)

    def plot_angle_distribution(self, num_bins: Optional[int] = None) -> float:
        """
        Plots the distribution of bond angles in the system and returns the Shannon entropy
        """
        num_bins = "auto" if num_bins is None else num_bins
        base_node_coords = pd.read_csv(self.path.joinpath("output_files", "base_network_coords.txt"), sep=r"\s+", header=None).values
        base_node_adjacency = read_adjacencies(self.path.joinpath("output_files", "base_network_connections.txt"))
        bond_angles = get_angles(base_node_coords, base_node_adjacency, self.dimensions)
        print(np.var(bond_angles))
        ax = plt.gca()
        counts, bin_edges = np.histogram(bond_angles, bins=num_bins, range=(0, 360), density=True)
        ax.hist(bond_angles, bins=num_bins, range=(0, 360), density=True)
        format_axes(ax, "Angle (degrees)", "Probability Density", 0, 360, 0, None)
        remove_axes(ax)

        # Calculate the Shannon entropy
        pk = counts / np.sum(counts)  # normalize the counts to get probabilities
        pk = pk[pk > 0]  # remove zero probabilities to avoid log(0)
        entropy = -np.sum(pk * np.log(pk))

        return entropy

    def get_energy_data_fast(self, smoothing: int = 20) -> tuple[pd.Series, pd.Series]:
        smoothing = 1 if smoothing < 1 else smoothing
        steps, energies = self.get_stats_data_fast([0, 2])

        # Apply a moving average to the data
        energies = energies.rolling(window=smoothing, min_periods=1).mean()
        return steps, energies

    def get_temperature_data_fast(self, smoothing: int = 20) -> tuple[pd.Series, pd.Series]:
        smoothing = 1 if smoothing < 1 else smoothing
        steps, temperatures = self.get_stats_data_fast([0, 1])

        # Apply a moving average to the data
        temperatures = temperatures.rolling(window=smoothing, min_periods=1).mean()
        return steps, temperatures

    def plot_energy(self, smoothing: int = 20) -> None:
        steps, energies = self.get_energy_data_fast(smoothing)
        ax = plt.gca()
        ax.plot(steps, energies)
        format_axes(ax, "Step", r"Energy ($\mathdefault{E_h}$)", 0, max(steps), 0, None)
        remove_axes(ax)
        arrowed_spines(ax)

    def plot_relative_energy(self, smoothing: int = 20) -> None:
        steps, energies = self.get_energy_data_fast(smoothing)
        ax = plt.gca()
        ax.plot(steps, energies / self.num_nodes - RELATIVE_ENERGY)
        format_axes(ax, "Step", r"Relative Energy ($\mathdefault{E_h Node^{-1}}$)", 0, max(steps), 0, None)
        remove_axes(ax)
        arrowed_spines(ax)

    def get_ring_size_variance_data_fast(self, smoothing: int = 20) -> tuple[pd.Series, ...]:
        smoothing = 1 if smoothing < 1 else smoothing
        steps, ring_distributions = self.get_stats_data_fast([0, 6])
        ring_distributions = convert_dictionary_column(ring_distributions)

        # Calculate variance for each distribution
        variances = ring_distributions.apply(lambda d: sum((x - np.average(list(d.keys()), weights=list(d.values())))**2 * p for x, p in d.items()))

        variances = variances.rolling(window=smoothing, min_periods=1).mean()
        return steps, variances

    def plot_ring_size_variance(self, smoothing: int = 20) -> None:
        steps, variances = self.get_ring_size_variance_data_fast(smoothing)
        ax = plt.gca()
        ax.plot(steps, variances)
        format_axes(ax, "Step", "Ring Size Variance", 0, max(steps), 0, None)
        remove_axes(ax)
        arrowed_spines(ax)

    def plot_ring_size_entropy_and_variance(self, smoothing: int = 20) -> None:
        steps, entropies = self.get_entropy_data_fast(smoothing)
        _, variances = self.get_ring_size_variance_data_fast(smoothing)
        ax = plt.gca()
        ax.plot(steps, entropies, label="Entropy")
        ax.plot(steps, variances, label="Variance")
        format_axes(ax, "Step", "Ring Size Shannon Entropy and Variance", 0, max(steps), 0, None)
        remove_axes(ax)
        arrowed_spines(ax)
        ax.legend()

    def plot_all_per_step(self, smoothing: int = 20) -> None:
        steps, energies = self.get_energy_data_fast(smoothing)
        relative_energies = energies / self.num_nodes - RELATIVE_ENERGY
        _, temperatures = self.get_temperature_data_fast(smoothing)
        _, entropies = self.get_entropy_data_fast(smoothing)
        _, variances = self.get_ring_size_variance_data_fast(smoothing)
        ax = plt.gca()
        ax.plot(steps, relative_energies, label="Relative Energy ($\mathdefault{E_h Node^{-1}}$)")
        ax.plot(steps, entropies, label="Ring Size Entropy")
        ax.plot(steps, variances, label="Ring Size Variance")
        ax.plot(steps, temperatures, label="Temperature", color="red")
        format_axes(ax, "Step", "", 0, max(steps), 0, None)
        remove_axes(ax)
        arrowed_spines(ax)
        ax.legend(fontsize="x-large")

    def get_bss_data(self, enable_fixed_rings: bool = True) -> BSSData:
        if enable_fixed_rings:
            return BSSData.from_files(self.path.joinpath("output_files"), self.path.parents[1].joinpath("initial_network", "fixed_rings.txt"))
        return BSSData.from_files(self.path.joinpath("output_files"))

    def draw_network(self, enable_fixed_rings: bool = True) -> None:
        """
        Creates a BSSData object, attempts to recenter the fixed rings and then draws the network with the pretty figures method
        """
        bss_data = self.get_bss_data(enable_fixed_rings)
        bss_data._attempt_fixed_ring_recenter()
        bss_data.draw_graph_pretty_figures()

    def short_repr(self) -> str:
        return f"rings: {self.initial_num_rings}, pore size: {self.pore_size}, changing vars: {self.changing_vars}"

    def __repr__(self) -> str:
        return (f"{self.path},"
                f"{self.pore_size},{self.pore_distance},"
                f"{self.energy},{self.entropy},"
                f"{self.num_nodes},{self.num_rings},"
                f"{array_2d_to_string(self.dimensions)},"
                f"{self.ring_area},{self.ring_area_estimate},"
                f"{self.bond_length_variance},{self.angle_variance},"
                f"{self.ring_area_variance},{self.ring_size_variance},"
                f"{self.pearsons},{self.p6},{self.aboave_weaire}")

    def __str__(self) -> str:
        return ("ResultEntry object:\n"
                f"Path: {self.path}\n"
                f"Changing vars: {self.changing_vars}\n"
                f"Pore size: {self.pore_size}\t"
                f"Pore distance: {self.pore_distance}\n"
                f"Energy: {self.energy}\t"
                f"Entropy: {self.entropy}\n"
                f"Number of nodes: {self.num_nodes}\t"
                f"Number of rings: {self.num_rings}\n"
                f"Dimensions: {self.dimensions}\n"
                f"Ring area: {self.ring_area}\t"
                f"Ring area estimate: {self.ring_area_estimate}\n"
                f"Bond length variance: {self.bond_length_variance}\t"
                f"Angle variance: {self.angle_variance}\n"
                f"Ring area variance: {self.ring_area_variance}\t"
                f"Ring size variance: {self.ring_size_variance}\n"
                f"Pearsons: {self.pearsons}\t"
                f"Above Weaire: {self.aboave_weaire}\n")
