import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from scipy.spatial import KDTree

# Import existing functions from your module
from dat_parser_plots import (
    parse_dat_file, 
    compute_range_frames, 
    find_latest_dat_file, 
    flatten_data
)

# --------------------------------------------------
# 1. CONFIGURATION
# --------------------------------------------------
BACKGROUND_PATH = r"repo\mmwave_sensing_toolkit\dat_directory\20260313_181539_do_nothing"
SIGNAL_PATH     = r"repo\mmwave_sensing_toolkit\dat_directory\20260313_181607_walk_up_and_down"

EXPERIMENT_NAME = "cleanup_full_01"
THRESHOLD_M     = 0.30  # Adjust this if "removed" row is too empty

# --------------------------------------------------
# 2. PLOTTING HELPERS
# --------------------------------------------------
def plot_rti_ax(ax, t, r, title):
    if len(t) > 0:
        ax.hist2d(t, r, bins=[250, 150], cmap='turbo', norm=mcolors.LogNorm())
    ax.set_title(title)
    ax.set_ylim(0, 10)

def plot_md_ax(ax, t, v, title):
    if len(t) > 0:
        ax.hist2d(t, v, bins=[250, 150], cmap='turbo', norm=mcolors.PowerNorm(gamma=0.4))
    ax.set_title(title)

def plot_scatter_ax(ax, time_axis, range_frames, title, color):
    for i, rngs in enumerate(range_frames):
        if len(rngs) > 0:
            ax.scatter([time_axis[i]]*len(rngs), rngs, s=2, color=color, alpha=0.3)
    ax.set_title(title)
    ax.set_ylim(0, 10)

def get_dat_path(path):
    if os.path.isfile(path) and path.endswith('.dat'): return path
    if os.path.isdir(path): return find_latest_dat_file(path)
    raise FileNotFoundError(f"No .dat found at: {path}")

# --------------------------------------------------
# 3. MAIN EXECUTION
# --------------------------------------------------
bg_file = get_dat_path(BACKGROUND_PATH)
sig_file = get_dat_path(SIGNAL_PATH)

print("Parsing files...")
bg_frames, bg_vel_frames = parse_dat_file(bg_file)
sig_frames, sig_vel_frames = parse_dat_file(sig_file)

# Aggregate background points for the spatial filter
all_bg_coords = np.vstack([f for f in bg_frames if f.size > 0])
bg_tree = KDTree(all_bg_coords)

# Filter Signal
cleaned_frames, removed_frames = [], []
cleaned_vels, removed_vels = [], []

for i, frame in enumerate(sig_frames):
    if frame.size == 0:
        cleaned_frames.append(np.empty((0,3))); removed_frames.append(np.empty((0,3)))
        cleaned_vels.append(np.array([])); removed_vels.append(np.array([]))
        continue
    
    dist, _ = bg_tree.query(frame)
    mask = dist > THRESHOLD_M
    
    cleaned_frames.append(frame[mask])
    removed_frames.append(frame[~mask])
    cleaned_vels.append(sig_vel_frames[i][mask])
    removed_vels.append(sig_vel_frames[i][~mask])

# Prepare Plotting Data
t_axis, sig_r_frames = compute_range_frames(sig_frames)
_, clean_r_frames = compute_range_frames(cleaned_frames)
_, removed_r_frames = compute_range_frames(removed_frames)

sig_t, sig_v, sig_r = flatten_data(t_axis, sig_frames, sig_vel_frames)
clean_t, clean_v, clean_r = flatten_data(t_axis, cleaned_frames, cleaned_vels)
removed_t, removed_v, removed_r = flatten_data(t_axis, removed_frames, removed_vels)

# --- GENERATE MATRIX ---
fig, axes = plt.subplots(3, 3, figsize=(20, 15), sharex='col')

# Labels
cols = ["Range-Time Intensity", "Micro-Doppler (VT)", "Range Scatter"]
rows = ["1. ORIGINAL", "2. BACKGROUND (REMOVED)", "3. SUBTRACTED (CLEANED)"]

# Row 1: Original
plot_rti_ax(axes[0,0], sig_t, sig_r, rows[0] + " - " + cols[0])
plot_md_ax(axes[0,1], sig_t, sig_v, rows[0] + " - " + cols[1])
plot_scatter_ax(axes[0,2], t_axis, sig_r_frames, rows[0] + " - " + cols[2], "black")

# Row 2: Noise Removed
plot_rti_ax(axes[1,0], removed_t, removed_r, rows[1] + " - " + cols[0])
plot_md_ax(axes[1,1], removed_t, removed_v, rows[1] + " - " + cols[1])
plot_scatter_ax(axes[1,2], t_axis, removed_r_frames, rows[1] + " - " + cols[2], "red")

# Row 3: Cleaned
plot_rti_ax(axes[2,0], clean_t, clean_r, rows[2] + " - " + cols[0])
plot_md_ax(axes[2,1], clean_t, clean_v, rows[2] + " - " + cols[1])
plot_scatter_ax(axes[2,2], t_axis, clean_r_frames, rows[2] + " - " + cols[2], "green")

# Formatting
for ax in axes[:,0]: ax.set_ylabel("Range (m)")
for ax in axes[:,1]: ax.set_ylabel("Velocity (m/s)")
for ax in axes[2,:]: ax.set_xlabel("Time (s)")

plt.tight_layout()
compare_dir = os.path.join("dat_compare", EXPERIMENT_NAME)
os.makedirs(compare_dir, exist_ok=True)
plt.savefig(os.path.join(compare_dir, "full_comparison_matrix.png"))
print(f"Matrix saved to {compare_dir}")
plt.show()