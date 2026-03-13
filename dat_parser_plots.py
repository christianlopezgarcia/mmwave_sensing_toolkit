"""
dat_parser_plots.py
-------------------
Reusable module for parsing TI mmWave .dat files and generating plots.

Importing this module does NOT execute any code automatically.
All functions are designed to be called explicitly by pipeline or
visualization scripts.
"""

import os

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from scipy.ndimage import gaussian_filter

from ti_mmw_official_tool.parser_scripts.parser_mmw_demo import parser_one_mmw_demo_output_packet


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

FRAME_PERIOD = 0.1


# --------------------------------------------------
# PARSER
# --------------------------------------------------

def parse_dat_file(dat_file):
    """
    Parse a TI mmWave .dat binary file into per-frame point clouds
    and velocity arrays.

    Parameters
    ----------
    dat_file : str
        Path to the .dat file to parse.

    Returns
    -------
    frames_points : list of np.ndarray
        List of (N, 3) arrays containing [X, Y, Z] for each frame.
        Empty frames contain a (0, 3) array.
    frames_velocity : list of np.ndarray
        List of 1-D arrays of Doppler velocity values per frame.
        Empty frames contain an empty array.
    """

    with open(dat_file, "rb") as fp:
        allBinData = fp.read()

    readNumBytes = len(allBinData)
    totalBytesParsed = 0

    frames_points = []
    frames_velocity = []

    numFramesParsed = 0

    while totalBytesParsed < readNumBytes:

        result = parser_one_mmw_demo_output_packet(
            allBinData[totalBytesParsed:],
            readNumBytes - totalBytesParsed
        )

        parser_result = result[0]

        if parser_result != 0:
            break

        headerStartIndex = result[1]
        totalPacketNumBytes = result[2]
        numDetObj = result[3]

        detectedX = result[6]
        detectedY = result[7]
        detectedZ = result[8]
        detectedV = result[9]

        totalBytesParsed += headerStartIndex + totalPacketNumBytes
        numFramesParsed += 1

        if numDetObj > 0:
            points = np.column_stack((
                detectedX[:numDetObj],
                detectedY[:numDetObj],
                detectedZ[:numDetObj]
            ))
            velocities = np.array(detectedV[:numDetObj])

            frames_points.append(points)
            frames_velocity.append(velocities)
        else:
            frames_points.append(np.empty((0, 3)))
            frames_velocity.append(np.array([]))

    print("Total frames parsed:", numFramesParsed)
    return frames_points, frames_velocity


# --------------------------------------------------
# DATA PROCESSING
# --------------------------------------------------

def compute_range_frames(frames_points):
    """
    Compute the Euclidean range for every detected point, organised by frame.

    Parameters
    ----------
    frames_points : list of np.ndarray
        Per-frame (N, 3) XYZ point clouds as returned by parse_dat_file.

    Returns
    -------
    time_axis : np.ndarray
        1-D array of frame timestamps in seconds.
    range_frames : list of np.ndarray
        Per-frame arrays of range (distance) values.
    """

    time_axis = []
    range_frames = []

    for i, points in enumerate(frames_points):
        time_axis.append(i * FRAME_PERIOD)

        if len(points) > 0:
            ranges = np.sqrt(
                points[:, 0] ** 2 +
                points[:, 1] ** 2 +
                points[:, 2] ** 2
            )
            range_frames.append(ranges)
        else:
            range_frames.append(np.array([]))

    return np.array(time_axis), range_frames


def flatten_data(time_axis, frames_points, frames_velocity):
    """
    Flatten per-frame data into three parallel 1-D arrays suitable
    for scatter plots and 2-D histograms.

    Parameters
    ----------
    time_axis : np.ndarray
        Frame timestamps as returned by compute_range_frames.
    frames_points : list of np.ndarray
        Per-frame XYZ point clouds.
    frames_velocity : list of np.ndarray
        Per-frame Doppler velocity arrays.

    Returns
    -------
    all_times : np.ndarray
        Timestamp for every detected point.
    all_velocities : np.ndarray
        Doppler velocity for every detected point.
    all_ranges : np.ndarray
        Euclidean range for every detected point.
    """

    all_times = []
    all_velocities = []
    all_ranges = []

    for i, vels in enumerate(frames_velocity):
        if len(vels) > 0:
            pts = frames_points[i]
            rngs = np.sqrt(
                pts[:, 0] ** 2 +
                pts[:, 1] ** 2 +
                pts[:, 2] ** 2
            )
            all_times.extend([time_axis[i]] * len(vels))
            all_velocities.extend(vels)
            all_ranges.extend(rngs)

    return (
        np.array(all_times),
        np.array(all_velocities),
        np.array(all_ranges)
    )


