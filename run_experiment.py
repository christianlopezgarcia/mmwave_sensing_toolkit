"""
run_experiment.py
-----------------
Full experiment pipeline: record → parse → save plots.

Usage
-----
    python run_experiment.py

The script records live radar data, parses the resulting .dat file, and
saves all standard plots alongside the .dat file in the experiment folder.
No interactive windows are opened.
"""

import os

import record_radar
record_radar.EXPERIMENT_NAME = "walk_up_and_down"

from dat_parser_plots import (
    parse_dat_file,
    compute_range_frames,
    flatten_data,
    save_all_plots,
)


# --------------------------------------------------
# PIPELINE
# --------------------------------------------------

def run_experiment():
    """
    Execute the full record → parse → plot pipeline.

    Returns
    -------
    str
        Path to the experiment output directory where plots were saved.
    """

    # 1. Record and retrieve .dat file path
    dat_file = record_radar.record_dat_file()

    # 2. Determine output directory from the .dat file location
    output_dir = os.path.dirname(dat_file)
    base_name  = os.path.splitext(os.path.basename(dat_file))[0]

    # 3. Parse (Updated to catch all 5 arrays)
    (frames_points, frames_velocity, 
     frames_azimuth, frames_elevation, frames_snr) = parse_dat_file(dat_file)

    # 4. Compute derived data structures
    time_axis, range_frames = compute_range_frames(frames_points)

    # Flatten all data (Updated to handle Azimuth, Elevation, and SNR)
    (all_times, all_velocities, all_ranges, 
     all_azimuths, all_elevations, all_snrs) = flatten_data(
        time_axis,
        frames_points,
        frames_velocity,
        frames_azimuth,
        frames_elevation,
        frames_snr
    )

    # 5. Save all plots to the experiment folder (Updated with new parameters)
    save_all_plots(
        output_dir      = output_dir,
        base_name       = base_name,
        all_times       = all_times,
        all_velocities  = all_velocities,
        all_ranges      = all_ranges,
        all_azimuths    = all_azimuths,
        all_elevations  = all_elevations,
        all_snrs        = all_snrs,
        time_axis       = time_axis,
        range_frames    = range_frames,
        frames_points   = frames_points,   
        frames_velocity = frames_velocity  
    )

    print("Experiment complete. Outputs saved to:", output_dir)
    return output_dir


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":
    run_experiment()