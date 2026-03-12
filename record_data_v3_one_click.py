import os
import time
import glob
import shutil
import socket
from datetime import datetime

import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d import Axes3D
from scipy.ndimage import gaussian_filter

from ti_mmw_official_tool.parser_scripts.parser_mmw_demo import parser_one_mmw_demo_output_packet


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

RECORD_LIVE = True
EXPERIMENT_NAME = "test2"

DAT_SOURCE_DIR = r"C:\Users\c1op3\Downloads"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DAT_DEST_DIR = os.path.join(SCRIPT_DIR, "dat_directory")

FRAME_PERIOD = 0.1

SERIAL_PORTS = {
    "comPort_0": "COM6",
    "comPort_1": "COM5"
}

PLATFORM_VALUE = "xWR68xx_AOP"

RECORD_DURATION_SEC = 10
FILE_SIZE_MB = 100
DOWNLOAD_BUFFER = 5

DEBUG_PORT = 9222
PROFILE_PATH = r"C:\SeleniumTIProfile"

# --------------------------------------------------
# FILE DETECTION
# --------------------------------------------------

def wait_for_new_dat_file(start_time):

    timeout = RECORD_DURATION_SEC + DOWNLOAD_BUFFER
    deadline = start_time + timeout

    print("Waiting for new .dat file...")

    while time.time() < deadline:

        dat_files = glob.glob(os.path.join(DAT_SOURCE_DIR, "*.dat"))

        for f in dat_files:
            # Added a 2-second buffer for system clock mismatches
            if os.path.getmtime(f) >= (start_time - 2):
                return f

        time.sleep(1)

    return None


def move_dat_file(filepath):

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    experiment_folder = os.path.join(
        DAT_DEST_DIR,
        f"{timestamp}_{EXPERIMENT_NAME}"
    )

    os.makedirs(experiment_folder, exist_ok=True)

    filename = os.path.basename(filepath)
    destination = os.path.join(experiment_folder, filename)

    shutil.move(filepath, destination)

    print("File moved to:", destination)

    return destination


# --------------------------------------------------
# PARSER
# --------------------------------------------------

def parse_dat_file(dat_file):

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

    time_axis = []
    range_frames = []

    for i, points in enumerate(frames_points):
        time_axis.append(i * FRAME_PERIOD)

        if len(points) > 0:
            ranges = np.sqrt(
                points[:,0]**2 +
                points[:,1]**2 +
                points[:,2]**2
            )
            range_frames.append(ranges)
        else:
            range_frames.append(np.array([]))

    return np.array(time_axis), range_frames


