"""
dat_parser_plots.py
-------------------
Reusable module for parsing TI mmWave .dat files and generating plots.
Updated to support Azimuth, Elevation, SNR extraction, Parallel Chunk Parsing,
Hardware Clock Unwrapping, and Plot Saving.
"""

import os
import glob
import time
import struct
import numpy as np
from datetime import datetime
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from ti_mmw_official_tool.parser_scripts.parser_mmw_demo import parser_one_mmw_demo_output_packet

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------
NUM_CHUNKS = 24  # Threads/Chunks to split the dat file into
MAGIC_WORD = bytes([2, 1, 4, 3, 6, 5, 8, 7])

# --------------------------------------------------
# PARSER UTILITIES & MULTIPROCESSING
# --------------------------------------------------

def find_latest_dat_file(directory_path):
    search_pattern = os.path.join(directory_path, '*.dat')
    list_of_files = glob.glob(search_pattern)
    if not list_of_files:
        return None
    return max(list_of_files, key=os.path.getmtime)

def get_chunk_boundaries(filepath, num_chunks):
    """
    Splits the file into byte ranges, ensuring each chunk starts EXACTLY at a magic word.
    """
    file_size = os.path.getsize(filepath)
    if file_size == 0:
        return []
        
    chunk_size = file_size // num_chunks
    boundaries = [0]
    
    with open(filepath, 'rb') as f:
        for i in range(1, num_chunks):
            target_start = i * chunk_size
            f.seek(target_start)
            # Read ahead slightly to find the next clean magic word boundary
            search_window = f.read(1024 * 1024) 
            idx = search_window.find(MAGIC_WORD)
            
            if idx != -1:
                boundaries.append(target_start + idx)
            else:
                boundaries.append(target_start) 
                
    boundaries.append(file_size)
    
    # Create start/end tuples for each chunk
    chunks = [(boundaries[i], boundaries[i+1]) for i in range(len(boundaries)-1) if boundaries[i] != boundaries[i+1]]
    return chunks

def parse_chunk(args):
    """
    Worker function to parse a specific byte range of the file.
    """
    filepath, start_idx, end_idx = args
    
    with open(filepath, 'rb') as f:
        f.seek(start_idx)
        chunk_data = f.read(end_idx - start_idx)
        
    readNumBytes = len(chunk_data)
    totalBytesParsed = 0
    
    c_frames_points, c_frames_velocity = [], []
    c_frames_azimuth, c_frames_elevation = [], []
    c_frames_snr, c_frames_cycles = [], []

    while totalBytesParsed < readNumBytes:
        result = parser_one_mmw_demo_output_packet(
            chunk_data[totalBytesParsed:],
            readNumBytes - totalBytesParsed
        )

        if result[0] != 0: # TC_FAIL
            break

        headerStartIndex = result[1]
        totalPacketNumBytes = result[2]
        numDetObj = result[3]
        timeCpuCycles = result[-1] # The newly extracted CPU cycles

        totalBytesParsed += headerStartIndex + totalPacketNumBytes

        c_frames_cycles.append(timeCpuCycles)

        if numDetObj > 0:
            points = np.column_stack((
                result[6][:numDetObj],   # X
                result[7][:numDetObj],   # Y
                result[8][:numDetObj]    # Z
            ))
            c_frames_points.append(points)
            c_frames_velocity.append(np.array(result[9][:numDetObj]))
            c_frames_azimuth.append(np.array(result[11][:numDetObj]))
            c_frames_elevation.append(np.array(result[12][:numDetObj]))
            c_frames_snr.append(np.array(result[13][:numDetObj]))
        else:
            c_frames_points.append(np.empty((0, 3)))
            c_frames_velocity.append(np.array([]))
            c_frames_azimuth.append(np.array([]))
            c_frames_elevation.append(np.array([]))
            c_frames_snr.append(np.array([]))

    return c_frames_points, c_frames_velocity, c_frames_azimuth, c_frames_elevation, c_frames_snr, c_frames_cycles

