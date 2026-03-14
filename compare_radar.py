import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from scipy.spatial import KDTree
from datetime import datetime

from dat_parser_plots import (
    parse_dat_file,
    compute_range_frames,
    find_latest_dat_file,
    flatten_data,
    save_all_plots
)

# --------------------------------------------------
# 1. SETTINGS
# --------------------------------------------------

BACKGROUND_PATH = r"repo\mmwave_sensing_toolkit\dat_directory\20260313_181539_do_nothing"
SIGNAL_PATH     = r"repo\mmwave_sensing_toolkit\dat_directory\20260313_181607_walk_up_and_down"

EXPERIMENT_NAME = "cleanup_test_01"
THRESHOLD_M = 0.25


# --------------------------------------------------
# 2. PLOTTING UTILITIES
# --------------------------------------------------

def plot_rti_ax(ax, time_axis, range_frames, title):
    """
    Range vs Time scatter identical to original
    plot_range_vs_time_scatter implementation
    """

    for i in range(len(range_frames)):
        if len(range_frames[i]) > 0:
            t = np.ones(len(range_frames[i])) * time_axis[i]
            ax.scatter(t, range_frames[i], s=5)

    ax.set_title(title)
    ax.set_ylabel("Range (m)")
    ax.set_ylim(0, 10)
    ax.grid(True)


def plot_md_ax(ax, t, v, title):
    """
    Micro-Doppler density map
    """

    if len(t) > 0:
        ax.hist2d(
            t,
            v,
            bins=[350,150],
            cmap="turbo",
            norm=mcolors.PowerNorm(gamma=0.4)
        )

    ax.set_title(title)
    ax.set_ylabel("Velocity (m/s)")


def plot_scatter_ax(ax, time_axis, range_frames, title, color):
    """
    Colored range scatter (for matrix comparison)
    """

    for i, rngs in enumerate(range_frames):
        if len(rngs) > 0:
            ax.scatter(
                [time_axis[i]] * len(rngs),
                rngs,
                s=3,
                color=color,
                alpha=0.3
            )

    ax.set_title(title)
    ax.set_ylim(0,10)


# --------------------------------------------------
# 3. DATA PIPELINE
# --------------------------------------------------

def run_comparison():

    # --------------------------------------------------
    # Resolve data paths
    # --------------------------------------------------

    bg_file = BACKGROUND_PATH if BACKGROUND_PATH.endswith(".dat") else find_latest_dat_file(BACKGROUND_PATH)
    sig_file = SIGNAL_PATH if SIGNAL_PATH.endswith(".dat") else find_latest_dat_file(SIGNAL_PATH)

    base_dir = os.path.dirname(os.path.dirname(BACKGROUND_PATH))

    compare_root = os.path.join(base_dir,"dat_compare")
    output_dir = os.path.join(compare_root, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{EXPERIMENT_NAME}")
    os.makedirs(output_dir,exist_ok=True)

    print("Processing Experiment:",EXPERIMENT_NAME)


    # --------------------------------------------------
    # Parse data
    # --------------------------------------------------

    bg_frames,bg_vels = parse_dat_file(bg_file)
    sig_frames,sig_vels = parse_dat_file(sig_file)


    # --------------------------------------------------
    # Build KDTree background model
    # --------------------------------------------------

    all_bg_coords = np.vstack([f for f in bg_frames if f.size > 0])

    bg_tree = KDTree(all_bg_coords)


    # --------------------------------------------------
    # Subtract background
    # --------------------------------------------------

    cln_frames = []
    cln_vels = []

    for i,frame in enumerate(sig_frames):

        if frame.size == 0:
            cln_frames.append(np.empty((0,3)))
            cln_vels.append(np.array([]))
            continue

        dist,_ = bg_tree.query(frame)

        mask = dist > THRESHOLD_M

        cln_frames.append(frame[mask])
        cln_vels.append(sig_vels[i][mask])


    # --------------------------------------------------
    # Compute range structures
    # --------------------------------------------------

    t_sig, r_sig_f = compute_range_frames(sig_frames)
    t_bg , r_bg_f  = compute_range_frames(bg_frames)
    t_cln, r_cln_f = compute_range_frames(cln_frames)


    # Flattened data for density plots
    sig_t,sig_v,sig_r = flatten_data(t_sig,sig_frames,sig_vels)
    bg_t ,bg_v ,bg_r  = flatten_data(t_bg ,bg_frames ,bg_vels)
    cln_t,cln_v,cln_r = flatten_data(t_cln,cln_frames,cln_vels)


    # --------------------------------------------------
    # GRAPH A : Comparison Matrix
    # --------------------------------------------------

    fig,axes = plt.subplots(3,3,figsize=(20,16),sharex="col")

    labels = [
        "1. ORIGINAL SIGNAL",
        "2. BACKGROUND BASELINE",
        "3. SUBTRACTED RESULT"
    ]

    datasets = [

        (t_sig,r_sig_f,sig_t,sig_v,'black'),
        (t_bg ,r_bg_f ,bg_t ,bg_v ,'red'),
        (t_cln,r_cln_f,cln_t,cln_v,'green')

    ]

    for i,(ta,rf,t,v,col) in enumerate(datasets):

        plot_rti_ax(axes[i,0],ta,rf,f"{labels[i]} (Range vs Time)")
        plot_md_ax(axes[i,1],t,v,f"{labels[i]} (Micro-Doppler)")
        plot_scatter_ax(axes[i,2],ta,rf,f"{labels[i]} (Scatter)",col)


    axes[2,0].set_xlabel("Time (s)")
    axes[2,1].set_xlabel("Time (s)")
    axes[2,2].set_xlabel("Time (s)")

    plt.tight_layout()

    plt.savefig(os.path.join(output_dir,"comparison_matrix.png"),dpi=300)

    plt.close()


    # --------------------------------------------------
    # GRAPH B : Final stacked plots
    # --------------------------------------------------

    fig2,(ax_r,ax_v) = plt.subplots(2,1,figsize=(14,10),sharex=True)

    plot_rti_ax(ax_r,t_cln,r_cln_f,"Subtracted Result: Range vs Time")

    plot_md_ax(ax_v,cln_t,cln_v,"Subtracted Result: Velocity vs Time")

    ax_v.set_xlabel("Time (s)")

    plt.tight_layout()

    plt.savefig(os.path.join(output_dir,"compare_3_and_4.png"),dpi=300)

    plt.close()


    # --------------------------------------------------
    # GRAPH C : Save standard plots
    # --------------------------------------------------

    save_all_plots(

        output_dir = output_dir,

        base_name = "subtracted_final",

        all_times = cln_t,
        all_velocities = cln_v,
        all_ranges = cln_r,

        time_axis = t_cln,
        range_frames = r_cln_f,

        frames_points = cln_frames,
        frames_velocity = cln_vels
    )


    print("All files saved to:",output_dir)
    
    with open(os.path.join(output_dir, "experiment_info.txt"), "w") as f:
        f.write(f"Experiment Name: {EXPERIMENT_NAME}\n")
        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Background Folder:\n{BACKGROUND_PATH}\n\n")
        f.write(f"Signal Folder:\n{SIGNAL_PATH}\n\n")
        f.write(f"Threshold Used: {THRESHOLD_M} meters\n")



# --------------------------------------------------
# MAIN
# --------------------------------------------------

if __name__ == "__main__":
    run_comparison()