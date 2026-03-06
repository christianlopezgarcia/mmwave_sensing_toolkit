import os
import time
import glob
import shutil
from datetime import datetime
import seaborn as sns
import numpy as np
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.colors as mcolors

from ti_mmw_official_tool.parser_scripts.parser_mmw_demo import parser_one_mmw_demo_output_packet
from scipy.ndimage import gaussian_filter
# -----------------------------
# CONFIGURATION
# -----------------------------
RECORD_LIVE = True  # True: record from TI Visualizer, False: use latest dat_directory file
EXPERIMENT_NAME = "Thursday_Test1"

DAT_SOURCE_DIR = r"C:\Users\c1op3\Downloads"  # only used if RECORD_LIVE=True
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DAT_DEST_DIR = os.path.join(SCRIPT_DIR, 'dat_directory')
FRAME_PERIOD = 0.1  # seconds, adjust from frameCfg

# Serial ports and platform (for recording)
SERIAL_PORTS = {"comPort_0": "COM6", "comPort_1": "COM5"}
PLATFORM_VALUE = "xWR68xx_AOP"

# Recording parameters
RECORD_DURATION_SEC = 10
FILE_SIZE_MB = 100

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def find_and_move_latest_dat_file(source_dir, destination_root, experiment_name):
    """Find newest .dat file, move to timestamped folder, return path."""
    list_of_files = glob.glob(os.path.join(source_dir, '*.dat'))
    if not list_of_files:
        print(f"No .dat files found in: {source_dir}")
        return None

    latest_file = max(list_of_files, key=os.path.getmtime)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    experiment_folder = os.path.join(destination_root, f"{experiment_name}_{timestamp}")
    os.makedirs(experiment_folder, exist_ok=True)

    filename = os.path.basename(latest_file)
    destination_file = os.path.join(experiment_folder, filename)

    # Avoid overwrite
    base_name, ext = os.path.splitext(filename)
    counter = 1
    while os.path.exists(destination_file):
        destination_file = os.path.join(experiment_folder, f"{base_name}_{counter}{ext}")
        counter += 1

    shutil.move(latest_file, destination_file)
    print(f"File moved to: {destination_file}")
    return destination_file

def parse_dat_file(dat_file):
    """Parse all frames from .dat file into points and velocities."""
    with open(dat_file, 'rb') as fp:
        allBinData = fp.read()
    readNumBytes = len(allBinData)

    totalBytesParsed = 0
    frames_points, frames_velocity = [], []
    numFramesParsed = 0

    while totalBytesParsed < readNumBytes:
        parser_result, headerStartIndex, totalPacketNumBytes, numDetObj, numTlv, subFrameNumber, \
        detectedX_array, detectedY_array, detectedZ_array, detectedV_array, detectedRange_array, \
        detectedAzimuth_array, detectedElevation_array, detectedSNR_array, detectedNoise_array = parser_one_mmw_demo_output_packet(
            allBinData[totalBytesParsed:], readNumBytes - totalBytesParsed)

        if parser_result != 0:
            break

        totalBytesParsed += (headerStartIndex + totalPacketNumBytes)
        numFramesParsed += 1

        if numDetObj > 0:
            points = np.column_stack((detectedX_array[:numDetObj],
                                      detectedY_array[:numDetObj],
                                      detectedZ_array[:numDetObj]))
            velocities = np.array(detectedV_array[:numDetObj])
            frames_points.append(points)
            frames_velocity.append(velocities)
        else:
            frames_points.append(np.empty((0,3)))
            frames_velocity.append(np.array([]))

    print("Total frames parsed:", numFramesParsed)
    return frames_points, frames_velocity

def compute_range_frames(frames_points, frame_period):
    """Compute ranges and time axis for all frames."""
    time_axis, range_frames = [], []
    for i, points in enumerate(frames_points):
        current_time = i * frame_period
        time_axis.append(current_time)
        if len(points) > 0:
            ranges = np.sqrt(points[:,0]**2 + points[:,1]**2 + points[:,2]**2)
            range_frames.append(ranges)
        else:
            range_frames.append(np.array([]))
    return np.array(time_axis), range_frames

