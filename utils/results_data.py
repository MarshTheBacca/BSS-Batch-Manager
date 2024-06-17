from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Generator, Optional

import matplotlib.cm as cm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import gridspec
from matplotlib import pyplot as plt
from matplotlib.colors import Normalize

from .custom_types import RELATIVE_ENERGY, RELATIVE_ENTROPY, RELATIVE_PEARSONS
from .other_utils import progress_tracker
from .plotting_utils import (add_colourbar, arrowed_spines, format_axes,
                             remove_axes)
from .result_entry import ResultEntry

plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Latin Modern Roman"]


def calculate_average(data):
    return {thermal_temp: {anneal_temp: {pore_size: np.mean(energies)
                                         for pore_size, energies in pore_sizes.items()}
                           for anneal_temp, pore_sizes in anneal_temps.items()}
            for thermal_temp, anneal_temps in data.items()}


def sort_data(avg_data):
    return {(thermal_temp, anneal_temp): sorted([(pore_size, avg_data[thermal_temp][anneal_temp][pore_size])
                                                 for pore_size in avg_data[thermal_temp][anneal_temp].keys()], key=lambda x: x[0])
            for thermal_temp, anneal_temps in avg_data.items()
            for anneal_temp in anneal_temps.keys()}


def plot_data(temps, thermal_temps, anneal_temps, cmap):
    for (thermal_temp, anneal_temp), avg_energies in temps.items():
        pore_sizes, avg_energies = zip(*avg_energies)
        color = cmap((thermal_temps.index(thermal_temp) + anneal_temps.index(anneal_temp) / len(anneal_temps)) / len(thermal_temps))
        plt.plot(pore_sizes, avg_energies, color=color)
    return pore_sizes


def get_relative_energy(entry: ResultEntry) -> float:
    return entry.energy / entry.num_nodes - RELATIVE_ENERGY


def get_angle_variance(entry: ResultEntry) -> float:
    return entry.angle_variance


def get_relative_entropy(entry: ResultEntry) -> float:
    return entry.entropy - RELATIVE_ENTROPY


def get_relative_pearsons(entry: ResultEntry) -> float:
    return entry.pearsons - RELATIVE_PEARSONS


def get_lemaitre(entry: ResultEntry) -> tuple[float, float]:
    return entry.p6, entry.ring_size_variance


def get_bond_length_variance(entry: ResultEntry) -> float:
    return entry.bond_length_variance


def get_angle_variance(entry: ResultEntry) -> float:
    return entry.angle_variance


def import_maximum_entropy_solution(path: Path) -> tuple[np.ndarray, np.ndarray]:
    p_6s = []
    variances = []
    with path.open("r") as max_entropy_file:
        node_degrees = np.array([int(float(x)) for x in max_entropy_file.readline().strip().split()[:-1]])
        degree_6_index = np.where(node_degrees == 6)[0][0]
        for line in max_entropy_file.readlines():
            data = line.strip().split()
            p_6s.append(float(data[degree_6_index]))
            variances.append(float(data[-1]))
    return np.array(p_6s), np.array(variances)


