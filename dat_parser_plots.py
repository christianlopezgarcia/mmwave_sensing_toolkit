"""
dat_parser_plots.py
-------------------
Reusable module for parsing TI mmWave .dat files and generating plots.

Importing this module does NOT execute any code automatically.
All functions are designed to be called explicitly by pipeline or
visualization scripts.
"""

import os
import glob
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d import Axes3D

from ti_mmw_official_tool.parser_scripts.parser_mmw_demo import parser_one_mmw_demo_output_packet


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

FRAME_PERIOD = 0.1


# --------------------------------------------------
# FILE UTILITIES
# --------------------------------------------------

def find_latest_dat_file(directory_path):
    """
    Find the most recently modified .dat file in the specified directory.
    """
    search_pattern = os.path.join(directory_path, '*.dat')
    list_of_files = glob.glob(search_pattern)
    
    if not list_of_files:
        return None
        
    latest_file = max(list_of_files, key=os.path.getmtime)
    return latest_file


# --------------------------------------------------
# PARSER
# --------------------------------------------------

def parse_dat_file(dat_file):
    """
    Parse a TI mmWave .dat binary file into per-frame point clouds
    and velocity arrays.
    """
    with open(dat_file, "rb") as fp:
        allBinData = fp.read()

    readNumBytes = len(allBinData)
    totalBytesParsed = 0

    frames_points = []
    frames_velocity = []

    numFramesParsed = 0

    while totalBytesParsed < readNumBytes:
        # Note: Unpacking adapted to standard parser_one_mmw_demo_output_packet length
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

def _save_or_show(save_path, ani=None):
    """
    Internal helper: save the current figure to disk when save_path is
    provided, otherwise show it interactively. Also handles animations.
    """
    if save_path:
        if ani:
            # Save animation using pillow (for gif) or ffmpeg (for mp4)
            writer = 'pillow' if save_path.endswith('.gif') else 'ffmpeg'
            ani.save(save_path, writer=writer)
            print("Saved Animation:", save_path)
        else:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            print("Saved:", save_path)
        plt.close()
    else:
        plt.show()


# --- ANIMATIONS ---

def animate_3d_point_cloud(frames_points, frames_velocity, save_path=None):
    """3D animated scatter of point clouds."""
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    def update(frame_idx):
        ax.cla()
        points = frames_points[frame_idx]
        velocities = frames_velocity[frame_idx]

        ax.set_xlim(-5, 5)
        ax.set_ylim(0, 10)
        ax.set_zlim(-3, 3)

        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_zlabel("Z (m)")
        ax.set_title(f"Frame {frame_idx}")

        if len(points) > 0:
            ax.scatter(
                points[:, 0],
                points[:, 1],
                points[:, 2],
                c=velocities,
                cmap='jet'
            )
        return []

    ani = FuncAnimation(fig, update, frames=len(frames_points), interval=50)
    _save_or_show(save_path, ani=ani)


def animate_range_vs_time(time_axis, range_frames, save_path=None):
    """Animated 2D scatter of range over time."""
    fig2, ax2 = plt.subplots()

    all_times_acc = []
    all_ranges_acc = []

    def update_range(frame_idx):
        if len(range_frames[frame_idx]) > 0:
            t = np.ones(len(range_frames[frame_idx])) * time_axis[frame_idx]
            all_times_acc.extend(t)
            all_ranges_acc.extend(range_frames[frame_idx])

        ax2.cla()
        if len(time_axis) > 0:
            ax2.set_xlim(0, time_axis[-1])
        ax2.set_ylim(0, 10)
        ax2.set_xlabel("Time (s)")
        ax2.set_ylabel("Range (m)")
        ax2.set_title("Range vs Time Animation")

        if all_times_acc:
            ax2.scatter(all_times_acc, all_ranges_acc, s=5)
        
        return []

    ani2 = FuncAnimation(fig2, update_range, frames=len(range_frames), interval=50)
    _save_or_show(save_path, ani=ani2)


# --- HISTOGRAMS & DENSITY MAPS ---

def plot_micro_doppler_high_fidelity(all_times, all_velocities, save_path=None):
    """Plot A: High-Fidelity Micro-Doppler (Velocity vs Time) using turbo and PowerNorm."""
    plt.figure(figsize=(12, 5))
    plt.hist2d(all_times, all_velocities, bins=[350, 150], cmap='turbo', 
               norm=mcolors.PowerNorm(gamma=0.4))
    plt.colorbar(label='Reflection Density')
    plt.title("High-Fidelity Micro-Doppler Signature (VT)")
    plt.xlabel("Time (s)")
    plt.ylabel("Velocity (m/s)")
    plt.grid(alpha=0.2)
    _save_or_show(save_path)


def plot_range_time_intensity(all_times, all_ranges, save_path=None):
    """Plot B: Range-Time Intensity Profile (RT) using turbo and LogNorm."""
    plt.figure(figsize=(12, 5))
    plt.hist2d(all_times, all_ranges, bins=[350, 200], cmap='turbo', 
               norm=mcolors.LogNorm())
    plt.colorbar(label='Signal Intensity')
    plt.title("Range-Time Intensity Profile (RT)")
    plt.xlabel("Time (s)")
    plt.ylabel("Range (m)")
    plt.ylim(0, 10)
    _save_or_show(save_path)