# -----------------------------
# RECORDING LOGIC (if RECORD_LIVE)
# -----------------------------
if RECORD_LIVE:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager

    print("Recording live data from TI Visualizer...")

    # Chrome setup
    options = webdriver.ChromeOptions()
    options.add_argument(r"--user-data-dir=C:\SeleniumTIProfile")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 15)

    try:
        driver.get("https://dev.ti.com/gallery/view/mmwave/mmWave_Demo_Visualizer/ver/3.6.0/")
        time.sleep(12)

        # Handle modals
        try: wait.until(EC.element_to_be_clickable((By.ID, "consent_prompt_submit"))).click()
        except: pass
        try: wait.until(EC.element_to_be_clickable((By.XPATH, "//paper-button[contains(text(),'CLOSE')] | //button[contains(text(),'CLOSE')]"))).click()
        except: pass

        # Set platform
        driver.execute_script("""
            var element = document.getElementById(arguments[0]);
            element.selectedValue = arguments[1];
            element.dispatchEvent(new Event('change'));
        """, "ti_widget_droplist_platform", PLATFORM_VALUE)
        time.sleep(2)

        # Configure serial ports
        options_menu = wait.until(EC.presence_of_element_located((By.XPATH, "//span[contains(text(),'Options')]")))
        driver.execute_script("arguments[0].click();", options_menu)
        serial_item = wait.until(EC.presence_of_element_located((By.XPATH, "//li[.//td[contains(text(),'Serial Port')]]")))
        driver.execute_script("arguments[0].click();", serial_item)
        time.sleep(5)

        for widget_id, port_name in SERIAL_PORTS.items():
            success = False
            for _ in range(10):
                res = driver.execute_script("""
                    var widget = document.getElementById(arguments[0]);
                    if (!widget) return "missing";
                    var options = widget.querySelectorAll('option');
                    for (var i = 0; i < options.length; i++) {
                        if (options[i].textContent.includes(arguments[1])) {
                            widget.selectedValue = options[i].value;
                            widget.dispatchEvent(new CustomEvent('selected-value-changed'));
                            widget.dispatchEvent(new Event('change', { bubbles: true }));
                            return "ok";
                        }
                    }
                    return "loading";
                """, widget_id, port_name)
                if res == "ok": success=True; break
                time.sleep(1)
            if not success: print(f"✗ Failed to set {port_name}")

        # Confirm
        driver.execute_script("arguments[0].click();", wait.until(EC.presence_of_element_located((By.ID, "btnOK"))))
        time.sleep(3)

        # Send config
        send_xpath = "//paper-button[contains(.,'Send Config')] | //paper-material[contains(.,'Send Config')]"
        driver.execute_script("arguments[0].click();", wait.until(EC.element_to_be_clickable((By.XPATH, send_xpath))))
        time.sleep(5)

        # Switch to Plots tab
        plots_tab_xpath = "//paper-tab[@id='tab_1'] | //paper-tab[contains(., 'Plots')]"
        driver.execute_script("arguments[0].click();", wait.until(EC.presence_of_element_located((By.XPATH, plots_tab_xpath))))
        time.sleep(3)

        # Configure recording
        for wid, val in [("ti_widget_textbox_record_time", RECORD_DURATION_SEC),
                         ("ti_widget_textbox_record_file_size_limit", FILE_SIZE_MB)]:
            driver.execute_script("""
                var container = document.getElementById(arguments[0]);
                var input = container.querySelector('input');
                input.value = arguments[1];
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
            """, wid, str(val))
        time.sleep(1)

        # Start recording
        record_btn_id = "ti_widget_button_record"
        driver.execute_script("arguments[0].click();", wait.until(EC.element_to_be_clickable((By.ID, record_btn_id))))
        print("Recording started...")
        time.sleep(RECORD_DURATION_SEC)
        driver.execute_script("arguments[0].click();", wait.until(EC.element_to_be_clickable((By.ID, record_btn_id))))
        print("Recording stopped.")

    finally:
        driver.quit()

# -----------------------------
# DATA FILE SELECTION
# -----------------------------
if RECORD_LIVE:
    dat_file = find_and_move_latest_dat_file(DAT_SOURCE_DIR, DAT_DEST_DIR, EXPERIMENT_NAME)
    if not dat_file: raise FileNotFoundError("No .dat file found after recording.")
