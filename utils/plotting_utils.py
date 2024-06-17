from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import cm
from matplotlib.axes import Axes
from matplotlib.cm import ScalarMappable
from matplotlib.colors import (BoundaryNorm, Colormap, ListedColormap,
                               Normalize, to_rgba)
from matplotlib.patches import FancyArrow
from matplotlib.ticker import NullLocator


def get_ring_colours_1() -> list[tuple[float, float, float, float]]:
    """
    Gets a colour palette for ring sizes 

    Returns:
        A list of colours for the rings, where each index is equivalent to a ring size
    """
    colour_maps = ["YlGnBu", "YlGnBu", "GnBu", "Greys", "YlOrRd", "YlOrRd", "RdPu", "RdPu"]
    colours = [0.8, 0.7, 0.6, 0.3, 0.3, 0.5, 0.4, 0.7]
    ring_colours = [to_rgba("white")] * 3
    ring_colours.extend(cm.get_cmap(cmap)(colour) for cmap, colour in zip(colour_maps, colours))
    ring_colours.extend([to_rgba("black")] * 30)
    return ring_colours


def get_ring_colours_2(average_ring_size: int = 6) -> list[tuple[float, float, float, float]]:
    """
    Gets a colour palette for ring sizes 

    Returns:
        A list of colours for the rings, where each index is equivalent to a ring size
        Average ring size is coloured grey
        Rings over the average size are coloured red
        Rings under the average size are coloured blue
    """
    map_lower = ListedColormap(cm.get_cmap("Blues_r")(np.arange(20, 100)))
    map_upper = ListedColormap(cm.get_cmap("Reds")(np.arange(50, 100)))
    norm_lower = Normalize(vmin=average_ring_size - 3, vmax=average_ring_size)
    norm_upper = Normalize(vmin=average_ring_size, vmax=average_ring_size + 6)
    colour_mean = cm.get_cmap("Greys")(50)

    return [to_rgba("white") if i < 3 else
            colour_mean if np.abs(i - average_ring_size) < 1e-6 else
            map_lower(norm_lower(i)) if i < average_ring_size else
            map_upper(norm_upper(i)) for i in range(340)]


def get_ring_colours_3() -> list[tuple[float, float, float, float]]:
    """
    Gets a colour palette for ring sizes 

    Returns:
        A list of colours for the rings, where each index is equivalent to a ring size
    """
    colormaps = ["GnBu", "Greens", "Blues", "Greys", "Reds", "YlOrBr", "PuRd", "RdPu"]
    color_values = [140, 100, 150, 90, 105, 100, 100, 80]
    ring_colours = [to_rgba("white")] * 3
    ring_colours.extend(cm.get_cmap(cmap)(value) for cmap, value in zip(colormaps, color_values))
    ring_colours.extend([to_rgba("black")] * 30)
    return ring_colours


def get_ring_colours_4() -> list[tuple[float, float, float, float]]:
    """
    Gets a colour palette for ring sizes (best palette)

    Returns:
        A list of colours for the rings, where each index is equivalent to a ring size
    """
    ring_colours = [to_rgba("white")] * 2 + [to_rgba("black")]
    ring_colours.extend(cm.get_cmap("cividis")(i) for i in np.linspace(0, 1, 8))
    ring_colours.extend(cm.get_cmap("YlOrRd")(i) for i in np.linspace(0.4, 1, 8))
    return ring_colours


def save_plot(save_path: Path, dimensions: tuple[int, int] = (6, 6), dpi: int = 300) -> None:
    """
    Saves the current plot to a file without clearing it

    Args:
        save_path: The path to save the plot to
        dimensions: The dimensions of the plot in inches
        dpi: The resolution of the plot
    """
    fig = plt.gcf()
    fig.set_size_inches(dimensions[0], dimensions[1])
    plt.savefig(save_path, dpi=dpi, bbox_inches='tight', pad_inches=0.1)


def arrowed_spines(ax: Axes, x_width_fraction: float = 0.02, x_height_fraction: float = 0.02,
                   line_width: float = 0, overhang_fraction: float = 0.3,
                   locations: tuple[str] = ("bottom right", "left up"), **arrow_kwargs) -> dict[str, FancyArrow]:

    arrow_kwargs = {"overhang": overhang_fraction,
                    "clip_on": False,
                    "length_includes_head": True,
                    "head_starts_at_zero": False,
                    **arrow_kwargs}

    line_width = line_width or ax.spines["left"].get_linewidth()
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()

    hw = x_width_fraction * (ymax - ymin)
    hl = x_height_fraction * (xmax - xmin)

    fig = ax.get_figure()
    width, height = fig.get_size_inches()
    yhw = hw / (ymax - ymin) * (xmax - xmin) * height / width
    yhl = hl / (xmax - xmin) * (ymax - ymin) * width / height

    annotations = {location: ax.arrow(0 if side == "zero" else (xmin if side in {"left", "bottom"} else xmax),
                                      0 if side == "zero" else (ymin if side in {"left", "bottom"} else ymax),
                                      0 if direction in {"left", "right"} else ((xmax - xmin) + 2 * hl),
                                      0 if direction in {"up", "down"} else (ymax - ymin),
                                      fc="k", ec="k", lw=line_width,
                                      head_width=(yhw, hw)[direction in {"up", "down"}],
                                      head_length=(yhl, hl)[direction in {"up", "down"}],
                                      **arrow_kwargs)
                   for location in locations for side, direction in [location.split(" ")]}

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    return annotations