def parse_dat_file_parallel(dat_file, num_chunks=NUM_CHUNKS):
    """
    Main parser driver utilizing multiprocessing.
    """
    chunks = get_chunk_boundaries(dat_file, num_chunks)
    args = [(dat_file, start, end) for start, end in chunks]
    
    print(f"Spawning {len(chunks)} parallel workers to parse {dat_file}...")
    
    frames_points, frames_velocity = [], []
    frames_azimuth, frames_elevation = [], []
    frames_snr, frames_cycles = [], []
    
    with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
        results = list(executor.map(parse_chunk, args))
        
    for res in results:
        frames_points.extend(res[0])
        frames_velocity.extend(res[1])
        frames_azimuth.extend(res[2])
        frames_elevation.extend(res[3])
        frames_snr.extend(res[4])
        frames_cycles.extend(res[5])
        
    print(f"Complete. Total frames parsed: {len(frames_cycles)}")
    return frames_points, frames_velocity, frames_azimuth, frames_elevation, frames_snr, frames_cycles

# --------------------------------------------------
# DATA PROCESSING & HARDWARE CLOCK UNWRAPPING
# --------------------------------------------------

def unwrap_hardware_time(frames_cycles):
    """
    Unwraps the 32-bit CPU cycle counter to prevent the 21.47 second rollover.
    Converts cycle count to an absolute continuous time in seconds.
    """
    time_axis = []
    rollovers = 0
    prev_cycle = 0
    
    for cycle in frames_cycles:
        if cycle < prev_cycle and prev_cycle > 2**31:
            rollovers += 1
        prev_cycle = cycle
        
        # 200 MHz Clock -> seconds
        absolute_cycles = cycle + (rollovers * (2**32))
        t_sec = absolute_cycles / 200e6
        time_axis.append(t_sec)
        
    return np.array(time_axis)

# def compute_range_frames(time_axis, frames_points):
#     range_frames = []
#     for points in frames_points:
#         if len(points) > 0:
#             ranges = np.sqrt(np.sum(points**2, axis=1))
#             range_frames.append(ranges)
#         else:
#             range_frames.append(np.array([]))
#     return range_frames

def compute_range_frames(time_axis, frames_points):
    # Normalize the time axis so it starts at 0
    if len(time_axis) > 0:
        normalized_time = time_axis - time_axis[0]
    else:
        normalized_time = time_axis

    range_frames = []
    for points in frames_points:
        if len(points) > 0:
            # Use np.linalg.norm for cleaner, optimized Euclidean distance
            ranges = np.linalg.norm(points, axis=1)
            range_frames.append(ranges)
        else:
            range_frames.append(np.array([]))
            
    return normalized_time, range_frames

def flatten_data(time_axis, frames_points, frames_velocity, frames_azimuth, frames_elevation, frames_snr):
    """
    Flatten per-frame data into parallel 1-D arrays.
    """
    all_times, all_velocities, all_ranges = [], [], []
    all_azimuths, all_elevations, all_snrs = [], [], []

    for i, vels in enumerate(frames_velocity):
        if len(vels) > 0:
            pts = frames_points[i]
            rngs = np.sqrt(np.sum(pts**2, axis=1))
            
            n_pts = len(vels)
            all_times.extend([time_axis[i]] * n_pts)
            all_velocities.extend(vels)
            all_ranges.extend(rngs)
            all_azimuths.extend(frames_azimuth[i])
            all_elevations.extend(frames_elevation[i])
            all_snrs.extend(frames_snr[i])

    return (
        np.array(all_times), np.array(all_velocities), np.array(all_ranges),
        np.array(all_azimuths), np.array(all_elevations), np.array(all_snrs)
    )

# --------------------------------------------------
# PLOTTING UTILITIES
# --------------------------------------------------

def _save_or_show(save_path):
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        plt.close()
    else:
        plt.show()

def plot_micro_doppler_high_fidelity(all_times, all_velocities, save_path=None):
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
    plt.figure(figsize=(12, 5))
    plt.hist2d(all_times, all_ranges, bins=[350, 200], cmap='turbo', 
               norm=mcolors.LogNorm())
    plt.colorbar(label='Signal Intensity')
    plt.title("Range-Time Intensity Profile (RT)")
    plt.xlabel("Time (s)")
    plt.ylabel("Range (m)")
    plt.ylim(0, 10)
    _save_or_show(save_path)