else:
    # Grab latest .dat file from dat_directory
    experiment_folders = sorted(
        [os.path.join(DAT_DEST_DIR, d) for d in os.listdir(DAT_DEST_DIR)
         if os.path.isdir(os.path.join(DAT_DEST_DIR, d))],
        key=os.path.getmtime, reverse=True
    )
    if not experiment_folders: raise FileNotFoundError("No experiment folders in dat_directory.")
    latest_folder = experiment_folders[0]
    dat_files = glob.glob(os.path.join(latest_folder, '*.dat'))
    if not dat_files: raise FileNotFoundError(f"No .dat files in latest folder: {latest_folder}")
    dat_file = max(dat_files, key=os.path.getmtime)
    print(f"Using latest .dat file: {dat_file}")

# -----------------------------
# PARSE AND PROCESS DATA
# -----------------------------
frames_points, frames_velocity = parse_dat_file(dat_file)
time_axis, range_frames = compute_range_frames(frames_points, FRAME_PERIOD)

# -----------------------------
# PLOTTING FUNCTIONS
# -----------------------------
def plot_3d_animation(frames_points, frames_velocity):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.set_xlim(-5,5); ax.set_ylim(0,10); ax.set_zlim(-3,3)
    ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)"); ax.set_zlabel("Z (m)")

    def update(frame_idx):
        ax.cla()
        points = frames_points[frame_idx]
        velocities = frames_velocity[frame_idx]
        ax.set_xlim(-5,5); ax.set_ylim(0,10); ax.set_zlim(-3,3)
        ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)"); ax.set_zlabel("Z (m)")
        ax.set_title(f"Frame {frame_idx}")
        if len(points) > 0: ax.scatter(points[:,0], points[:,1], points[:,2], c=velocities, cmap='jet')
        return []

    ani = FuncAnimation(fig, update, frames=len(frames_points), interval=50)
    plt.show()

def plot_range_vs_time(time_axis, range_frames):
    # Static
    plt.figure()
    for i, rngs in enumerate(range_frames):
        if len(rngs) > 0: plt.scatter([time_axis[i]]*len(rngs), rngs, s=5)
    plt.xlabel("Time (s)"); plt.ylabel("Range (m)"); plt.title("Range vs Time"); plt.grid(True)
    plt.show()

    # Animated
    fig2, ax2 = plt.subplots()
    all_times, all_ranges = [], []
    ax2.set_xlim(0, time_axis[-1]); ax2.set_ylim(0,10)
    ax2.set_xlabel("Time (s)"); ax2.set_ylabel("Range (m)"); ax2.set_title("Range vs Time Animation")

    def update(frame_idx):
        rngs = range_frames[frame_idx]
        if len(rngs) > 0:
            t = np.ones(len(rngs)) * time_axis[frame_idx]
            all_times.extend(t)
            all_ranges.extend(rngs)
        ax2.cla()
        ax2.set_xlim(0, time_axis[-1]); ax2.set_ylim(0,10)
        ax2.set_xlabel("Time (s)"); ax2.set_ylabel("Range (m)"); ax2.set_title("Range vs Time Animation")
        ax2.scatter(all_times, all_ranges, s=5)

    ani2 = FuncAnimation(fig2, update, frames=len(range_frames), interval=50)
    plt.show()

