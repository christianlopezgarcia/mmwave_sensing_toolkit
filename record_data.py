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
time.sleep(15)

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
# --------------------------------------------------
# 4️⃣ SELECT COM PORTS (CLI and DATA)
# --------------------------------------------------
# --------------------------------------------------
# 4️⃣ SELECT COM PORTS (CLI and DATA)
# --------------------------------------------------
try:
    print("Waiting for serial ports to populate...")
    
    # Port mapping based on your requirements
    # comPort_0 = CLI CFG_port -> COM6
    # comPort_1 = DATA_port     -> COM5
    port_config = {
        "comPort_0": "COM6",
        "comPort_1": "COM5"
    }

    for widget_id, port_name in port_config.items():
        success = False
        print(f"Searching for {port_name} in {widget_id}...")
        
        # We loop because the dropdown list takes time to populate after the menu opens
        for attempt in range(15): 
            script = """
                var widget = document.getElementById(arguments[0]);
                if (!widget) return "no_widget";
                
                var options = widget.querySelectorAll('option');
                if (options.length <= 1) return "not_ready"; // Only 'N/A' or empty
                
                for (var i = 0; i < options.length; i++) {
                    if (options[i].textContent.includes(arguments[1])) {
                        widget.selectedValue = options[i].value;
                        // Trigger events so the app knows we changed it
                        widget.dispatchEvent(new CustomEvent('selected-value-changed'));
                        widget.dispatchEvent(new Event('change', { bubbles: true }));
                        return "success";
                    }
                }
                return "port_not_found";
            """
            result = driver.execute_script(script, widget_id, port_name)
            
            if result == "success":
                print(f"✓ {port_name} successfully set in {widget_id}")
                success = True
                break
            elif result == "no_widget":
                print(f"CRITICAL: Could not find widget {widget_id} in DOM")
                break
            
            time.sleep(1) # Wait for scan to populate list
            
        if not success:
            print(f"✗ Failed to set {port_name} in {widget_id} (Result: {result})")

    time.sleep(1)

    # --------------------------------------------------
    # CLICK OK BUTTON (Using exact ID from your HTML)
    # --------------------------------------------------
    print("Attempting to click OK button...")
    # The ID in your HTML is 'btnOK'
    ok_button = wait.until(
        EC.presence_of_element_located((By.ID, "btnOK"))
    )
    
    # JavaScript click is safer for paper-buttons
    driver.execute_script("arguments[0].click();", ok_button)
    print("✓ Serial ports confirmed via btnOK.")
    
    time.sleep(3) # Wait for dialog to close and connection to establish

except Exception as e:
    print(f"Serial configuration failed: {e}")

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