def flatten_data(time_axis, frames_points, frames_velocity):

    all_times = []
    all_velocities = []
    all_ranges = []

    for i, vels in enumerate(frames_velocity):
        if len(vels) > 0:
            pts = frames_points[i]
            rngs = np.sqrt(
                pts[:,0]**2 +
                pts[:,1]**2 +
                pts[:,2]**2
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
# RECORDING
# --------------------------------------------------

if RECORD_LIVE:

    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager

    print("Recording live data from TI Visualizer...")

    # Check if browser is already open on our debug port
    browser_is_open = False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(('localhost', DEBUG_PORT)) == 0:
            browser_is_open = True

    options = webdriver.ChromeOptions()

    if browser_is_open:
        print("🔗 Reconnecting to existing browser session...")
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        wait = WebDriverWait(driver, 15)
    else:
        print("🚀 Launching new Chrome session...")
        os.makedirs(PROFILE_PATH, exist_ok=True)
        
        # Combined Clean Profile + Debug Port logic
        options.add_argument(f"--user-data-dir={PROFILE_PATH}")
        options.add_argument(f"--remote-debugging-port={DEBUG_PORT}")
        options.add_argument("--start-maximized")
        options.add_argument("--no-first-run")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_experimental_option("detach", True)

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        wait = WebDriverWait(driver, 15)

        driver.get("https://dev.ti.com/gallery/view/mmwave/mmWave_Demo_Visualizer/ver/3.6.0/")
        time.sleep(12)

    # Handle standard popups
    for xpath in ["//paper-button[text()='ACCEPT']", "//paper-button[contains(text(),'CLOSE')] | //button[contains(text(),'CLOSE')]"]:
        try:
            driver.find_element(By.XPATH, xpath).click()
            time.sleep(1)
        except:
            pass

    # Check if we are already configured
    is_configured = False
    try:
        plots_tab = driver.find_element(By.ID, "tab_1")
        if "iron-selected" in plots_tab.get_attribute("class"):
            is_configured = True
            print("✅ Already on Plots tab. Skipping configuration.")
    except:
        pass

    # Setup hardware only if not already on plots
    if not is_configured:
        print("⚙️ Configuring Hardware...")
        driver.execute_script("""
            var element = document.getElementById(arguments[0]);
            element.selectedValue = arguments[1];
            element.dispatchEvent(new Event('change'));
        """, "ti_widget_droplist_platform", PLATFORM_VALUE)

        time.sleep(2)

        options_menu = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//span[contains(text(),'Options')]")
        ))
        driver.execute_script("arguments[0].click();", options_menu)

        serial_item = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//li[.//td[contains(text(),'Serial Port')]]")
        ))
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
                            widget.dispatchEvent(
                                new CustomEvent('selected-value-changed')
                            );
                            widget.dispatchEvent(
                                new Event('change', { bubbles: true })
                            );
                            return "ok";
                        }
                    }
                    return "loading";
                """, widget_id, port_name)

                if res == "ok":
                    success = True
                    break
                time.sleep(1)

            if not success:
                print("Failed to set", port_name)

        driver.execute_script(
            "arguments[0].click();",
            wait.until(EC.presence_of_element_located((By.ID, "btnOK")))
        )

        time.sleep(3)

        send_xpath = (
            "//paper-button[contains(.,'Send Config')] | "
            "//paper-material[contains(.,'Send Config')]"
        )

        driver.execute_script(
            "arguments[0].click();",
            wait.until(EC.element_to_be_clickable((By.XPATH, send_xpath)))
        )

        time.sleep(5)

        plots_tab_xpath = (
            "//paper-tab[@id='tab_1'] | "
            "//paper-tab[contains(., 'Plots')]"
        )

        driver.execute_script(
            "arguments[0].click();",
            wait.until(EC.presence_of_element_located((By.XPATH, plots_tab_xpath)))
        )
        time.sleep(3)


    # --- RECORDING STEP ---
    for wid, val in [
        ("ti_widget_textbox_record_time", RECORD_DURATION_SEC),
        ("ti_widget_textbox_record_file_size_limit", FILE_SIZE_MB)
    ]:
        driver.execute_script("""
            var container = document.getElementById(arguments[0]);
            var input = container.querySelector('input');
            input.value = arguments[1];
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
        """, wid, str(val))

    record_btn = "ti_widget_button_record"

    record_start_time = time.time()

    driver.execute_script(
        "arguments[0].click();",
        wait.until(EC.element_to_be_clickable((By.ID, record_btn)))
    )

    print("🔴 Recording started")

    time.sleep(RECORD_DURATION_SEC)

    driver.execute_script(
        "arguments[0].click();",
        wait.until(EC.element_to_be_clickable((By.ID, record_btn)))
    )

    print("⏹️ Recording stopped")


# --------------------------------------------------
# FILE HANDLING
# --------------------------------------------------

new_file = wait_for_new_dat_file(record_start_time)

if not new_file:
    raise FileNotFoundError("No new dat file found")

dat_file = move_dat_file(new_file)


# --------------------------------------------------
# PARSE DATA
# --------------------------------------------------

frames_points, frames_velocity = parse_dat_file(dat_file)

time_axis, range_frames = compute_range_frames(frames_points)

all_times, all_velocities, all_ranges = flatten_data(
    time_axis,
    frames_points,
    frames_velocity
)


# --------------------------------------------------
# SAVE PATH
# --------------------------------------------------

output_dir = os.path.dirname(dat_file)
base_name = os.path.splitext(os.path.basename(dat_file))[0]


def save_plot(name):
    path = os.path.join(output_dir, f"{base_name}_{name}.png")
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    print("Saved:", path)


# --------------------------------------------------
# RANGE TIME INTENSITY
# --------------------------------------------------

plt.figure(figsize=(14,5))

h, x, y = np.histogram2d(all_times, all_ranges, bins=[600,250])
h = gaussian_filter(h, sigma=1.2)

plt.imshow(
    h.T,
    origin="lower",
    aspect="auto",
    extent=[x[0], x[-1], y[0], y[-1]],
    cmap="turbo",
    norm=mcolors.LogNorm()
)

plt.xlabel("Time (s)")
plt.ylabel("Range (m)")
plt.title("Range-Time Intensity")
plt.colorbar(label="Intensity")

save_plot("rti")


# --------------------------------------------------
# RANGE VS TIME
# --------------------------------------------------

plt.figure(figsize=(14,5))

for i, rngs in enumerate(range_frames):
    if len(rngs) > 0:
        plt.scatter([time_axis[i]] * len(rngs), rngs, s=5, alpha=0.6)

plt.xlabel("Time (s)")
plt.ylabel("Range (m)")
plt.title("Range vs Time")
plt.grid(True)

save_plot("range_vs_time")


# --------------------------------------------------
# VELOCITY HEXBIN
# --------------------------------------------------

plt.figure(figsize=(14,5))

hb = plt.hexbin(
    all_times,
    all_velocities,
    gridsize=(80,40),
    cmap="magma",
    mincnt=1
)

plt.colorbar(hb, label="Reflection Density")
plt.xlabel("Time (s)")
plt.ylabel("Velocity (m/s)")
plt.title("Velocity Density")

save_plot("velocity_hexbin")


# --------------------------------------------------
# RANGE DOPPLER
# --------------------------------------------------

plt.figure(figsize=(10,6))

plt.hist2d(
    all_ranges,
    all_velocities,
    bins=[50,50],
    cmap="viridis",
    cmin=1
)

plt.colorbar(label="Point Count")
plt.xlabel("Range (m)")
plt.ylabel("Velocity (m/s)")
plt.title("Range-Doppler Distribution")

save_plot("range_doppler")


print("\n✅ Processing complete")