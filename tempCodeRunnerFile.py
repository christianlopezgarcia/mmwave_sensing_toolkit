import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --------------------------------------------------
# SETUP CHROME (Persistent Profile + Reduced Detection)
# --------------------------------------------------

# --------------------------------------------------
# SETUP CHROME (Persistent Profile ONLY)
# --------------------------------------------------

options = webdriver.ChromeOptions()

options.add_argument(r"--user-data-dir=C:\SeleniumTIProfile")
options.add_argument("--profile-directory=Default")
options.add_argument("--start-maximized")

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)

wait = WebDriverWait(driver,1)

# --------------------------------------------------
# 1️⃣ OPEN TI VISUALIZER
# --------------------------------------------------

driver.get("https://dev.ti.com/gallery/view/mmwave/mmWave_Demo_Visualizer/ver/3.6.0/")
print("Waiting for Visualizer to load...")
time.sleep(12)

# --------------------------------------------------
# 2️⃣ CLOSE MODALS (Cookies / Instructions)
# --------------------------------------------------

try:
    cookie_btn = wait.until(
        EC.element_to_be_clickable((By.ID, "consent_prompt_submit"))
    )
    cookie_btn.click()
    print("✓ Cookie accepted.")
    time.sleep(2)
except:
    print("No cookie modal.")

try:
    close_btn = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, "//paper-button[contains(text(),'CLOSE')] | //button[contains(text(),'CLOSE')]")
        )
    )
    close_btn.click()
    print("✓ Instruction modal closed.")
except:
    print("No instruction modal.")

# --------------------------------------------------
# 3️⃣ SELECT PLATFORM xWR68xx_AOP
# --------------------------------------------------

try:
    platform_id = "ti_widget_droplist_platform"

    wait.until(EC.presence_of_element_located((By.ID, platform_id)))

    driver.execute_script("""
        var element = document.getElementById(arguments[0]);
        element.selectedValue = 'xWR68xx_AOP';
        element.dispatchEvent(new Event('change'));
    """, platform_id)

    print("✓ Platform set to xWR68xx_AOP.")
    time.sleep(3)

except Exception as e:
    print("Platform selection failed:", e)

# --------------------------------------------------
# 4️⃣ OPEN OPTIONS → SERIAL PORT
# --------------------------------------------------

try:
    # Click Options in top bar
    options_menu = wait.until(
        EC.presence_of_element_located(
            (By.XPATH, "//span[contains(text(),'Options')]")
        )
    )
    driver.execute_script("arguments[0].click();", options_menu)
    print("✓ Options menu opened.")
    time.sleep(2)

    # Click Serial Port ... using visible text
    serial_item = wait.until(
        EC.presence_of_element_located(
            (By.XPATH, "//li[.//td[contains(text(),'Serial Port')]]")
        )
    )
    driver.execute_script("arguments[0].click();", serial_item)
    print("✓ Serial Port menu clicked.")
    time.sleep(8)

except Exception as e:
    print("Serial menu failed:", e)


# --------------------------------------------------
# 4️⃣ OPEN OPTIONS → SERIAL PORT
# --------------------------------------------------

# --------------------------------------------------
# SELECT COM PORTS (CLI and DATA)
# --------------------------------------------------
try:
    # 1. Target the TI custom widgets directly
    # The first one is usually for CLI, the second for DATA
    ti_dropdowns = wait.until(
        EC.presence_of_all_elements_located((By.TAG_NAME, "ti-widget-droplist"))
    )
    
    # Map your desired ports
    ports_to_set = ["COM6", "COM5"]

    for i, port_name in enumerate(ports_to_set):
        # We find the internal value by checking the options inside the dropdown
        # TI widgets usually map 'COM6 (Silicon Labs)' to a value like '1' or 'COM6'
        
        script = """
            var widget = arguments[0];
            var targetPort = arguments[1];
            var options = widget.querySelectorAll('option');
            var foundValue = null;

            for (var i = 0; i < options.length; i++) {
                if (options[i].textContent.includes(targetPort)) {
                    foundValue = options[i].value;
                    break;
                }
            }

            if (foundValue) {
                widget.selectedValue = foundValue;
                // Important: Trigger the event so the app UI reacts
                widget.dispatchEvent(new CustomEvent('selected-value-changed'));
                widget.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
            }
            return false;
        """
        
        success = driver.execute_script(script, ti_dropdowns[i], port_name)
        if success:
            print(f"✓ {port_name} assigned to dropdown {i+1}")
        else:
            print(f"✗ Could not find {port_name} in dropdown {i+1}")

    time.sleep(2)

    # --------------------------------------------------
    # CLICK OK BUTTON
    # --------------------------------------------------
    # Using a more robust selector for the OK button
    ok_button = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "paper-button[id='okButton'], button#okButton, paper-button:contains('OK')"))
    )
    driver.execute_script("arguments[0].click();", ok_button)
    print("✓ Serial ports confirmed.")

except Exception as e:
    print("Serial configuration failed:", e)

# --------------------------------------------------
# 5️⃣ SWITCH TO PLOTS TAB
# --------------------------------------------------

try:
    plots_tab = wait.until(
        EC.element_to_be_clickable((By.ID, "ti_widget_tab_plot"))
    )
    plots_tab.click()
    print("✓ Switched to Plots tab.")
    time.sleep(3)
except Exception as e:
    print("Plots tab failed:", e)

# --------------------------------------------------
# 6️⃣ START RECORDING (1000 seconds)
# --------------------------------------------------

try:
    time_input_id = "ti_widget_textbox_record_time"
    record_btn_id = "ti_widget_button_record"

    wait.until(EC.presence_of_element_located((By.ID, time_input_id)))

    driver.execute_script("""
        document.getElementById(arguments[0]).value = '1000';
    """, time_input_id)

    record_btn = wait.until(
        EC.element_to_be_clickable((By.ID, record_btn_id))
    )
    record_btn.click()

    print("✓ Recording started.")

except Exception as e:
    print("Recording failed:", e)

print("Script complete.")