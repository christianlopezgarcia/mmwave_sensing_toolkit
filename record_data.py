import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --------------------------------------------------
# SETUP CHROME
# --------------------------------------------------
options = webdriver.ChromeOptions()
options.add_argument(r"--user-data-dir=C:\SeleniumTIProfile")
options.add_argument("--profile-directory=Default")
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)
wait = WebDriverWait(driver, 15) # Increased global wait for stability

try:
    # 1️⃣ OPEN TI VISUALIZER
    driver.get("https://dev.ti.com/gallery/view/mmwave/mmWave_Demo_Visualizer/ver/3.6.0/")
    print("Waiting for Visualizer to load...")
    time.sleep(12)

    # 2️⃣ CLOSE MODALS
    try:
        cookie_btn = wait.until(EC.element_to_be_clickable((By.ID, "consent_prompt_submit")))
        cookie_btn.click()
        print("✓ Cookie accepted.")
    except:
        print("No cookie modal.")

    try:
        close_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//paper-button[contains(text(),'CLOSE')] | //button[contains(text(),'CLOSE')]")
        ))
        close_btn.click()
        print("✓ Instruction modal closed.")
    except:
        print("No instruction modal.")

    # 3️⃣ SELECT PLATFORM
    platform_id = "ti_widget_droplist_platform"
    wait.until(EC.presence_of_element_located((By.ID, platform_id)))
    driver.execute_script("""
        var element = document.getElementById(arguments[0]);
        element.selectedValue = 'xWR68xx_AOP';
        element.dispatchEvent(new Event('change'));
    """, platform_id)
    print("✓ Platform set to xWR68xx_AOP.")
    time.sleep(2)

    # 4️⃣ CONFIGURE SERIAL PORTS
    # Open Menu
    options_menu = wait.until(EC.presence_of_element_located((By.XPATH, "//span[contains(text(),'Options')]")))
    driver.execute_script("arguments[0].click();", options_menu)
    
    serial_item = wait.until(EC.presence_of_element_located((By.XPATH, "//li[.//td[contains(text(),'Serial Port')]]")))
    driver.execute_script("arguments[0].click();", serial_item)
    print("✓ Serial Port menu opened. Waiting for scan...")
    time.sleep(5)

    # Set COM Ports
    port_config = {"comPort_0": "COM6", "comPort_1": "COM5"}
    for widget_id, port_name in port_config.items():
        success = False
        for attempt in range(10):
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
            if res == "ok":
                print(f"✓ {port_name} set.")
                success = True
                break
            time.sleep(1)
        if not success: print(f"✗ Failed to find {port_name}")

    # Click OK
    ok_btn = wait.until(EC.presence_of_element_located((By.ID, "btnOK")))
    driver.execute_script("arguments[0].click();", ok_btn)
    print("✓ Serial ports confirmed.")
    time.sleep(3)

    # 5️⃣ SEND CONFIG TO DEVICE
    print("Attempting to Send Config...")
    try:
        # Targeting the paper-button or paper-material containing the specific text
        send_config_xpath = "//paper-button[contains(.,'Send Config')] | //paper-material[contains(.,'Send Config')]"
        send_btn = wait.until(EC.element_to_be_clickable((By.XPATH, send_config_xpath)))
        driver.execute_script("arguments[0].click();", send_btn)
        print("✓ Config sent to mmWave device.")
        time.sleep(5) # Vital: give the device time to process the commands
    except Exception as e:
        print(f"✗ Failed to Send Config: {e}")

    # 6️⃣ SWITCH TO PLOTS TAB
    print("Switching to Plots tab...")
    
    # We target the paper-tab by ID 'tab_1' based on your HTML snippet
    # If tab_1 doesn't work, we fallback to finding the tab containing the word 'Plots'
    plots_tab_xpath = "//paper-tab[@id='tab_1'] | //paper-tab[contains(., 'Plots')]"
    
    plots_tab = wait.until(
        EC.presence_of_element_located((By.XPATH, plots_tab_xpath))
    )

    # Use JavaScript click because paper-ripple/paper-material often 
    # blocks standard Selenium click events.
    driver.execute_script("arguments[0].click();", plots_tab)
    
    print("✓ Switched to Plots tab.")
    time.sleep(3) # Give the graphs time to initialize

    # 7️⃣ CONFIGURE RECORDING LIMITS
    print("Setting recording limits...")
    
    # IDs from your HTML
    time_limit_id = "ti_widget_textbox_record_time"
    size_limit_id = "ti_widget_textbox_record_file_size_limit"
    
    # Value targets
    recording_duration_sec = 10
    file_size_mb = 100

    # Helper to set values in TI Textboxes via JS (triggers internal events)
    set_value_script = """
        var container = document.getElementById(arguments[0]);
        var input = container.querySelector('input');
        input.value = arguments[1];
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
    """

    driver.execute_script(set_value_script, time_limit_id, str(recording_duration_sec))
    print(f"✓ Time limit set to {recording_duration_sec}s")
    
    driver.execute_script(set_value_script, size_limit_id, str(file_size_mb))
    print(f"✓ Size limit set to {file_size_mb} MB")
    
    time.sleep(1)

    # 8️⃣ START RECORDING
    record_btn_id = "ti_widget_button_record"
    record_btn = wait.until(EC.element_to_be_clickable((By.ID, record_btn_id)))
    
    # Using JS click to bypass the paper-ripple overlay
    driver.execute_script("arguments[0].click();", record_btn)
    print("▶ Recording STARTED.")

    # 9️⃣ PYTHON TIMER FOR STOPPING
    # We wait for the duration specified
    print(f"Waiting {recording_duration_sec} seconds before stopping...")
    
    # If you want to see a countdown in console:
    for i in range(recording_duration_sec, 0, -1):
        if i % 10 == 0: # Print every 10 seconds to avoid spam
            print(f"Time remaining: {i}s", end="\r")
        time.sleep(1)

    # 🔟 STOP RECORDING
    # The button text changes to 'Record Stop' but the ID remains the same
    print("\nAttempting to Stop Recording...")
    stop_btn = wait.until(EC.element_to_be_clickable((By.ID, record_btn_id)))
    driver.execute_script("arguments[0].click();", stop_btn)
    print("■ Recording STOPPED.")
    time.sleep(5)

