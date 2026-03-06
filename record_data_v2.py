import os
import time
import glob
import shutil
from datetime import datetime
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d import Axes3D
from scipy.ndimage import gaussian_filter

# Ensure this import matches your local directory structure
from ti_mmw_official_tool.parser_scripts.parser_mmw_demo import parser_one_mmw_demo_output_packet

# -----------------------------
# 1. CONFIGURATION
# -----------------------------
class Config:
    # Mode Selection
    RECORD_LIVE = True  # True: Use Selenium to record, False: Use latest existing file
    EXPERIMENT_NAME = "Thursday_Test1"

    # Paths
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    DAT_SOURCE_DIR = r"C:\Users\c1op3\Downloads"  
    DAT_DEST_DIR = os.path.join(SCRIPT_DIR, 'dat_directory')
    
    # Radar Parameters
    FRAME_PERIOD = 0.1  # seconds
    SERIAL_PORTS = {"comPort_0": "COM6", "comPort_1": "COM5"}
    PLATFORM_VALUE = "xWR68xx_AOP"

    # Recording Parameters
    RECORD_DURATION_SEC = 10
    FILE_SIZE_MB = 100
    DOWNLOAD_TIMEOUT_SEC = 20  # How long to wait for Chrome to finish downloading


# -----------------------------
# 2. RECORDER CLASS (Selenium)
# -----------------------------
class RadarRecorder:
    def __init__(self, config):
        self.cfg = config

    def record_and_fetch_file(self):
        """Runs the Selenium automation and returns the path to the new .dat file."""
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager

        print("🌐 Starting TI Visualizer via Selenium...")
        
        # Chrome setup with download preferences to prevent prompts
        options = webdriver.ChromeOptions()
        options.add_argument(r"--user-data-dir=C:\SeleniumTIProfile")
        options.add_argument("--profile-directory=Default")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        prefs = {
            "download.default_directory": self.cfg.DAT_SOURCE_DIR,
            "download.prompt_for_download": False,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        wait = WebDriverWait(driver, 15)

        script_start_time = time.time() # MARKER: Capture time before recording starts

        try:
            driver.get("https://dev.ti.com/gallery/view/mmwave/mmWave_Demo_Visualizer/ver/3.6.0/")
            time.sleep(12)

            # Handle modals
            for selector in [(By.ID, "consent_prompt_submit"), 
                             (By.XPATH, "//paper-button[contains(text(),'CLOSE')] | //button[contains(text(),'CLOSE')]")]:
                try: wait.until(EC.element_to_be_clickable(selector)).click()
                except: pass

            # Set platform
            driver.execute_script("""
                var element = document.getElementById(arguments[0]);
                element.selectedValue = arguments[1];
                element.dispatchEvent(new Event('change'));
            """, "ti_widget_droplist_platform", self.cfg.PLATFORM_VALUE)
            time.sleep(2)

            # Configure serial ports
            driver.execute_script("arguments[0].click();", wait.until(EC.presence_of_element_located((By.XPATH, "//span[contains(text(),'Options')]"))))
            driver.execute_script("arguments[0].click();", wait.until(EC.presence_of_element_located((By.XPATH, "//li[.//td[contains(text(),'Serial Port')]]"))))
            time.sleep(5)

            for widget_id, port_name in self.cfg.SERIAL_PORTS.items():
                driver.execute_script("""
                    var widget = document.getElementById(arguments[0]);
                    var options = widget.querySelectorAll('option');
                    for (var i = 0; i < options.length; i++) {
                        if (options[i].textContent.includes(arguments[1])) {
                            widget.selectedValue = options[i].value;
                            widget.dispatchEvent(new CustomEvent('selected-value-changed'));
                            widget.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }
                """, widget_id, port_name)
                time.sleep(1)

            # Confirm and Send Config
            driver.execute_script("arguments[0].click();", wait.until(EC.presence_of_element_located((By.ID, "btnOK"))))
            time.sleep(3)
            driver.execute_script("arguments[0].click();", wait.until(EC.element_to_be_clickable((By.XPATH, "//paper-button[contains(.,'Send Config')] | //paper-material[contains(.,'Send Config')]"))))
            time.sleep(5)

            # Switch to Plots and Set limits
            driver.execute_script("arguments[0].click();", wait.until(EC.presence_of_element_located((By.XPATH, "//paper-tab[@id='tab_1'] | //paper-tab[contains(., 'Plots')]"))))
            time.sleep(3)

            for wid, val in [("ti_widget_textbox_record_time", self.cfg.RECORD_DURATION_SEC),
                             ("ti_widget_textbox_record_file_size_limit", self.cfg.FILE_SIZE_MB)]:
                driver.execute_script("""
                    var input = document.getElementById(arguments[0]).querySelector('input');
                    input.value = arguments[1];
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                """, wid, str(val))

            # Record
            record_btn_id = "ti_widget_button_record"
            driver.execute_script("arguments[0].click();", wait.until(EC.element_to_be_clickable((By.ID, record_btn_id))))
            print(f"🔴 Recording started for {self.cfg.RECORD_DURATION_SEC} seconds...")
            time.sleep(self.cfg.RECORD_DURATION_SEC)
            
            driver.execute_script("arguments[0].click();", wait.until(EC.element_to_be_clickable((By.ID, record_btn_id))))
            print("⏹️ Recording stopped.")
        except Exception as e:
            print(f"Selenium Error: {e}")
        # finally:
        #     driver.quit()

        return self._wait_and_move_file(script_start_time)

    def _wait_and_move_file(self, start_time):
        """Robustly waits for the newly downloaded file to appear."""
        print("⏳ Waiting for file download to complete...")
        elapsed = 0
        
        while elapsed < self.cfg.DOWNLOAD_TIMEOUT_SEC:
            files = glob.glob(os.path.join(self.cfg.DAT_SOURCE_DIR, '*.dat'))
            if files:
                latest_file = max(files, key=os.path.getmtime)
                # Ensure the file is NEWER than when we started the script
                if os.path.getmtime(latest_file) > start_time:
                    time.sleep(1)  # Buffer to ensure writing is totally finished
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    exp_folder = os.path.join(self.cfg.DAT_DEST_DIR, f"{self.cfg.EXPERIMENT_NAME}_{timestamp}")
                    os.makedirs(exp_folder, exist_ok=True)
                    
                    dest_file = os.path.join(exp_folder, os.path.basename(latest_file))
                    shutil.move(latest_file, dest_file)
                    print(f"✅ Success! Moved new file to: {dest_file}")
                    return dest_file
            
            time.sleep(1)
            elapsed += 1
            
        raise FileNotFoundError("❌ Timeout: No new .dat file appeared in Downloads folder.")

    def get_latest_offline_file(self):
        """Grabs the most recent file from the dat_directory if offline."""
        folders = sorted([os.path.join(self.cfg.DAT_DEST_DIR, d) for d in os.listdir(self.cfg.DAT_DEST_DIR) 
                          if os.path.isdir(os.path.join(self.cfg.DAT_DEST_DIR, d))], 
                         key=os.path.getmtime, reverse=True)
        if not folders: raise FileNotFoundError("No experiment folders found.")
        
        dat_files = glob.glob(os.path.join(folders[0], '*.dat'))
        if not dat_files: raise FileNotFoundError(f"No .dat files in {folders[0]}")
        
        return max(dat_files, key=os.path.getmtime)


# -----------------------------
# 3. PARSER CLASS
# -----------------------------
class RadarParser:
    def __init__(self, config):
        self.cfg = config
        self.frames_points = []
        self.frames_velocity = []
        self.time_axis = []
        self.range_frames = []

    def parse(self, dat_file):
        print(f"🛠️ Parsing data from: {dat_file}")
        with open(dat_file, 'rb') as fp:
            allBinData = fp.read()
            
        readNumBytes = len(allBinData)
        totalBytesParsed = 0
        numFramesParsed = 0

        while totalBytesParsed < readNumBytes:
            try:
                result = parser_one_mmw_demo_output_packet(allBinData[totalBytesParsed:], readNumBytes - totalBytesParsed)
                parser_result, headerStartIndex, totalPacketNumBytes, numDetObj = result[:4]
                
                if parser_result != 0: break

                if numDetObj > 0:
                    detectedX_array, detectedY_array, detectedZ_array, detectedV_array = result[6:10]
                    points = np.column_stack((detectedX_array[:numDetObj], detectedY_array[:numDetObj], detectedZ_array[:numDetObj]))
                    self.frames_points.append(points)
                    self.frames_velocity.append(np.array(detectedV_array[:numDetObj]))
                else:
                    self.frames_points.append(np.empty((0,3)))
                    self.frames_velocity.append(np.array([]))

                totalBytesParsed += (headerStartIndex + totalPacketNumBytes)
                numFramesParsed += 1
            except Exception as e:
                print(f"Parsing ended or encountered error: {e}")
                break

        print(f"📊 Total frames parsed: {numFramesParsed}")
        self._compute_metrics()

    def _compute_metrics(self):
        """Calculates ranges and time progression."""
        for i, points in enumerate(self.frames_points):
            self.time_axis.append(i * self.cfg.FRAME_PERIOD)
            if len(points) > 0:
                self.range_frames.append(np.sqrt(points[:,0]**2 + points[:,1]**2 + points[:,2]**2))
            else:
                self.range_frames.append(np.array([]))
        self.time_axis = np.array(self.time_axis)


# -----------------------------
# 4. VISUALIZER CLASS
# -----------------------------
class RadarVisualizer:
    def __init__(self, parser):
        self.parser = parser
        self.time_axis = parser.time_axis
        self.frames_points = parser.frames_points
        self.frames_velocity = parser.frames_velocity
        self.range_frames = parser.range_frames
        
        self.all_times, self.all_vels, self.all_ranges = [], [], []
        self._flatten_data()

    def _flatten_data(self):
        for i, vels in enumerate(self.frames_velocity):
            if len(vels) > 0:
                pts = self.frames_points[i]
                rngs = np.sqrt(pts[:,0]**2 + pts[:,1]**2 + pts[:,2]**2)
                self.all_times.extend([self.time_axis[i]] * len(vels))
                self.all_vels.extend(vels)
                self.all_ranges.extend(rngs)

        self.all_times = np.array(self.all_times)
        self.all_vels = np.array(self.all_vels)
        self.all_ranges = np.array(self.all_ranges)

    def plot_and_save_combined(self, save_filepath):
        """Plots all three visualizations on a single figure and saves it."""
        if len(self.all_times) == 0:
            print("No data points available for plotting.")
            return

        # Create a large figure with 3 stacked plots (rows=3, cols=1)
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 18))
        fig.tight_layout(pad=6.0) # Adds padding between subplots

        # -----------------------------
        # Subplot 1: Basic Velocity
        # -----------------------------
        v_max = max(abs(self.all_vels.min()) if len(self.all_vels) else 0, 
                    abs(self.all_vels.max()) if len(self.all_vels) else 0, 0.1)
        norm = mcolors.TwoSlopeNorm(vmin=-v_max, vcenter=0, vmax=v_max)
        
        sc1 = ax1.scatter(self.all_times, self.all_vels, c=self.all_vels, cmap='RdBu_r', norm=norm, s=12, alpha=0.7, edgecolors='none')
        fig.colorbar(sc1, ax=ax1, label="Radial Velocity (m/s)")
        ax1.axhline(0, color='black', linestyle='--', linewidth=1, alpha=0.5)
        ax1.set_xlabel("Time (s)")
        ax1.set_ylabel("Velocity (m/s)")
        ax1.set_title("Doppler Velocity Profile")
        ax1.grid(True, linestyle=':', alpha=0.6)

        # -----------------------------
        # Subplot 2: Micro-Doppler
        # -----------------------------
        h_v, x_v, y_v = np.histogram2d(self.all_times, self.all_vels, bins=[600, 200])
        h_v_smooth = gaussian_filter(h_v, sigma=1.5)
        
        im2 = ax2.imshow(h_v_smooth.T, origin='lower', aspect='auto', extent=[x_v[0], x_v[-1], y_v[0], y_v[-1]], cmap='turbo', norm=mcolors.PowerNorm(gamma=0.4))
        ax2.set_title("Gradient Micro-Doppler Signature (VT Profile)")
        ax2.set_xlabel("Time (s)")
        ax2.set_ylabel("Velocity (m/s)")
        fig.colorbar(im2, ax=ax2, label='Signal Density')

        # -----------------------------
        # Subplot 3: Range-Time Intensity
        # -----------------------------
        h_r, x_r, y_r = np.histogram2d(self.all_times, self.all_ranges, bins=[600, 250])
        h_r_smooth = gaussian_filter(h_r, sigma=1.2)
        
        im3 = ax3.imshow(h_r_smooth.T, origin='lower', aspect='auto', extent=[x_r[0], x_r[-1], y_r[0], y_r[-1]], cmap='turbo', norm=mcolors.LogNorm())
        ax3.set_title("Gradient Range-Time Intensity (RT Profile)")
        ax3.set_xlabel("Time (s)")
        ax3.set_ylabel("Range (m)")
        ax3.set_ylim(0, 8) 
        fig.colorbar(im3, ax=ax3, label='Intensity')

        # -----------------------------
        # Save and Display
        # -----------------------------
        plt.savefig(save_filepath, dpi=300, bbox_inches='tight')
        print(f"🖼️ Saved combined plot to: {save_filepath}")
        plt.show()

# -----------------------------
# 5. MAIN EXECUTION
# -----------------------------
if __name__ == "__main__":
    # 1. Load Config
    cfg = Config()
    
    # 2. Setup Recorder and get File
    recorder = RadarRecorder(cfg)
    if cfg.RECORD_LIVE:
        dat_filepath = recorder.record_and_fetch_file()
    else:
        dat_filepath = recorder.get_latest_offline_file()
        print(f"📁 Using offline file: {dat_filepath}")

    # 3. Parse Data
    parser = RadarParser(cfg)
    parser.parse(dat_filepath)

    # 4. Visualize Data
    print("🎨 Generating visualizations...")
    viz = RadarVisualizer(parser)
    
    # Create an image filename based on the .dat filename
    save_img_path = dat_filepath.replace('.dat', '_combined_plots.png')
    
    # Generate, display, and save the massive 3-pane figure
    viz.plot_and_save_combined(save_img_path)