# --------------------------------------------------
# PLOTTING UTILITIES
# --------------------------------------------------

def _save_or_show(save_path):
    """
    Internal helper: save the current figure to disk when save_path is
    provided, otherwise show it interactively.

    Parameters
    ----------
    save_path : str or None
        Full path (including filename) to write the PNG to.
        Pass None to display interactively instead.
    """
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        plt.close()
        print("Saved:", save_path)
    else:
        plt.show()


def plot_micro_doppler(all_ranges, all_velocities, save_path=None):
    """
    Plot a 2-D histogram of range vs. Doppler velocity (micro-Doppler map).

    Parameters
    ----------
    all_ranges : np.ndarray
        Flattened range values.
    all_velocities : np.ndarray
        Flattened velocity values.
    save_path : str or None
        File path to save the figure, or None to display interactively.
    """
    plt.figure(figsize=(10, 6))
    plt.hist2d(
        all_ranges,
        all_velocities,
        bins=[50, 50],
        cmap="viridis",
        cmin=1
    )
    plt.xlabel("Range (m)")
    plt.ylabel("Velocity (m/s)")
    plt.title("Range-Doppler / Micro-Doppler")
    plt.colorbar(label="Point Count")
    _save_or_show(save_path)


def plot_velocity_trends(all_times, all_velocities, save_path=None):
    """
    Plot a hexbin density map of velocity over time.

    Parameters
    ----------
    all_times : np.ndarray
        Flattened timestamp values.
    all_velocities : np.ndarray
        Flattened velocity values.
    save_path : str or None
        File path to save the figure, or None to display interactively.
    """
    plt.figure(figsize=(14, 5))
    plt.hexbin(
        all_times,
        all_velocities,
        gridsize=(80, 40),
        cmap="magma",
        mincnt=1
    )
    plt.xlabel("Time (s)")
    plt.ylabel("Velocity (m/s)")
    plt.title("Velocity Trends")
    plt.colorbar(label="Reflection Density")
    _save_or_show(save_path)


def plot_range_vs_time_scatter(time_axis, range_frames, save_path=None):
    """
    Plot per-frame range detections as a scatter plot over time.

    Parameters
    ----------
    time_axis : np.ndarray
        Frame timestamps.
    range_frames : list of np.ndarray
        Per-frame range arrays as returned by compute_range_frames.
    save_path : str or None
        File path to save the figure, or None to display interactively.
    """
    plt.figure(figsize=(14, 5))
    for i, rngs in enumerate(range_frames):
        if len(rngs) > 0:
            plt.scatter(
                [time_axis[i]] * len(rngs),
                rngs,
                s=5,
                alpha=0.6
            )
    plt.xlabel("Time (s)")
    plt.ylabel("Range (m)")
    plt.title("Range vs Time Scatter")
    plt.grid(True)
    _save_or_show(save_path)


# --------------------------------------------------
# CONVENIENCE: SAVE ALL STANDARD PLOTS
# --------------------------------------------------

def save_all_plots(output_dir, base_name,
                   all_times, all_velocities, all_ranges,
                   time_axis, range_frames):
    """
    Generate and save all standard plots to output_dir using a
    numbered naming convention.

    Parameters
    ----------
    output_dir : str
        Directory in which to write the PNG files.
    base_name : str
        Base filename (without extension) used as a naming prefix.
    all_times : np.ndarray
    all_velocities : np.ndarray
    all_ranges : np.ndarray
    time_axis : np.ndarray
    range_frames : list of np.ndarray
    """

    def _path(index, description):
        return os.path.join(output_dir, f"{index:02d}_{description}.png")

    plot_micro_doppler(
        all_ranges, all_velocities,
        save_path=_path(2, "micro_doppler")
    )

    plot_velocity_trends(
        all_times, all_velocities,
        save_path=_path(3, "velocity_trends")
    )

    plot_range_vs_time_scatter(
        time_axis, range_frames,
        save_path=_path(4, "range_vs_time_scatter")
    )


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":
    import sys
    
    dat_file = r"repo\mmwave_sensing_toolkit\dat_directory\20260313_135643_new_file_system\xwr68xx_AOP_processed_stream_2026_03_13T20_56_32_549.dat"

    # Parse
    frames_points, frames_velocity = parse_dat_file(dat_file)

    # Compute derived data structures
    time_axis, range_frames = compute_range_frames(frames_points)

    all_times, all_velocities, all_ranges = flatten_data(
        time_axis,
        frames_points,
        frames_velocity,
    )

    # Display all plots interactively (save_path=None → plt.show())
    plot_micro_doppler(all_ranges, all_velocities)
    plot_velocity_trends(all_times, all_velocities)
    plot_range_vs_time_scatter(time_axis, range_frames)