except Exception as e:
    print(f"General script failure: {e}")

finally:
    print("Script complete. Browser remains open for recording.")
    driver.quit() # Uncomment if you want it to close automatically


import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d import Axes3D

from ti_mmw_official_tool.parser_scripts.parser_mmw_demo import parser_one_mmw_demo_output_packet

###############################################################################
# FIND LATEST .DAT FILE + MOVE TO EXPERIMENT FOLDER (SAFE)
###############################################################################

import glob
import shutil
from datetime import datetime
import os

def find_and_move_latest_dat_file(source_dir, destination_root, experiment_name):
    """
    1. Finds newest .dat file in source_dir
    2. Creates experiment subdirectory in destination_root
    3. Moves file safely (no overwrite)
    4. Returns new file path
    """

    # Search for .dat files
    search_pattern = os.path.join(source_dir, '*.dat')
    list_of_files = glob.glob(search_pattern)

    if not list_of_files:
        print(f"No .dat files found in: {source_dir}")
        return None

    # Get newest file
    latest_file = max(list_of_files, key=os.path.getmtime)
    print(f"Latest file found: {latest_file}")

    # Create experiment folder with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    experiment_folder = os.path.join(
        destination_root,
        f"{experiment_name}_{timestamp}"
    )

    os.makedirs(experiment_folder, exist_ok=True)

    # Prepare destination file path
    filename = os.path.basename(latest_file)
    destination_file = os.path.join(experiment_folder, filename)

    # Prevent overwrite
    base_name, extension = os.path.splitext(filename)
    counter = 1

    while os.path.exists(destination_file):
        destination_file = os.path.join(
            experiment_folder,
            f"{base_name}_{counter}{extension}"
        )
        counter += 1

    # Move file
    shutil.move(latest_file, destination_file)

    print(f"File moved to: {destination_file}")

    return destination_file


###############################################################################
# PATH CONFIGURATION
###############################################################################

your_path = r"C:\Users\c1op3\Downloads"
script_dir = os.path.dirname(os.path.abspath(__file__))
destination_path = os.path.join(script_dir, 'dat_directory')
experiment_name = "test1"


###############################################################################
# EXECUTE MOVE
###############################################################################

capturedFileName = find_and_move_latest_dat_file(
    source_dir=your_path,
    destination_root=destination_path,
    experiment_name=experiment_name
)

if capturedFileName:
    print(f"Using file: {capturedFileName}")
else:
    print("No file available. Exiting.")