def plot_velocity(time_axis, frames_points, frames_velocity):
    all_velocities, all_times, all_ranges = [], [], []
    for i, vels in enumerate(frames_velocity):
        if len(vels) > 0:
            t = np.ones(len(vels)) * time_axis[i]
            pts = frames_points[i]
            rngs = np.sqrt(pts[:,0]**2 + pts[:,1]**2 + pts[:,2]**2)
            all_times.extend(t); all_velocities.extend(vels); all_ranges.extend(rngs)

    all_times = np.array(all_times)
    all_velocities = np.array(all_velocities)
    all_ranges = np.array(all_ranges)

    # Doppler scatter
    plt.figure(figsize=(12,6))
    v_max = max(abs(all_velocities.min()), abs(all_velocities.max()), 0.1)
    norm = mcolors.TwoSlopeNorm(vmin=-v_max, vcenter=0, vmax=v_max)
    sc = plt.scatter(all_times, all_velocities, c=all_velocities, cmap='RdBu_r', norm=norm, s=12, alpha=0.7, edgecolors='none')
    plt.colorbar(sc, label="Radial Velocity (m/s)")
    plt.axhline(0, color='black', linestyle='--', linewidth=1, alpha=0.5)
    plt.xlabel("Time (s)"); plt.ylabel("Velocity (m/s)"); plt.title("Doppler Velocity Profile"); plt.grid(True, linestyle=':', alpha=0.6)
    plt.show()

    # Velocity density hexbin
    plt.figure(figsize=(12,6))
    hb = plt.hexbin(all_times, all_velocities, gridsize=(80,40), cmap='magma', mincnt=1)
    plt.colorbar(hb, label='Reflection Density')
    plt.axhline(0, color='white', linestyle='--', linewidth=1, alpha=0.3)
    plt.xlabel("Time (s)"); plt.ylabel("Velocity (m/s)"); plt.title("Doppler Intensity")
    plt.show()

    # Range-Doppler
    plt.figure(figsize=(10,6))
    plt.hist2d(all_ranges, all_velocities, bins=[50,50], cmap='viridis', cmin=1)
    plt.colorbar(label='Point Count')
    plt.xlabel("Range (m)"); plt.ylabel("Velocity (m/s)"); plt.title("Range-Doppler Distribution"); plt.grid(alpha=0.2)
    plt.show()

    # Statistical trends
    avg_velocity = [np.mean(v) if len(v)>0 else 0 for v in frames_velocity]
    max_velocity = [np.max(v) if len(v)>0 else 0 for v in frames_velocity]
    min_velocity = [np.min(v) if len(v)>0 else 0 for v in frames_velocity]

    plt.figure(figsize=(12,5))
    plt.plot(time_axis, avg_velocity, label='Average Velocity', color='green', alpha=0.8)
    plt.fill_between(time_axis, min_velocity, max_velocity, color='gray', alpha=0.2, label='Velocity Spread')
    plt.axhline(0, color='black', lw=1)
    plt.xlabel("Time (s)"); plt.ylabel("Velocity (m/s)"); plt.title("Velocity Dynamics Over Time"); plt.legend(loc='upper right'); plt.grid(True, alpha=0.3)
    plt.show()

def plot_velocity_enhanced(time_axis, frames_points, frames_velocity):
    """
    Improved velocity visualization for Doppler-based identification.
    Includes:
    1. Scatter velocity vs time (colored by velocity)
    2. Range-Doppler heatmap
    3. Smoothed velocity vs time (KDE)
    """
    all_times, all_velocities, all_ranges = [], [], []

    # Aggregate all points
    for i, vels in enumerate(frames_velocity):
        if len(vels) > 0:
            t = np.ones(len(vels)) * time_axis[i]
            pts = frames_points[i]
            rngs = np.sqrt(pts[:,0]**2 + pts[:,1]**2 + pts[:,2]**2)
            all_times.extend(t)
            all_velocities.extend(vels)
            all_ranges.extend(rngs)

    all_times = np.array(all_times)
    all_velocities = np.array(all_velocities)
    all_ranges = np.array(all_ranges)

    # -----------------------------
    # 1️⃣ Doppler Scatter (Velocity vs Time)
    # -----------------------------
    plt.figure(figsize=(12,6))
    v_max = max(abs(all_velocities.min()), abs(all_velocities.max()), 0.1)
    norm = mcolors.TwoSlopeNorm(vmin=-v_max, vcenter=0, vmax=v_max)
    plt.scatter(all_times, all_velocities, c=all_velocities, cmap='RdBu_r', norm=norm,
                s=12, alpha=0.7, edgecolors='none')
    plt.colorbar(label="Radial Velocity (m/s)\n(-) Away | (+) Approaching")
    plt.axhline(0, color='black', linestyle='--', linewidth=1, alpha=0.5)
    plt.xlabel("Time (s)"); plt.ylabel("Velocity (m/s)")
    plt.title("Doppler Velocity Profile")
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.show()

    # -----------------------------
    # 2️⃣ Range-Doppler Heatmap
    # -----------------------------
    plt.figure(figsize=(12,6))
    bins_range = np.linspace(0, 10, 120)        # fine range bins
    bins_velocity = np.linspace(-3, 3, 120)     # fine velocity bins
    H, xedges, yedges = np.histogram2d(all_ranges, all_velocities,
                                       bins=[bins_range, bins_velocity])
    H = H.T  # transpose for correct orientation
    plt.imshow(H, extent=[bins_range[0], bins_range[-1], bins_velocity[0], bins_velocity[-1]],
               origin='lower', aspect='auto', cmap='magma', interpolation='nearest')
    plt.colorbar(label='Reflection Density')
    plt.xlabel("Range (m)"); plt.ylabel("Velocity (m/s)")
    plt.title("Enhanced Range-Doppler Signature")
    plt.show()

    # -----------------------------
    # 3️⃣ Smoothed Velocity (KDE)
    # -----------------------------
    plt.figure(figsize=(12,6))
    sns.kdeplot(x=all_times, y=all_velocities, fill=True, cmap='viridis', bw_adjust=0.3)
    plt.xlabel("Time (s)"); plt.ylabel("Radial Velocity (m/s)")
    plt.title("Smoothed Velocity Profile (KDE)")
    plt.grid(True, alpha=0.3)
    plt.show()