@dataclass
class ResultsData:
    path: Path
    entries: list[ResultEntry] = field(default_factory=list)

    @staticmethod
    def from_file(path: Path) -> ResultsData:
        with path.open("r") as results_file:
            return ResultsData(path, [ResultEntry.from_string(line.strip()) for line in results_file.readlines()])

    @staticmethod
    def gen_from_paths(job_paths: list[Path], save_path: Path) -> ResultsData:
        total = len(job_paths)
        entries = []
        errored_path = save_path.parent.joinpath("errored_jobs.txt")
        for job_path in progress_tracker(job_paths, total):
            try:
                entries.append(ResultEntry.from_path(job_path))
            except Exception as e:
                print(f"Failed to process {job_path}: {e}")
                with errored_path.open("a") as errored_file:
                    errored_file.write(f"{job_path}\t{e}\n")
        return_data = ResultsData(save_path, entries)
        return_data.export()
        return return_data

    def export(self, path: Optional[Path] = None) -> None:
        output_path = self.path if path is None else path
        with output_path.open("w") as output_file:
            for entry in self.entries:
                output_file.write(f"{repr(entry)}\n")

    def data_by_therm_anneal_pore(self, function: Callable[[ResultEntry], Any]) -> dict:
        data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for entry in self.entries:
            thermal_temp = entry.changing_vars.get("Thermalising temperature")
            anneal_temp = entry.changing_vars.get("Annealing end temperature")
            if thermal_temp is not None and anneal_temp is not None:
                data[thermal_temp][anneal_temp][entry.pore_size].append(function(entry))
        return data

    def data_by_therm_anneal(self, function: Callable[[ResultEntry], Any]) -> dict:
        data = defaultdict(lambda: defaultdict(list))
        for entry in self.entries:
            thermal_temp = entry.changing_vars.get("Thermalising temperature")
            anneal_temp = entry.changing_vars.get("Annealing end temperature")
            if thermal_temp is not None and anneal_temp is not None:
                data[thermal_temp][anneal_temp].append(function(entry))
        return data

    def data_by_therm_pore(self, function: Callable[[ResultEntry], Any]) -> dict:
        data = defaultdict(lambda: defaultdict(list))
        for entry in self.entries:
            thermal_temp = entry.changing_vars.get("Thermalising temperature")
            if thermal_temp is not None:
                data[thermal_temp][entry.pore_size].append(function(entry))
        return data

    def data_by_therm_pore_fraction(self, function: Callable[[ResultEntry], Any]) -> dict:
        data = defaultdict(lambda: defaultdict(list))
        for entry in self.entries:
            thermal_temp = entry.changing_vars.get("Thermalising temperature")
            if thermal_temp is not None:
                data[thermal_temp][entry.pore_concentration].append(function(entry))
        return data

    def data_by_therm_p6(self, function: Callable[[ResultEntry], Any]) -> dict:
        data = defaultdict(lambda: defaultdict(list))
        for entry in self.entries:
            thermal_temp = entry.changing_vars.get("Thermalising temperature")
            if thermal_temp is not None:
                data[thermal_temp][entry.p6].append(function(entry))
        return data

    def plot_lemaitre(self) -> None:
        data = np.array([[entry.changing_vars.get("Thermalising temperature"), entry.p6, entry.ring_size_variance] for entry in self.entries])
        cmap = cm.get_cmap("Wistia")
        norm = Normalize(vmin=np.min(data[:, 0]), vmax=np.max(data[:, 0]))
        colors = cmap(norm(data[:, 0]))
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        ax.scatter(data[:, 1], data[:, 2], color=colors)
        maximum_entropy_solution = import_maximum_entropy_solution(Path(__file__).parents[1].joinpath("lemaitre.txt"))
        ax.plot(*maximum_entropy_solution, label="Maximum Entropy Solution", color="black", linewidth=2)
        remove_axes(ax)
        format_axes(ax, r"$\mathdefault{p_6}$", "Ring Size Variance", 0, 1, 0, None)
        arrowed_spines(ax)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, np.unique(data[:, 0]), " \n" + r"$\mathdefault{log_{10}(T_{thermal})}$")

    def plot_lemaitre_by_pore_size(self) -> None:
        data = np.array([[entry.pore_size, entry.p6, entry.ring_size_variance] for entry in self.entries])
        data = data[np.argsort(data[:, 0])]
        cmap = cm.get_cmap("cool")
        norm = Normalize(vmin=np.min(data[:, 0]), vmax=np.max(data[:, 0]))
        colors = cmap(norm(data[:, 0]))
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        ax.scatter(data[:, 1], data[:, 2], color=colors)
        maximum_entropy_solution = import_maximum_entropy_solution(Path(__file__).parents[1].joinpath("lemaitre.txt"))
        ax.plot(*maximum_entropy_solution, label="Maximum Entropy Solution", color="black", linewidth=2)
        remove_axes(ax)
        format_axes(ax, r"$\mathdefault{p_6}$", "Ring Size Variance", 0, 1, 0, None)
        arrowed_spines(ax)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, np.unique(data[:, 0]), " \n" + "Pore size")

    def plot_lemaitre_avg(self) -> None:
        # Group data by temperature
        grouped_data = {}
        for entry in self.entries:
            temp = entry.changing_vars.get("Thermalising temperature")
            if temp not in grouped_data:
                grouped_data[temp] = {'p6': [], 'variance': []}
            grouped_data[temp]['p6'].append(entry.p6)
            grouped_data[temp]['variance'].append(entry.ring_size_variance)
        # Calculate averages
        avg_data = np.array([[temp, np.mean(group['p6']), np.mean(group['variance'])] for temp, group in grouped_data.items()])
        # Create color map
        cmap = cm.get_cmap("Wistia")
        norm = Normalize(vmin=np.min(avg_data[:, 0]), vmax=np.max(avg_data[:, 0]))
        colors = cmap(norm(avg_data[:, 0]))
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        ax.scatter(avg_data[:, 1], avg_data[:, 2], color=colors)
        maximum_entropy_solution = import_maximum_entropy_solution(Path(__file__).parents[1].joinpath("lemaitre.txt"))
        ax.plot(*maximum_entropy_solution, label="Maximum Entropy Solution", color="black", linewidth=2)
        remove_axes(ax)
        format_axes(ax, r"$\mathdefault{p_6}$", "Ring Size Variance", 0, 1, 0, None)
        arrowed_spines(ax)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, np.unique(avg_data[:, 0]), " \n" + r"$\mathdefault{log_{10}(T_{thermal})}$")

    def plot_energy_vs_pore_size(self) -> None:
        data = self.data_by_therm_anneal_pore(get_relative_energy)
        avg_data = calculate_average(data)
        temps = sort_data(avg_data)
        thermal_temps = sorted(set(thermal_temp for thermal_temp, _ in temps.keys()))
        anneal_temps = sorted(set(anneal_temp for _, anneal_temp in temps.keys()))
        cmap = cm.get_cmap("cool")
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        remove_axes(ax)
        pore_sizes = plot_data(temps, thermal_temps, anneal_temps, cmap)
        format_axes(ax, "Pore Size", r"Average Relative Energy ($\mathdefault{E_h Node^{-1}}$)",
                    min(pore_sizes), max(pore_sizes), 0, None, 5, None)
        arrowed_spines(ax)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, thermal_temps, " \n" + r"$\mathdefault{log_{10}(T_{thermal})}$")

    def plot_energy_vs_pore_size_2(self) -> None:
        # Dont consider annealing temperature
        data = self.data_by_therm_pore(get_relative_energy)
        data = {temperature: {pore: (np.mean(energies), np.std(energies)) for pore, energies in pore_sizes.items()}
                for temperature, pore_sizes in data.items()}
        cmap = cm.get_cmap("cool")
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        remove_axes(ax)
        min_temp = min(data.keys())
        temp_range = max(data.keys()) - min_temp
        for temperature, pore_sizes in sorted(data.items()):
            sorted_pore_sizes = dict(sorted(pore_sizes.items()))
            color = cmap((temperature - min_temp) / temp_range)
            ax.plot(list(sorted_pore_sizes.keys()), [mean for mean, std in sorted_pore_sizes.values()], color=color)
        format_axes(ax, "Pore Size", r"Average Relative Energy ($\mathdefault{E_h Node^{-1}}$)", list(sorted_pore_sizes.keys()))
        arrowed_spines(ax)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, list(data.keys()), " \n" + r"$\mathdefault{log_{10}(T_{thermal})}$")

    def plot_entropy_vs_pore_size(self) -> None:
        data = self.data_by_therm_pore(get_relative_entropy)
        data = {temperature: {pore: (np.mean(energies), np.std(energies)) for pore, energies in pore_sizes.items()}
                for temperature, pore_sizes in data.items()}
        cmap = cm.get_cmap("Wistia")
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        remove_axes(ax)
        min_temp = min(data.keys())
        temp_range = max(data.keys()) - min_temp
        for temperature, pore_sizes in sorted(data.items()):
            sorted_pore_sizes = dict(sorted(pore_sizes.items()))
            color = cmap((temperature - min_temp) / temp_range)
            x = list(sorted_pore_sizes.keys())
            y = [mean for mean, std in sorted_pore_sizes.values()]
            yerr = [std for mean, std in sorted_pore_sizes.values()]
            ax.plot(x, y, color=color)
            ax.fill_between(x, [yi - err for yi, err in zip(y, yerr)], [yi + err for yi, err in zip(y, yerr)], color=color, alpha=0.3)
        format_axes(ax, "Pore Size", r"Average Ring Size Entropy")
        arrowed_spines(ax)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, list(data.keys()), " \n" + r"$\mathdefault{log_{10}(T_{thermal})}$")

    def plot_energy_vs_pore_size_error_bars(self) -> None:
        data = self.data_by_therm_pore(get_relative_energy)
        data = {temperature: {pore: (np.mean(energies), np.std(energies)) for pore, energies in pore_sizes.items()}
                for temperature, pore_sizes in data.items()}
        cmap = cm.get_cmap("Wistia")

        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        remove_axes(ax)
        min_temp = min(data.keys())
        temp_range = max(data.keys()) - min_temp
        for temperature, pore_sizes in sorted(data.items()):
            sorted_pore_sizes = dict(sorted(pore_sizes.items()))
            color = cmap((temperature - min_temp) / temp_range)
            ax.plot(list(sorted_pore_sizes.keys()), [mean for mean, std in sorted_pore_sizes.values()], color=color)
            ax.errorbar(list(sorted_pore_sizes.keys()), [mean for mean, std in sorted_pore_sizes.values()],
                        yerr=[std for mean, std in sorted_pore_sizes.values()], color=color, fmt='o')
        format_axes(ax, "Pore Size", r"Average Relative Energy ($\mathdefault{E_h Node^{-1}}$)", list(sorted_pore_sizes.keys()))
        arrowed_spines(ax)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, list(data.keys()), " \n" + r"$\mathdefault{log_{10}(T_{thermal})}$")

    def plot_energy_vs_pore_size_fill_between(self) -> None:
        data = self.data_by_therm_pore(get_relative_energy)
        data = {temperature: {pore: (np.mean(energies), np.std(energies)) for pore, energies in pore_sizes.items()}
                for temperature, pore_sizes in data.items()}
        max_pore_size = max(pore for pore_sizes in data.values() for pore in pore_sizes.keys())
        cmap = cm.get_cmap("Wistia")
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        remove_axes(ax)
        min_temp = min(data.keys())
        temp_range = max(data.keys()) - min_temp
        for temperature, pore_sizes in sorted(data.items()):
            sorted_pore_sizes = dict(sorted(pore_sizes.items()))
            color = cmap((temperature - min_temp) / temp_range)
            x = list(sorted_pore_sizes.keys())
            y = [mean for mean, std in sorted_pore_sizes.values()]
            yerr = [std for mean, std in sorted_pore_sizes.values()]
            ax.plot(x, y, color=color)
            ax.fill_between(x, [yi - err for yi, err in zip(y, yerr)], [yi + err for yi, err in zip(y, yerr)], color=color, alpha=0.3)
        format_axes(ax, "Pore Size", r"Average Relative Energy ($\mathdefault{E_h Node^{-1}}$)", 8, max_pore_size, 0, None)
        arrowed_spines(ax)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, list(data.keys()), " \n" + r"$\mathdefault{log_{10}(T_{thermal})}$")

    def plot_energy_vs_pore_size_fill_between_2(self) -> None:
        # Only plot the minimum and maximum thermalising temperatures
        data = self.data_by_therm_pore(get_relative_energy)
        data = {temperature: {pore: (np.mean(energies), np.std(energies)) for pore, energies in pore_sizes.items()}
                for temperature, pore_sizes in data.items()}
        cmap = cm.get_cmap("Wistia")
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        remove_axes(ax)
        min_temp = min(data.keys())
        max_temp = max(data.keys())
        temp_range = max_temp - min_temp
        for temperature in [min_temp, max_temp]:
            pore_sizes = data[temperature]
            sorted_pore_sizes = dict(sorted(pore_sizes.items()))
            color = cmap((temperature - min_temp) / temp_range)
            x = list(sorted_pore_sizes.keys())
            y = [mean for mean, std in sorted_pore_sizes.values()]
            yerr = [std for mean, std in sorted_pore_sizes.values()]
            ax.plot(x, y, color=color)
            ax.fill_between(x, [yi - err for yi, err in zip(y, yerr)], [yi + err for yi, err in zip(y, yerr)], color=color, alpha=0.3)
        format_axes(ax, "Pore Size", r"Average Relative Energy ($\mathdefault{E_h Node^{-1}}$)", list(sorted_pore_sizes.keys()))
        arrowed_spines(ax)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, [min_temp, max_temp], " \n" + r"$\mathdefault{log_{10}(T_{thermal})}$")

    def plot_pearsons_vs_pore_size(self) -> None:
        data = self.data_by_therm_pore(get_relative_pearsons)
        data = {temperature: {pore: (np.mean(energies), np.std(energies)) for pore, energies in pore_sizes.items()}
                for temperature, pore_sizes in data.items()}
        cmap = cm.get_cmap("Wistia")
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        remove_axes(ax)
        min_temp = min(data.keys())
        temp_range = max(data.keys()) - min_temp
        for temperature, pore_sizes in sorted(data.items()):
            sorted_pore_sizes = dict(sorted(pore_sizes.items()))
            color = cmap((temperature - min_temp) / temp_range)
            x = list(sorted_pore_sizes.keys())
            y = [mean for mean, std in sorted_pore_sizes.values()]
            yerr = [std for mean, std in sorted_pore_sizes.values()]
            ax.plot(x, y, color=color)
            ax.fill_between(x, [yi - err for yi, err in zip(y, yerr)], [yi + err for yi, err in zip(y, yerr)], color=color, alpha=0.3)
        format_axes(ax, "Pore Size", r"Average Pearson's Correlation Coefficient", 8, None, -0.35, -0.1)
        arrowed_spines(ax)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, list(data.keys()), " \n" + r"$\mathdefault{log_{10}(T_{thermal})}$")

    def plot_energy_vs_distance(self) -> None:
        data = [(entry.pore_distance, entry.energy / entry.num_nodes - RELATIVE_ENERGY,
                 entry.changing_vars.get("Thermalising temperature"),
                 entry.changing_vars.get("Annealing end temperature")) for entry in self.entries]

        # Extract pore distances, energies, and thermalising temperatures
        pore_distances, energies, thermal_temps, _ = zip(*data)

        # Calculate mean and standard deviation for each unique pore_distance
        unique_distances = np.unique(pore_distances)
        means = [np.mean([energies[i] for i in range(len(energies)) if pore_distances[i] == dist]) for dist in unique_distances]
        std_devs = [np.std([energies[i] for i in range(len(energies)) if pore_distances[i] == dist]) for dist in unique_distances]

        cmap = cm.get_cmap("cool")
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        remove_axes(ax)
        # Plot data
        ax.scatter(pore_distances, energies, c=thermal_temps, cmap=cmap)
        # Plot variance with fill_between
        ax.fill_between(unique_distances, [mean - std_dev for mean, std_dev in zip(means, std_devs)], [mean + std_dev for mean, std_dev in zip(means, std_devs)], alpha=0.2)
        format_axes(ax, r"Distance Between Pores ($\mathdefault{a_0}$)", r"Average Relative Energy ($\mathdefault{E_h Node^{-1}}$)")
        arrowed_spines(ax)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, thermal_temps, " \n" + r"$\mathdefault{log_{10}(T_{thermal})}$")

    def plot_energy_vs_distance_2(self) -> None:
        data = defaultdict(lambda: defaultdict(list))
        for entry in self.entries:
            data[entry.pore_size][entry.pore_distance].append(entry.energy / entry.num_nodes - RELATIVE_ENERGY)

        # Calculate mean and standard deviation for each unique pore_distance for each pore_size
        average_data = {pore_size: {distance: (np.mean(energies), np.std(energies)) for distance, energies in distances.items()}
                        for pore_size, distances in data.items()}

        # sort data by distance
        average_data = {pore_size: {distance: energy for distance, energy in sorted(distances.items(), key=lambda x: x[0])}
                        for pore_size, distances in average_data.items()}

        # Get a list of unique pore sizes
        pore_sizes = sorted(set(average_data.keys()))
        max_pore_size = max(pore_sizes)
        min_pore_size = min(pore_sizes)

        # Create a colormap
        cmap = cm.get_cmap("cool")

        # Normalize the pore sizes to the range [0, 1] to map to the colormap
        norm = Normalize(vmin=min_pore_size, vmax=max_pore_size)

        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        remove_axes(ax)

        for pore_size, distances in average_data.items():
            distances_keys, distances_values = zip(*distances.items())
            means, std_devs = zip(*distances_values)
            ax.plot(distances_keys, means, label=f"Pore Size {pore_size}", color=cmap(norm(pore_size)))
            ax.fill_between(distances_keys, [mean - std_dev for mean, std_dev in zip(means, std_devs)], [mean + std_dev for mean, std_dev in zip(means, std_devs)], alpha=0.2, color=cmap(norm(pore_size)))

        format_axes(ax, r"Distance Between Pores ($\mathdefault{a_0}$)", r"Average Relative Energy ($\mathdefault{E_h Node^{-1}}$)")
        arrowed_spines(ax)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, pore_sizes, "Pore Size")

    def plot_energy_vs_concentration(self) -> None:
        data = defaultdict(lambda: defaultdict(list))
        for entry in self.entries:
            data[entry.pore_size][entry.pore_concentration].append(entry.energy / entry.num_nodes - RELATIVE_ENERGY)
        average_data = {pore_size: {concentration: np.mean(energies) for concentration, energies in concentrations.items()}
                        for pore_size, concentrations in data.items()}
        # sort data by concentration
        average_data = {pore_size: {concentration: energy for concentration, energy in sorted(concentrations.items(), key=lambda x: x[0])}
                        for pore_size, concentrations in average_data.items()}
        # Get a list of unique pore sizes
        pore_sizes = sorted(set(average_data.keys()))
        cmap = cm.get_cmap("cool")
        norm = Normalize(vmin=min(pore_sizes), vmax=max(pore_sizes))
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        remove_axes(ax)
        for pore_size, concentrations in average_data.items():
            ax.plot(concentrations.keys(), concentrations.values(), label=f"Pore Size {pore_size}", color=cmap(norm(pore_size)))
        format_axes(ax, "Pore Fraction", r"Average Relative Energy ($\mathdefault{E_h Node^{-1}}$)")
        arrowed_spines(ax)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, pore_sizes, "Pore Size")

    def plot_energy_vs_concentration_2(self) -> None:
        data = defaultdict(lambda: defaultdict(list))
        for entry in self.entries:
            data[entry.pore_size][entry.pore_concentration].append((entry.energy / entry.num_nodes - RELATIVE_ENERGY) / entry.pore_size)
        average_data = {pore_size: {concentration: np.mean(energies) for concentration, energies in concentrations.items()}
                        for pore_size, concentrations in data.items()}
        # sort data by concentration
        average_data = {pore_size: {concentration: energy for concentration, energy in sorted(concentrations.items(), key=lambda x: x[0])}
                        for pore_size, concentrations in average_data.items()}
        # Get a list of unique pore sizes
        pore_sizes = sorted(set(average_data.keys()))
        cmap = cm.get_cmap("cool")
        norm = Normalize(vmin=min(pore_sizes), vmax=max(pore_sizes))
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        remove_axes(ax)
        for pore_size, concentrations in average_data.items():
            ax.plot(concentrations.keys(), concentrations.values(), label=f"Pore Size {pore_size}", color=cmap(norm(pore_size)))
        format_axes(ax, "Pore Fraction", r"Average Relative Energy / Pore Size ($\mathdefault{E_h Node^{-1}}$)")
        arrowed_spines(ax)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, pore_sizes, "Pore Size")

    def plot_energy_vs_concentration_3(self) -> None:
        data = defaultdict(lambda: defaultdict(list))
        for entry in self.entries:
            data[entry.pore_size][entry.pore_concentration].append((entry.energy / entry.num_nodes - RELATIVE_ENERGY) / entry.ring_area_estimate)

        # Calculate mean and standard deviation for each unique pore_concentration for each pore_size
        average_data = {pore_size: {concentration: (np.mean(energies), np.std(energies)) for concentration, energies in concentrations.items()}
                        for pore_size, concentrations in data.items()}

        # sort data by concentration
        average_data = {pore_size: {concentration: energy for concentration, energy in sorted(concentrations.items(), key=lambda x: x[0])}
                        for pore_size, concentrations in average_data.items()}

        # Get a list of unique pore sizes
        pore_sizes = sorted(set(average_data.keys()))

        cmap = cm.get_cmap("cool")
        norm = Normalize(vmin=min(pore_sizes), vmax=max(pore_sizes))

        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        remove_axes(ax)

        for pore_size, concentrations in average_data.items():
            concentrations_keys, concentrations_values = zip(*concentrations.items())
            means, std_devs = zip(*concentrations_values)
            ax.plot(concentrations_keys, means, label=f"Pore Size {pore_size}", color=cmap(norm(pore_size)))

            # Plot variance with fill_between
            ax.fill_between(concentrations_keys, [mean - std_dev for mean, std_dev in zip(means, std_devs)], [mean + std_dev for mean, std_dev in zip(means, std_devs)], alpha=0.2, color=cmap(norm(pore_size)))

        format_axes(ax, "Pore Fraction", r"Avg Relative Energy / Pore Area Estimate ($\mathdefault{E_h Node^{-1} a_0^{-2}}$)")
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, pore_sizes, "Pore Size")

    def plot_energy_vs_concentration_4(self) -> None:
        data = defaultdict(lambda: defaultdict(list))
        for entry in self.entries:
            data[entry.pore_size][entry.pore_concentration].append((entry.energy / entry.num_nodes - RELATIVE_ENERGY) / entry.ring_area)
        average_data = {pore_size: {concentration: np.mean(energies) for concentration, energies in concentrations.items()}
                        for pore_size, concentrations in data.items()}
        # sort data by concentration
        average_data = {pore_size: {concentration: energy for concentration, energy in sorted(concentrations.items(), key=lambda x: x[0])}
                        for pore_size, concentrations in average_data.items()}
        # Get a list of unique pore sizes
        pore_sizes = sorted(set(average_data.keys()))
        cmap = cm.get_cmap("cool")
        norm = Normalize(vmin=min(pore_sizes), vmax=max(pore_sizes))
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        remove_axes(ax)
        for pore_size, concentrations in average_data.items():
            ax.plot(concentrations.keys(), concentrations.values(), label=f"Pore Size {pore_size}", color=cmap(norm(pore_size)))

        format_axes(ax, "Pore Fraction", r"Average Relative Energy / Pore Area ($\mathdefault{E_h Node^{-1} a_0^{-2}}$)")
        arrowed_spines(ax)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, pore_sizes, "Pore Size")

    def plot_entropy_vs_step(self) -> None:
        data = defaultdict(list)
        steps = self.entries[0].get_entropy_data()[0]
        for entry in self.entries:
            data[entry.changing_vars.get("Annealing steps")].append(entry.get_entropy_data()[1])
        average_data = {annealing_temp: np.mean(energies) for annealing_temp, energies in data.items()}
        cmap = cm.get_cmap("cool")
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        remove_axes(ax)
        ax.plot(steps, average_data.values(), color=cmap(0))
        format_axes(ax, "Annealing Steps", r"Average Relative Entropy (a.u)", steps)
        arrowed_spines(ax)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, [0], "Annealing Temperature")

    def gen_bond_angles(self) -> Generator[float, None, None]:
        for result_entry in self.entries:
            for bond_angle in result_entry.get_bond_angles_fast():
                yield bond_angle

    def plot_angle_distribution(self) -> None:
        bond_angles = self.gen_bond_angles()
        hist, bins = np.histogram([], bins=100, range=(0, 360))
        for bond_angle in bond_angles:
            hist += np.histogram([bond_angle], bins=bins)[0]
        ax = plt.gca()
        ax.bar(bins[:-1], hist, width=np.diff(bins), align="edge")
        format_axes(ax, "Bond Angle (degrees)", "Frequency", 0, 360, 0, None, 30, None)
        arrowed_spines(ax)

    def plot_angle_variance_vs_pore_size(self) -> None:
        data = self.data_by_therm_pore(get_angle_variance)
        data = {temperature: {pore: (np.mean(energies), np.std(energies)) for pore, energies in pore_sizes.items()}
                for temperature, pore_sizes in data.items()}
        cmap = cm.get_cmap("Wistia")
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        remove_axes(ax)
        min_temp = min(data.keys())
        temp_range = max(data.keys()) - min_temp
        max_pore_size = max(pore for pore_sizes in data.values() for pore in pore_sizes.keys())
        for temperature, pore_sizes in sorted(data.items()):
            sorted_pore_sizes = dict(sorted(pore_sizes.items()))
            color = cmap((temperature - min_temp) / temp_range)
            x = list(sorted_pore_sizes.keys())
            y = [mean for mean, std in sorted_pore_sizes.values()]
            yerr = [std for mean, std in sorted_pore_sizes.values()]
            ax.plot(x, y, color=color)
            ax.fill_between(x, [yi - err for yi, err in zip(y, yerr)], [yi + err for yi, err in zip(y, yerr)], color=color, alpha=0.3)
        format_axes(ax, "Pore Size", r"Average Angle Variance (degrees$\mathdefault{^2}$)", 8, max_pore_size, 0, None)
        arrowed_spines(ax)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, list(data.keys()), " \n" + r"$\mathdefault{log_{10}(T_{thermal})}$")

    def get_pore_fraction_vs_acceptance_rate(self, smoothing: float = 1) -> tuple[np.ndarray, np.ndarray]:
        data = defaultdict(list)
        for entry in self.entries:
            data[entry.pore_concentration].append(entry.acceptance_rate)
        data = {concentration: np.mean(acceptance_rates) for concentration, acceptance_rates in data.items()}
        # sort by concentration
        data = dict(sorted(data.items(), key=lambda x: x[0]))
        # Apply a moving average to the data
        acceptance_rates = pd.Series(list(data.values())).rolling(window=smoothing, min_periods=1).mean().tolist()
        return np.array(list(data.keys())), np.array(acceptance_rates)

    def plot_bond_length_variance_vs_pore_size(self) -> None:
        data = self.data_by_therm_pore(get_bond_length_variance)
        data = {temperature: {pore: (np.mean(variances), np.std(variances)) for pore, variances in pore_sizes.items()}
                for temperature, pore_sizes in data.items()}
        cmap = cm.get_cmap("Wistia")
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        remove_axes(ax)
        min_temp = min(data.keys())
        temp_range = max(data.keys()) - min_temp
        for temperature, pore_sizes in sorted(data.items()):
            sorted_pore_sizes = dict(sorted(pore_sizes.items()))
            color = cmap((temperature - min_temp) / temp_range)
            x = list(sorted_pore_sizes.keys())
            y = [mean for mean, std in sorted_pore_sizes.values()]
            yerr = [std for mean, std in sorted_pore_sizes.values()]
            ax.plot(x, y, color=color)
            ax.fill_between(x, [yi - err for yi, err in zip(y, yerr)], [yi + err for yi, err in zip(y, yerr)], color=color, alpha=0.3)
        format_axes(ax, "Pore Size", r"Average Bond Length Variance ($\mathdefault{a_0^2}$)", 8, None, 0, None)
        arrowed_spines(ax)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, list(data.keys()), " \n" + r"$\mathdefault{log_{10}(T_{thermal})}$")

    def plot_acceptance_rate_vs_pore_fraction(self) -> None:
        pore_fractions, acceptance_rates = self.get_pore_fraction_vs_acceptance_rate()
        plt.plot(pore_fractions, acceptance_rates)
        format_axes(plt.gca(), "Pore Fraction", "Acceptance Rate (%)", 0, None, 0, None)

    def plot_bond_length_variance_vs_pore_concentration_with_acceptance_rate(self) -> None:
        # Get the bond length variance data
        data = self.data_by_therm_pore_fraction(get_bond_length_variance)
        data = {temperature: {fraction: (np.mean(variances), np.std(variances)) for fraction, variances in fractions.items()}
                for temperature, fractions in data.items()}

        cmap = cm.get_cmap("Wistia")
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])

        remove_axes(ax, spines=["top"])
        min_temp = min(data.keys())
        temp_range = max(data.keys()) - min_temp

        for temperature, fractions in sorted(data.items()):
            sorted_fractions = dict(sorted(fractions.items()))
            color = cmap((temperature - min_temp) / temp_range)
            x = list(sorted_fractions.keys())
            y = [mean for mean, std in sorted_fractions.values()]
            yerr = [std for mean, std in sorted_fractions.values()]
            ax.plot(x, y, color=color)
            ax.fill_between(x, [yi - err for yi, err in zip(y, yerr)], [yi + err for yi, err in zip(y, yerr)], color=color, alpha=0.3)

        # Get the acceptance rate data
        pore_fractions, acceptance_rates = self.get_pore_fraction_vs_acceptance_rate(smoothing=5)
        assert pore_fractions.shape == acceptance_rates.shape
        acceptance_rates *= 100  # Convert to percentage

        ax2 = ax.twinx()  # Create a second y-axis
        # Plot the acceptance rate data on the second y-axis
        ax2.plot(pore_fractions, acceptance_rates, color="dodgerblue", label="Acceptance Rate", linewidth=3)
        ax2.set_ylabel("Acceptance Rate (%)", fontsize=20)
        ax2.tick_params(axis="y", color="dodgerblue", labelsize=20)
        ax2.spines["top"].set_visible(False)
        ax2.set_ylim(min(acceptance_rates), max(acceptance_rates))
        ax2.set_xlim(0, max(pore_fractions))
        format_axes(ax, "Pore Fraction", r"Average Bond Length Variance ($\mathdefault{a_0^2}$)", 0, max(pore_fractions), 0, None)

        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, list(data.keys()), " \n" + r"$\mathdefault{log_{10}(T_{thermal})}$")

    def plot_bond_length_variance_vs_pore_concentration(self) -> None:
        data = defaultdict(lambda: defaultdict(list))
        # use the colour bar for thermalisation temperature
        data = self.data_by_therm_pore_fraction(get_bond_length_variance)
        data = {temperature: {concentration: (np.mean(variances), np.std(variances)) for concentration, variances in concentrations.items()}
                for temperature, concentrations in data.items()}
        cmap = cm.get_cmap("Wistia")
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        remove_axes(ax)
        min_temp = min(data.keys())
        temp_range = max(data.keys()) - min_temp
        for temperature, concentrations in sorted(data.items()):
            sorted_concentrations = dict(sorted(concentrations.items()))
            color = cmap((temperature - min_temp) / temp_range)
            x = list(sorted_concentrations.keys())
            y = [mean for mean, std in sorted_concentrations.values()]
            yerr = [std for mean, std in sorted_concentrations.values()]
            ax.plot(x, y, color=color)
            ax.fill_between(x, [yi - err for yi, err in zip(y, yerr)], [yi + err for yi, err in zip(y, yerr)], color=color, alpha=0.3)
        format_axes(ax, "Pore Fraction", r"Average Bond Length Variance ($\mathdefault{a_0^2}$)", 0, None, 0, None)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, list(data.keys()), " \n" + r"$\mathdefault{log_{10}(T_{thermal})}$")

    def plot_angle_variance_vs_pore_concentration(self) -> None:
        data = defaultdict(lambda: defaultdict(list))
        # use the colour bar for thermalisation temperature
        data = self.data_by_therm_pore_fraction(get_angle_variance)
        data = {temperature: {concentration: (np.mean(variances), np.std(variances)) for concentration, variances in concentrations.items()}
                for temperature, concentrations in data.items()}
        cmap = cm.get_cmap("Wistia")
        gs = gridspec.GridSpec(1, 2, width_ratios=[20, 1])
        ax = plt.subplot(gs[0])
        remove_axes(ax)
        min_temp = min(data.keys())
        temp_range = max(data.keys()) - min_temp
        for temperature, concentrations in sorted(data.items()):
            sorted_concentrations = dict(sorted(concentrations.items()))
            color = cmap((temperature - min_temp) / temp_range)
            x = list(sorted_concentrations.keys())
            y = [mean for mean, std in sorted_concentrations.values()]
            yerr = [std for mean, std in sorted_concentrations.values()]
            ax.plot(x, y, color=color)
            ax.fill_between(x, [yi - err for yi, err in zip(y, yerr)], [yi + err for yi, err in zip(y, yerr)], color=color, alpha=0.3)
        format_axes(ax, "Pore Fraction", r"Average Angle  Variance ($\mathdefault{degrees^2}$)", 0, None, 0, None)
        colour_bar_axes = plt.subplot(gs[1])
        add_colourbar(colour_bar_axes, cmap, list(data.keys()), " \n" + r"$\mathdefault{log_{10}(T_{thermal})}$")

    @ property
    def num_entries(self) -> int:
        return len(self.entries)