###############################################################################
# READ FILE
###############################################################################
fp = open(capturedFileName,'rb')
readNumBytes = os.path.getsize(capturedFileName)
print("readNumBytes:", readNumBytes)
allBinData = fp.read()
fp.close()

###############################################################################
# PARSE ALL FRAMES INTO MEMORY
###############################################################################
totalBytesParsed = 0
numFramesParsed = 0

frames_points = []   # list of Nx3 arrays
frames_velocity = [] # list of N arrays

while totalBytesParsed < readNumBytes:

    parser_result, \
    headerStartIndex, \
    totalPacketNumBytes, \
    numDetObj, \
    numTlv, \
    subFrameNumber, \
    detectedX_array, \
    detectedY_array, \
    detectedZ_array, \
    detectedV_array, \
    detectedRange_array, \
    detectedAzimuth_array, \
    detectedElevation_array, \
    detectedSNR_array, \
    detectedNoise_array = parser_one_mmw_demo_output_packet(
        allBinData[totalBytesParsed:], 
        readNumBytes-totalBytesParsed)

    if parser_result != 0:
        break

    totalBytesParsed += (headerStartIndex + totalPacketNumBytes)
    numFramesParsed += 1

    if numDetObj > 0:
        points = np.column_stack((
            detectedX_array[:numDetObj],
            detectedY_array[:numDetObj],
            detectedZ_array[:numDetObj]
        ))
        velocities = np.array(detectedV_array[:numDetObj])

        frames_points.append(points)
        frames_velocity.append(velocities)
    else:
        frames_points.append(np.empty((0,3)))
        frames_velocity.append(np.array([]))

print("Total frames parsed:", numFramesParsed)
###############################################################################
# RANGE VS TIME DATA STRUCTURE
###############################################################################

frame_period = 0.05  # seconds (adjust if you know actual frameCfg)
time_axis = []
range_frames = []

for i, points in enumerate(frames_points):

    current_time = i * frame_period
    time_axis.append(current_time)

    if len(points) > 0:
        ranges = np.sqrt(
            points[:,0]**2 +
            points[:,1]**2 +
            points[:,2]**2
        )
        range_frames.append(ranges)
    else:
        range_frames.append(np.array([]))

time_axis = np.array(time_axis)
###############################################################################
# 3D ANIMATION
###############################################################################
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')

scatter = ax.scatter([], [], [], c=[], cmap='jet')

ax.set_xlim(-5, 5)
ax.set_ylim(0, 10)
ax.set_zlim(-3, 3)

ax.set_xlabel("X (m)")
ax.set_ylabel("Y (m)")
ax.set_zlabel("Z (m)")
ax.set_title("mmWave Point Cloud Motion")

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
        sc = ax.scatter(
            points[:,0],
            points[:,1],
            points[:,2],
            c=velocities,
            cmap='jet'
        )

    return []

ani = FuncAnimation(
    fig,
    update,
    frames=len(frames_points),
    interval=50
)

plt.show()

###############################################################################
# STATIC RANGE VS TIME PLOT
###############################################################################

plt.figure()

for i in range(len(range_frames)):
    if len(range_frames[i]) > 0:
        t = np.ones(len(range_frames[i])) * time_axis[i]
        plt.scatter(t, range_frames[i], s=5)

plt.xlabel("Time (s)")
plt.ylabel("Range (m)")
plt.title("Range vs Time")
plt.grid()
plt.show()

###############################################################################
# ANIMATED RANGE VS TIME
###############################################################################

fig2, ax2 = plt.subplots()

ax2.set_xlim(0, time_axis[-1])
ax2.set_ylim(0, 10)

ax2.set_xlabel("Time (s)")
ax2.set_ylabel("Range (m)")
ax2.set_title("Range vs Time Animation")

all_times = []
all_ranges = []

def update_range(frame_idx):

    if len(range_frames[frame_idx]) > 0:
        t = np.ones(len(range_frames[frame_idx])) * time_axis[frame_idx]
        all_times.extend(t)
        all_ranges.extend(range_frames[frame_idx])

    ax2.cla()
    ax2.set_xlim(0, time_axis[-1])
    ax2.set_ylim(0, 10)
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Range (m)")
    ax2.set_title("Range vs Time Animation")

    ax2.scatter(all_times, all_ranges, s=5)

ani2 = FuncAnimation(
    fig2,
    update_range,
    frames=len(range_frames),
    interval=50
)

plt.show()

#velocity vs time
#