def plot_velocity_histogram_per_frame(time_axis, frames_velocity, save_path=None):
    """Overlapping histograms of velocity per frame."""
    plt.figure(figsize=(10, 5))
    for i, vels in enumerate(frames_velocity):
        if len(vels) > 0:
            plt.hist(vels, bins=20, alpha=0.3, label=f"t={time_axis[i]:.2f}s")
    plt.xlabel("Velocity (m/s)")
    plt.ylabel("Count")
    plt.title("Velocity Distribution Over Time")
    # Only show legend if there aren't too many frames, otherwise it crowds the plot
    if len(frames_velocity) <= 20:
        plt.legend()
    _save_or_show(save_path)


# --- SCATTER & LINE PLOTS ---

def plot_range_vs_time_scatter(time_axis, range_frames, save_path=None):
    """Static scatter plot of Range vs Time (original basic style)."""
    plt.figure()
    for i in range(len(range_frames)):
        if len(range_frames[i]) > 0:
            t = np.ones(len(range_frames[i])) * time_axis[i]
            plt.scatter(t, range_frames[i], s=5)
    
    plt.xlabel("Time (s)")
    plt.ylabel("Range (m)")
    plt.title("Range vs Time")
    plt.grid()
    _save_or_show(save_path)


def plot_velocity_vs_time_scatter(all_times, all_velocities, save_path=None):
    """Scatter plot of velocity over time colored by velocity (viridis)."""
    plt.figure(figsize=(10, 5))
    plt.scatter(all_times, all_velocities, s=5, c=all_velocities, cmap='viridis')
    plt.colorbar(label="Velocity (m/s)")
    plt.xlabel("Time (s)")
    plt.ylabel("Velocity (m/s)")
    plt.title("Velocity of Detected Objects vs Time")
    plt.grid(True)
    _save_or_show(save_path)


def plot_average_velocity(time_axis, frames_velocity, save_path=None):
    """Line plot of average velocity per frame."""
    avg_velocity = [np.mean(v) if len(v) > 0 else 0 for v in frames_velocity]
    
    plt.figure(figsize=(10, 5))
    plt.plot(time_axis, avg_velocity, '-o', color='red')
    plt.xlabel("Time (s)")
    plt.ylabel("Average Velocity (m/s)")
    plt.title("Average Velocity vs Time")
    plt.grid(True)
    _save_or_show(save_path)


def plot_max_velocity(time_axis, frames_velocity, save_path=None):
    """Line plot of maximum velocity per frame."""
    max_velocity = [np.max(v) if len(v) > 0 else 0 for v in frames_velocity]
    
    plt.figure(figsize=(10, 5))
    plt.plot(time_axis, max_velocity, '-o', color='blue')
    plt.xlabel("Time (s)")
    plt.ylabel("Maximum Velocity (m/s)")
    plt.title("Maximum Velocity vs Time")
    plt.grid(True)
    _save_or_show(save_path)


# --------------------------------------------------
# CONVENIENCE: SAVE ALL STANDARD PLOTS
# --------------------------------------------------

def save_all_plots(output_dir, base_name,
                   all_times, all_velocities, all_ranges,
                   time_axis, range_frames, frames_points, frames_velocity):
    """
    Generate and save all static standard plots to output_dir using a
    numbered naming convention. (Animations excluded to save processing time, 
    call them individually if needed).
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    def _path(index, description):
        return os.path.join(output_dir, f"{index:02d}_{description}.png")

    plot_range_vs_time_scatter(time_axis, range_frames, save_path=_path(3, "range_vs_time_scatter"))
    plot_velocity_vs_time_scatter(all_times, all_velocities, save_path=_path(4, "velocity_vs_time_scatter"))
    # plot_average_velocity(time_axis, frames_velocity, save_path=_path(5, "avg_velocity"))
    # plot_max_velocity(time_axis, frames_velocity, save_path=_path(6, "max_velocity"))
    # plot_velocity_histogram_per_frame(time_axis, frames_velocity, save_path=_path(7, "velocity_hist_per_frame"))
    plot_range_time_intensity(all_times, all_ranges, save_path=_path(1, "range_time_intensity"))
    plot_micro_doppler_high_fidelity(all_times, all_velocities, save_path=_path(2, "micro_doppler_high_fidelity"))
    

# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":
    
    # Example logic to find and parse the file automatically
    # your_path = r"C:\Users\c1op3\Downloads"
    # dat_file = find_latest_dat_file(your_path)
    dat_file = r"C:\Users\c1op3\Downloads\xwr68xx_AOP_processed_stream_2026_02_26T06_17_54_793.dat"
    print(f"The latest .dat file found is: {dat_file}")
    
    # Parse
    frames_points, frames_velocity = parse_dat_file(dat_file)

    # Compute derived data structures
    time_axis, range_frames = compute_range_frames(frames_points)
    all_times, all_velocities, all_ranges = flatten_data(time_axis, frames_points, frames_velocity)

    # ---------------------------
    # Display all plots interactively
    # ---------------------------
    
    # Animations (Comment out if you just want static plots)
    # animate_3d_point_cloud(frames_points, frames_velocity)
    # animate_range_vs_time(time_axis, range_frames)
    
    # Static Plots
    plot_range_vs_time_scatter(time_axis, range_frames)
    plot_velocity_vs_time_scatter(all_times, all_velocities)
    # plot_average_velocity(time_axis, frames_velocity)
    # plot_max_velocity(time_axis, frames_velocity)
    # plot_velocity_histogram_per_frame(time_axis, frames_velocity)
    
    # High-Fidelity Density Maps
    plot_micro_doppler_high_fidelity(all_times, all_velocities)
    plot_range_time_intensity(all_times, all_ranges)