def format_axes(ax: Axes,
                x_label: str, y_label: str,
                xlo: Optional[float] = None, xhi: Optional[float] = None,
                ylo: Optional[float] = None, yhi: Optional[float] = None,
                x_tick_separation: Optional[float] = None, y_tick_separation: Optional[float] = None,
                label_font_size: int = 20, ticks_font_size: int = 20) -> None:
    """
    Formats the axes of a plot

    Args:
        ax: The axes to format
        x_label: The label for the x-axis
        y_label: The label for the y-axis
        xlo: The lower bound of the x-axis
        xhi: The upper bound of the x-axis
        ylo: The lower bound of the y-axis
        yhi: The upper bound of the y-axis
        x_tick_separation: The separation between x-axis ticks
        y_tick_separation: The separation between y-axis ticks
        label_font_size: The font size of the axis labels
        ticks_font_size: The font size of the axis ticks
    """

    ax.set_xlabel(x_label, fontsize=label_font_size)
    ax.set_ylabel(y_label, fontsize=label_font_size)
    xlo = ax.get_xlim()[0] if xlo is None else xlo
    xhi = ax.get_xlim()[1] if xhi is None else xhi
    ylo = ax.get_ylim()[0] if ylo is None else ylo
    yhi = ax.get_ylim()[1] if yhi is None else yhi
    ax.set_xlim(xlo, xhi)
    ax.set_ylim(ylo, yhi)
    if x_tick_separation is not None:
        ax.set_xticks(np.arange(xlo, xhi + 1, x_tick_separation))
    if y_tick_separation is not None:
        ax.set_yticks(np.arange(ylo, yhi + 1, y_tick_separation))
    ax.tick_params(axis='both', which='major', labelsize=ticks_font_size)


def remove_axes(ax: Axes, spines: list[str] = ["top", "right"]) -> None:
    """
    Removes the specified spines from an axes

    Args:
        ax: The axes to remove the spines from
        spines: The spines to remove
    """
    for spine in spines:
        ax.spines[spine].set_visible(False)


def add_colourbar(ax: Axes, cmap: Colormap, ticks: list, label: str, orientation: str = "vertical") -> None:
    """
    Adds a colourbar to axes

    Args:
        ax: The axes to add the colourbar to
        cmap: The colour map to use
        ticks: The ticks to use on the colourbar
        label: The label for the colourbar
        orientation: The orientation of the colourbar
    """
    norm = plt.Normalize(vmin=min(ticks), vmax=max(ticks))
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, cax=ax, orientation=orientation)
    cbar.set_ticks(sorted(set(ticks)))
    ax.set_xlabel(label, fontsize=20)
    cbar.ax.tick_params(labelsize=20)


def add_colourbar_2(ax: Axes, cmap: Colormap, label: str, min_label: float, max_label: float, orientation: str = "vertical") -> None:
    """
    Adds a colourbar to axes designed for ring sizes. Labels are centered about each colour

    Args:
        ax: The axes to add the colourbar to
        cmap: The colour map to use
        label: The label for the colourbar
        min_label: The minimum label for the colourbar
        max_label: The maximum label for the colourbar
        orientation: The orientation of the colourbar
    """
    num_colors = len(cmap.colors)
    boundaries = np.linspace(min_label - 0.5, max_label + 0.5, num_colors + 1)

    norm = BoundaryNorm(boundaries=boundaries, ncolors=cmap.N)
    sm = ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])

    # Create the colorbar
    cbar = plt.colorbar(sm, cax=ax, orientation=orientation, ticks=np.linspace(min_label, max_label, num_colors))

    # Change the label of the maximum tick to "max_tick+"
    max_tick = int(cbar.get_ticks()[-1])
    tick_labels = [str(int(tick)) if tick < max_tick else f'{max_tick}+' for tick in cbar.get_ticks()]
    cbar.set_ticklabels(tick_labels)

    # Remove minor ticks
    cbar.ax.yaxis.set_minor_locator(NullLocator())

    ax.set_xlabel(label, fontsize=20)
    cbar.ax.tick_params(labelsize=20)


def add_colourbar_3(ax: Axes, cmap: Colormap, ticks: list, label: str, orientation: str = "vertical") -> None:
    """
    Adds a colourbar to axes

    Args:
        ax: The axes to add the colourbar to
        cmap: The colour map to use
        ticks: The ticks to use on the colourbar
        label: The label for the colourbar
        orientation: The orientation of the colourbar
    """
    # Adjust the boundaries to be halfway between the ring sizes
    boundaries = [(ticks[i] + ticks[i + 1]) / 2 for i in range(len(ticks) - 1)]
    # Add the first and last boundaries
    boundaries = [ticks[0] - 0.5] + boundaries + [ticks[-1] + 0.5]

    # Create a boundary norm with the adjusted boundaries
    norm = BoundaryNorm(boundaries=boundaries, ncolors=cmap.N)
    sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, cax=ax, orientation=orientation, ticks=ticks)
    ax.set_xlabel(label, fontsize=20)
    cbar.ax.tick_params(labelsize=20)