def plot_micro_doppler_signature(time_axis, frames_velocity, frames_points):
    """
    New method to replicate professional Micro-Doppler (VT) 
    and Range-Time (RT) intensity plots.
    """
    all_times = []
    all_vels = []
    all_ranges = []
    
    # Flatten data for density plotting
    for i, vels in enumerate(frames_velocity):
        if len(vels) > 0:
            pts = frames_points[i]
            rngs = np.sqrt(pts[:,0]**2 + pts[:,1]**2 + pts[:,2]**2)
            
            all_times.extend([time_axis[i]] * len(vels))
            all_vels.extend(vels)
            all_ranges.extend(rngs)

    # Convert to numpy arrays
    all_times = np.array(all_times)
    all_vels = np.array(all_vels)
    all_ranges = np.array(all_ranges)

    # --- Plot A: Micro-Doppler (Velocity vs Time) ---
    plt.figure(figsize=(12, 5))
    # Using 'turbo' and PowerNorm to highlight subtle arm/leg movements
    plt.hist2d(all_times, all_vels, bins=[350, 150], cmap='turbo', 
               norm=mcolors.PowerNorm(gamma=0.4))
    plt.colorbar(label='Reflection Density')
    plt.title("High-Fidelity Micro-Doppler Signature (VT)")
    plt.xlabel("Time (s)")
    plt.ylabel("Velocity (m/s)")
    plt.grid(alpha=0.2)
    plt.show()

    # --- Plot B: Range-Time Intensity (RT) ---
    plt.figure(figsize=(12, 5))
    # LogNorm mimics the dB signal strength of the reference images
    plt.hist2d(all_times, all_ranges, bins=[350, 200], cmap='turbo', 
               norm=mcolors.LogNorm())
    plt.colorbar(label='Signal Intensity')
    plt.title("Range-Time Intensity Profile (RT)")
    plt.xlabel("Time (s)")
    plt.ylabel("Range (m)")
    plt.ylim(0, 10) # Adjust based on your environment
    plt.show()

