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

except Exception as e:
    print(f"General script failure: {e}")

finally:
    print("Script complete. Browser remains open for recording.")
    # driver.quit() # Uncomment if you want it to close automatically