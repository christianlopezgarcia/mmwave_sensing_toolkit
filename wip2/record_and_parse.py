import os
import time
import glob
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Import your custom parser
from ti_mmw_official_tool.parser_scripts.parser_mmw_demo import parser_one_mmw_demo_output_packet

###############################################################################
# CONFIGURATION & DIRECTORY SETUP
###############################################################################
EXPERIMENT_NAME = "test_run_01"
BASE_DIR = r"C:\Users\c1op3\Downloads\dat_directory"
SAVE_PATH = os.path.join(BASE_DIR, EXPERIMENT_NAME)

# Create directory if it doesn't exist
os.makedirs(SAVE_PATH, exist_ok=True)
print(f"Data will be saved to: {SAVE_PATH}")

###############################################################################
# PHASE 1: SELENIUM DATA RECORDING
###############################################################################
options = webdriver.ChromeOptions()
options.add_argument(r"--user-data-dir=C:\SeleniumTIProfile")
options.add_argument("--profile-directory=Default")

# FORCE CHROME TO DOWNLOAD TO OUR SPECIFIC EXPERIMENT FOLDER
prefs = {
    "download.default_directory": SAVE_PATH,
    "download.prompt_for_download": False,
    "directory_upgrade": True
}
options.add_experimental_option("prefs", prefs)

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 20)

try:
    driver.get("https://dev.ti.com/gallery/view/mmwave/mmWave_Demo_Visualizer/ver/3.6.0/")
    time.sleep(10) # Initial Load

    # --- Setup & Connection (Condensed for brevity, same as your working script) ---
    # [Note: Keep your specific button clicks/serial port logic here]
    # (Assuming Serial Ports COM6/COM5 and Platform xWR68xx_AOP are set)
    
    # 8️⃣ START RECORDING
    recording_duration_sec = 10
    record_btn_id = "ti_widget_button_record"
    record_btn = wait.until(EC.element_to_be_clickable((By.ID, record_btn_id)))
    driver.execute_script("arguments[0].click();", record_btn)
    print(f"▶ Recording STARTED for {recording_duration_sec}s...")
    
    time.sleep(recording_duration_sec)

    # 🔟 STOP RECORDING
    driver.execute_script("arguments[0].click();", record_btn)
    print("■ Recording STOPPED. Waiting for file to save...")
    time.sleep(5) # Give Chrome time to move file from .crdownload to .dat

finally:
    driver.quit() 

###############################################################################
# PHASE 2: FIND AND PARSE THE NEW FILE
###############################################################################
def get_latest_dat(path):
    files = glob.glob(os.path.join(path, '*.dat'))
    return max(files, key=os.path.getmtime) if files else None

capturedFileName = get_latest_dat(SAVE_PATH)

if not capturedFileName:
    print("Error: No .dat file found in the experiment directory!")
    exit()

print(f"Parsing: {capturedFileName}")

# --- Parsing Logic ---
with open(capturedFileName, 'rb') as fp:
    allBinData = fp.read()
    readNumBytes = len(allBinData)

totalBytesParsed = 0
frames_points = []
frames_velocity = []

while totalBytesParsed < readNumBytes:
    res = parser_one_mmw_demo_output_packet(allBinData[totalBytesParsed:], readNumBytes-totalBytesParsed)
    
    # Unpack result (Adjust indices if your parser returns different lengths)
    parser_result, headerStart, totalBytes, numObj = res[0], res[1], res[2], res[3]
    # x, y, z are usually indices 6, 7, 8; velocity is 9
    detX, detY, detZ, detV = res[6], res[7], res[8], res[9]

    if parser_result != 0: break

    totalBytesParsed += (headerStart + totalBytes)
    
    if numObj > 0:
        frames_points.append(np.column_stack((detX[:numObj], detY[:numObj], detZ[:numObj])))
        frames_velocity.append(np.array(detV[:numObj]))
    else:
        frames_points.append(np.empty((0,3)))
        frames_velocity.append(np.array([]))

###############################################################################
# PHASE 3: VISUALIZATION (Velocity vs Time)
###############################################################################
frame_period = 0.05
time_axis = np.arange(len(frames_points)) * frame_period

plt.figure(figsize=(10, 6))
for i, v_array in enumerate(frames_velocity):
    if len(v_array) > 0:
        plt.scatter([time_axis[i]] * len(v_array), v_array, c='blue', s=5, alpha=0.5)

plt.xlabel("Time (s)")
plt.ylabel("Velocity (m/s)")
plt.title(f"Velocity vs Time: {EXPERIMENT_NAME}")
plt.grid(True)
plt.show()

# (Optional: Your existing 3D Animation code can follow here)