def plot_micro_doppler_signature_2(time_axis, frames_velocity, frames_points):
    """
    Enhanced method to replicate professional radar signatures with smooth gradients.
    """
    all_times, all_vels, all_ranges = [], [], []
    
    for i, vels in enumerate(frames_velocity):
        if len(vels) > 0:
            pts = frames_points[i]
            rngs = np.sqrt(pts[:,0]**2 + pts[:,1]**2 + pts[:,2]**2)
            all_times.extend([time_axis[i]] * len(vels))
            all_vels.extend(vels)
            all_ranges.extend(rngs)

    all_times = np.array(all_times)
    all_vels = np.array(all_vels)
    all_ranges = np.array(all_ranges)

    # --- 1. Smoothed Micro-Doppler (VT) ---
    plt.figure(figsize=(12, 5))
    # Higher bin count (500) creates the detailed vertical spikes seen in walking
    h_vt, x_vt, y_vt = np.histogram2d(all_times, all_vels, bins=[500, 150])
    # Apply Gaussian smoothing to create the 'glowing' gradient
    h_vt = gaussian_filter(h_vt, sigma=1.2) 
    
    plt.imshow(h_vt.T, origin='lower', aspect='auto', 
               extent=[x_vt[0], x_vt[-1], y_vt[0], y_vt[-1]], 
               cmap='turbo', norm=mcolors.PowerNorm(gamma=0.5))
    plt.title("Gradient Micro-Doppler Signature (VT)")
    plt.xlabel("Time (s)"); plt.ylabel("Velocity (m/s)")
    plt.colorbar(label='Intensity (dB-like)')
    plt.show()

    # --- 2. Smoothed Range-Time (RT) ---
    plt.figure(figsize=(12, 5))
    h_rt, x_rt, y_rt = np.histogram2d(all_times, all_ranges, bins=[500, 200])
    h_rt = gaussian_filter(h_rt, sigma=1.0)
    
    plt.imshow(h_rt.T, origin='lower', aspect='auto', 
               extent=[x_rt[0], x_rt[-1], y_rt[0], y_rt[-1]], 
               cmap='turbo', norm=mcolors.LogNorm())
    plt.title("Gradient Range-Time Intensity (RT)")
    plt.xlabel("Time (s)"); plt.ylabel("Range (m)")
    plt.ylim(0, 8) 
    plt.colorbar(label='Intensity')
    plt.show()
def plot_gradient_spectrograms(time_axis, frames_velocity, frames_points):
    """
    Generates smooth, glowing spectrograms mimicking raw radar heatmaps.
    """
    all_times, all_vels, all_ranges = [], [], []
    
    for i, vels in enumerate(frames_velocity):
        if len(vels) > 0:
            pts = frames_points[i]
            rngs = np.sqrt(pts[:,0]**2 + pts[:,1]**2 + pts[:,2]**2)
            all_times.extend([time_axis[i]] * len(vels))
            all_vels.extend(vels)
            all_ranges.extend(rngs)

    # 1. Gradient Micro-Doppler (Velocity vs Time)
    plt.figure(figsize=(12, 6))
    # Higher binning creates the 'resolution' for the gradient
    h_v, x_v, y_v = np.histogram2d(all_times, all_vels, bins=[600, 200])
    # Sigma controls the 'glow' / smoothness. 1.5 is a sweet spot for 10Hz data.
    h_v_smooth = gaussian_filter(h_v, sigma=1.5)
    
    plt.imshow(h_v_smooth.T, origin='lower', aspect='auto', 
               extent=[x_v[0], x_v[-1], y_v[0], y_v[-1]], 
               cmap='turbo', norm=mcolors.PowerNorm(gamma=0.4))
    plt.title("Gradient Micro-Doppler Signature (VT Profile)")
    plt.xlabel("Time (s)"); plt.ylabel("Velocity (m/s)")
    plt.colorbar(label='Signal Density')
    plt.show()

    # 2. Gradient Range-Time (Range vs Time)
    plt.figure(figsize=(12, 6))
    h_r, x_r, y_r = np.histogram2d(all_times, all_ranges, bins=[600, 250])
    h_r_smooth = gaussian_filter(h_r, sigma=1.2)
    
    plt.imshow(h_r_smooth.T, origin='lower', aspect='auto', 
               extent=[x_r[0], x_r[-1], y_r[0], y_r[-1]], 
               cmap='turbo', norm=mcolors.LogNorm())
    plt.title("Gradient Range-Time Intensity (RT Profile)")
    plt.xlabel("Time (s)"); plt.ylabel("Range (m)")
    plt.ylim(0, 8) 
    plt.colorbar(label='Intensity')
    plt.show()
# -----------------------------
# RUN PLOTS
# -----------------------------
plot_3d_animation(frames_points, frames_velocity)
plot_range_vs_time(time_axis, range_frames)
plot_velocity(time_axis, frames_points, frames_velocity)
# plot_velocity_enhanced(time_axis, frames_points, frames_velocity)
# --- NEW PROFESSIONAL PLOTS ---
print("Generating high-fidelity signatures...")
plot_micro_doppler_signature(time_axis, frames_velocity, frames_points)
# plot_micro_doppler_signature_2(time_axis, frames_velocity, frames_points)
# plot_gradient_spectrograms(time_axis, frames_velocity, frames_points)