def plot_angle_time_intensity(all_times, all_angles, title, ylabel, save_path=None):
    plt.figure(figsize=(12, 5))
    plt.hist2d(all_times, all_angles, bins=[350, 180], cmap='turbo', 
               norm=mcolors.PowerNorm(gamma=0.5))
    plt.colorbar(label='Point Density')
    plt.title(title)
    plt.xlabel("Time (s)")
    plt.ylabel(ylabel)
    plt.grid(alpha=0.2)
    _save_or_show(save_path)

def plot_snr_vs_time_scatter(all_times, all_snrs, save_path=None):
    plt.figure(figsize=(10, 5))
    plt.scatter(all_times, all_snrs, s=5, c=all_snrs, cmap='plasma', alpha=0.6)
    plt.colorbar(label="SNR")
    plt.xlabel("Time (s)")
    plt.ylabel("SNR")
    plt.title("Signal-to-Noise Ratio vs Time")
    plt.grid(True)
    _save_or_show(save_path)

def plot_range_vs_time_scatter(time_axis, range_frames, save_path=None):
    plt.figure()
    for i in range(len(range_frames)):
        if len(range_frames[i]) > 0:
            plt.scatter(np.ones(len(range_frames[i])) * time_axis[i], range_frames[i], s=5)
    plt.xlabel("Time (s)")
    plt.ylabel("Range (m)")
    plt.title("Range vs Time")
    plt.grid()
    _save_or_show(save_path)

def plot_velocity_vs_time_scatter(all_times, all_velocities, save_path=None):
    plt.figure(figsize=(10, 5))
    plt.scatter(all_times, all_velocities, s=5, c=all_velocities, cmap='viridis')
    plt.colorbar(label="Velocity (m/s)")
    plt.xlabel("Time (s)")
    plt.ylabel("Velocity (m/s)")
    plt.title("Velocity vs Time")
    plt.grid(True)
    _save_or_show(save_path)

# --------------------------------------------------
# COMPARISON PLOTS (Stacked Layouts)
# --------------------------------------------------

def plot_compare_velocity_range(all_times, all_velocities, time_axis, range_frames, save_path=None):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    sc = ax1.scatter(all_times, all_velocities, s=5, c=all_velocities, cmap='viridis')
    ax1.set_ylabel("Velocity (m/s)")
    ax1.set_title("Velocity (Top) vs Range (Bottom)")
    ax1.grid(True, alpha=0.3)
    
    for i in range(len(range_frames)):
        if len(range_frames[i]) > 0:
            ax2.scatter(np.ones(len(range_frames[i])) * time_axis[i], range_frames[i], s=5, color='tab:blue')
    ax2.set_ylabel("Range (m)")
    ax2.set_xlabel("Time (s)")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    _save_or_show(save_path)

def plot_compare_snr_range(all_times, all_snrs, time_axis, range_frames, save_path=None):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    ax1.scatter(all_times, all_snrs, s=5, c=all_snrs, cmap='plasma')
    ax1.set_ylabel("SNR")
    ax1.set_title("SNR (Top) vs Range (Bottom)")
    ax1.grid(True)

    for i in range(len(range_frames)):
        if len(range_frames[i]) > 0:
            ax2.scatter(np.ones(len(range_frames[i])) * time_axis[i], range_frames[i], s=5, color='tab:red')
    ax2.set_ylabel("Range (m)")
    ax2.set_xlabel("Time (s)")
    ax2.grid(True)

    plt.tight_layout()
    _save_or_show(save_path)

def plot_compare_micro_doppler_range(all_times, all_velocities, time_axis, range_frames, save_path=None):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    ax1.hist2d(all_times, all_velocities, bins=[350, 150], cmap='turbo', norm=mcolors.PowerNorm(gamma=0.4))
    ax1.set_ylabel("Velocity (m/s)")
    ax1.set_title("Micro-Doppler Intensity (Top) vs Range (Bottom)")

    for i in range(len(range_frames)):
        if len(range_frames[i]) > 0:
            ax2.scatter(np.ones(len(range_frames[i])) * time_axis[i], range_frames[i], s=5, color='black', alpha=0.5)
    ax2.set_ylabel("Range (m)")
    ax2.set_xlabel("Time (s)")

    plt.tight_layout()
    _save_or_show(save_path)

