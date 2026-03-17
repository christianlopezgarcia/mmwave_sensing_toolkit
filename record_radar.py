# record_radar.py

import os
import time
import glob
import shutil
import socket
from datetime import datetime

# --- configuration (copy from your script) ---
RECORD_LIVE = True
EXPERIMENT_NAME = ""
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
DOWNLOAD_BUFFER = 60

DEBUG_PORT = 9222
PROFILE_PATH = r"C:\SeleniumTIProfile"


# --- file detection ---
def wait_for_new_dat_file(start_time):

    timeout = RECORD_DURATION_SEC + DOWNLOAD_BUFFER
    deadline = start_time + timeout

    while time.time() < deadline:

        dat_files = glob.glob(os.path.join(DAT_SOURCE_DIR, "*.dat"))

        for f in dat_files:
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
# RECORDING
# --------------------------------------------------

def record_dat_file():

    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager

    if RECORD_LIVE:

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
        # at the end return:
        return dat_file


if __name__ == "__main__":

    dat_file = record_dat_file()

    print("Recording complete:")
    print(dat_file)