def plot_compare_azimuth_range(all_times, all_azimuths, time_axis, range_frames, save_path=None):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    ax1.hist2d(all_times, all_azimuths, bins=[350, 180], cmap='turbo', norm=mcolors.PowerNorm(gamma=0.5))
    ax1.set_ylabel("Azimuth (deg)")
    ax1.set_title("Azimuth Density (Top) vs Range (Bottom)")

    for i in range(len(range_frames)):
        if len(range_frames[i]) > 0:
            ax2.scatter(np.ones(len(range_frames[i])) * time_axis[i], range_frames[i], s=5, color='tab:green')
    ax2.set_ylabel("Range (m)")
    ax2.set_xlabel("Time (s)")

    plt.tight_layout()
    _save_or_show(save_path)

def plot_compare_elevation_range(all_times, all_elevations, time_axis, range_frames, save_path=None):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    ax1.hist2d(all_times, all_elevations, bins=[350, 180], cmap='turbo', norm=mcolors.PowerNorm(gamma=0.5))
    ax1.set_ylabel("Elevation (deg)")
    ax1.set_title("Elevation Density (Top) vs Range (Bottom)")

    for i in range(len(range_frames)):
        if len(range_frames[i]) > 0:
            ax2.scatter(np.ones(len(range_frames[i])) * time_axis[i], range_frames[i], s=5, color='tab:purple')
    ax2.set_ylabel("Range (m)")
    ax2.set_xlabel("Time (s)")

    plt.tight_layout()
    _save_or_show(save_path)

def plot_compare_rti_range(all_times, all_ranges, time_axis, range_frames, save_path=None):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    ax1.hist2d(all_times, all_ranges, bins=[350, 200], cmap='turbo', norm=mcolors.LogNorm())
    ax1.set_ylabel("Range Intensity (m)")
    ax1.set_ylim(0, 10)
    ax1.set_title("Range Intensity Heatmap (Top) vs Range Scatter (Bottom)")

    for i in range(len(range_frames)):
        if len(range_frames[i]) > 0:
            ax2.scatter(np.ones(len(range_frames[i])) * time_axis[i], range_frames[i], s=5, color='tab:orange')
    ax2.set_ylabel("Range Scatter (m)")
    ax2.set_xlabel("Time (s)")
    ax2.set_ylim(0, 10)

    plt.tight_layout()
    _save_or_show(save_path)

# --------------------------------------------------
# UPDATED CONVENIENCE SAVER
# --------------------------------------------------

def save_all_comparison_plots(output_dir, base_name, all_times, all_velocities, all_ranges,
                              all_azimuths, all_elevations, all_snrs,
                              time_axis, range_frames):
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    def _path(idx, desc): return os.path.join(output_dir, f"COMPARE_{idx:02d}_{desc}.png")

    plot_compare_velocity_range(all_times, all_velocities, time_axis, range_frames, save_path=_path(1, "vel_vs_range"))
    plot_compare_snr_range(all_times, all_snrs, time_axis, range_frames, save_path=_path(2, "snr_vs_range"))
    plot_compare_micro_doppler_range(all_times, all_velocities, time_axis, range_frames, save_path=_path(3, "microDoppler_vs_range"))
    plot_compare_azimuth_range(all_times, all_azimuths, time_axis, range_frames, save_path=_path(4, "azimuth_vs_range"))
    plot_compare_elevation_range(all_times, all_elevations, time_axis, range_frames, save_path=_path(5, "elevation_vs_range"))
    plot_compare_rti_range(all_times, all_ranges, time_axis, range_frames, save_path=_path(6, "rti_vs_range"))

# --------------------------------------------------
# CONVENIENCE: SAVE ALL STANDARD PLOTS
# --------------------------------------------------

def save_all_plots(output_dir, base_name,
                   all_times, all_velocities, all_ranges,
                   all_azimuths, all_elevations, all_snrs,
                   time_axis, range_frames, frames_points, frames_velocity):
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    def _path(idx, desc): return os.path.join(output_dir, f"{idx:02d}_{desc}.png")

    plot_range_time_intensity(all_times, all_ranges, save_path=_path(1, "range_time_intensity"))
    plot_micro_doppler_high_fidelity(all_times, all_velocities, save_path=_path(2, "micro_doppler_high_fidelity"))
    plot_range_vs_time_scatter(time_axis, range_frames, save_path=_path(3, "range_vs_time_scatter"))
    plot_velocity_vs_time_scatter(all_times, all_velocities, save_path=_path(4, "velocity_vs_time_scatter"))
    plot_angle_time_intensity(all_times, all_azimuths, "Azimuth vs Time", "Azimuth (deg)", save_path=_path(5, "azimuth_vs_time"))
    plot_angle_time_intensity(all_times, all_elevations, "Elevation vs Time", "Elevation (deg)", save_path=_path(6, "elevation_vs_time"))
    plot_snr_vs_time_scatter(all_times, all_snrs, save_path=_path(7, "snr_vs_time"))
# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":
    # Ensure Windows compatibility with multiprocessing
    multiprocessing.freeze_support()
    
    dat_file = r"C:\Users\c1op3\Downloads\xwr68xx_AOP_processed_stream_2026_02_26T06_17_54_793.dat"
    dat_file = r"C:\Users\c1op3\Desktop\Occupations\Engineering Career\Ms_EEE\EEE_500\repo\mmwave_sensing_toolkit\run_2026-04-01_20-20-16\raw\run_2026-04-01_20-20-16.dat"
    
    # 1. Parse File in Parallel
    start_time = time.time()
    frames_points, frames_velocity, frames_azimuth, frames_elevation, frames_snr, frames_cycles = parse_dat_file_parallel(dat_file)
    print(f"Parsing Time: {time.time() - start_time:.2f} seconds")

    # 2. Compute Hardware Timestamps (Unwrapping the 32-bit roll over)
    time_axis = unwrap_hardware_time(frames_cycles)
    normalized_time, range_frames = compute_range_frames(time_axis, frames_points)
    
    # 3. Flatten all data
    (all_times, all_velocities, all_ranges, 
     all_azimuths, all_elevations, all_snrs) = flatten_data(
         normalized_time, frames_points, frames_velocity, 
         frames_azimuth, frames_elevation, frames_snr
    )

    # 4. Setup Output Directory
    timestamp_str = datetime.now().strftime("%Y_%m_%d_T%H_%M_%S")
    base_name = os.path.basename(dat_file).replace('.dat', '')
    save_dir = os.path.join(os.path.dirname(dat_file), f"Plots_{base_name}_{timestamp_str}")
    os.makedirs(save_dir, exist_ok=True)
    print(f"Saving output plots to: {save_dir}")

    # 5. Generate and Save Plots
    plot_range_vs_time_scatter(normalized_time, range_frames, save_path=os.path.join(save_dir, "range_vs_time.png"))
    plot_velocity_vs_time_scatter(all_times, all_velocities, save_path=os.path.join(save_dir, "velocity_vs_time.png"))
    plot_micro_doppler_high_fidelity(all_times, all_velocities, save_path=os.path.join(save_dir, "micro_doppler.png"))
    plot_range_time_intensity(all_times, all_ranges, save_path=os.path.join(save_dir, "rti.png"))
    plot_angle_time_intensity(all_times, all_azimuths, "Azimuth vs Time", "Azimuth (deg)", save_path=os.path.join(save_dir, "azimuth.png"))
    plot_angle_time_intensity(all_times, all_elevations, "Elevation vs Time", "Elevation (deg)", save_path=os.path.join(save_dir, "elevation.png"))
    plot_snr_vs_time_scatter(all_times, all_snrs, save_path=os.path.join(save_dir, "snr.png"))

    plot_compare_velocity_range(all_times, all_velocities, normalized_time, range_frames, save_path=os.path.join(save_dir, "comp_vel_range.png"))
    plot_compare_snr_range(all_times, all_snrs, normalized_time, range_frames, save_path=os.path.join(save_dir, "comp_snr_range.png"))
    plot_compare_micro_doppler_range(all_times, all_velocities, normalized_time, range_frames, save_path=os.path.join(save_dir, "comp_md_range.png"))
    plot_compare_azimuth_range(all_times, all_azimuths, normalized_time, range_frames, save_path=os.path.join(save_dir, "comp_az_range.png"))
    plot_compare_elevation_range(all_times, all_elevations, normalized_time, range_frames, save_path=os.path.join(save_dir, "comp_el_range.png"))
    plot_compare_rti_range(all_times, all_ranges, normalized_time, range_frames, save_path=os.path.join(save_dir, "comp_rti_range.png"))
    
    print("All plots generated and saved successfully.")