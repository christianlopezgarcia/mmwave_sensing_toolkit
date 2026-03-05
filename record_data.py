import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --------------------------------------------------
# SETUP DRIVER
# --------------------------------------------------
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
# Required for TI Gallery to prevent cross-origin issues with their custom widgets
options.add_argument("--disable-web-security")
options.add_argument("--allow-running-insecure-content")

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)

# Robust wait time for heavy industrial web apps
wait = WebDriverWait(driver, 20)

# --------------------------------------------------
# 1️⃣ OPEN URL
# --------------------------------------------------
driver.get("https://dev.ti.com/gallery/view/mmwave/mmWave_Demo_Visualizer/ver/3.6.0/")
print("Waiting for application to load...")
time.sleep(10) 

# --------------------------------------------------
# 2️⃣ CLEAR BLOCKING OVERLAYS (Cookies & Instructions)
# --------------------------------------------------
try:
    # This targets the button seen in your screenshot
    close_instructions = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//paper-button[contains(text(),'CLOSE')] | //button[contains(text(),'CLOSE')]"))
    )
    close_instructions.click()
    print("✓ Instruction modal closed.")
    time.sleep(1)
except Exception:
    print("! Instruction modal not found.")
# Step A: Click "Agree and proceed" on Cookie Modal
try:
    # Using the specific ID you provided: consent_prompt_submit
    cookie_btn = wait.until(
        EC.element_to_be_clickable((By.ID, "consent_prompt_submit"))
    )
    cookie_btn.click()
    print("✓ Cookie consent accepted.")
    time.sleep(2) # Wait for overlay to fade
except Exception:
    print("! Cookie modal not found or already dismissed.")

# Step B: Click "CLOSE" on the "How to Use" Instruction Modal


# --------------------------------------------------
# 3️⃣ SELECT PLATFORM → xWR68xx_AOP
# --------------------------------------------------
try:
    platform_id = "ti_widget_droplist_platform"
    wait.until(EC.presence_of_element_located((By.ID, platform_id)))
    
    # Custom TI widgets require JS to set the internal 'selectedValue' attribute
    driver.execute_script(f"document.getElementById('{platform_id}').selectedValue = 'xWR68xx_AOP';")
    driver.execute_script(f"document.getElementById('{platform_id}').dispatchEvent(new Event('change'));")
    print("✓ Platform set to xWR68xx_AOP.")
except Exception as e:
    print(f"✗ Failed to set platform: {e}")

# # --------------------------------------------------
# # 4️⃣ CONFIGURE SERIAL PORTS (Options Menu)
# # --------------------------------------------------
# try:
#     # Click 'Options' in the top red bar
#     options_menu = wait.until(EC.element_to_be_clickable((By.ID, "ti_widget_optionsmenu")))
#     options_menu.click()
    
#     # Click 'Serial Port' from the dropdown
#     serial_opt = wait.until(EC.element_to_be_clickable((By.XPATH, "//ti-widget-menuaction[contains(@label,'Serial Port')]")))
#     serial_opt.click()
    
#     # Click OK on the port configuration dialog
#     ok_btn = wait.until(EC.element_to_be_clickable((By.ID, "okButton")))
#     ok_btn.click()
#     print("✓ Serial ports configured.")
#     time.sleep(2)
# except Exception as e:
#     print(f"! Serial configuration failed: {e}")
# --------------------------------------------------
# 4️⃣ CONFIGURE SERIAL PORTS (Options Menu)
# --------------------------------------------------
# --------------------------------------------------
# 4️⃣ CONFIGURE SERIAL PORTS (Correct Method)
# --------------------------------------------------
try:
    # 1️⃣ Click Options menu
    options_trigger = wait.until(
        EC.presence_of_element_located((By.XPATH, "//span[contains(text(),'Options')]"))
    )
    driver.execute_script("arguments[0].click();", options_trigger)
    print("✓ Options menu opened.")
    time.sleep(2)

    # 2️⃣ Click Serial Port using its visible text
    driver.execute_script("""
        let items = document.querySelectorAll('ti-widget-menuaction');
        for (let i of items) {
            if (i.innerText.includes('Serial Port')) {
                i.click();
                break;
            }
        }
    """)
    print("✓ Serial Port menu item clicked.")
    time.sleep(2)

    # 3️⃣ Click OK in dialog
    ok_btn = wait.until(EC.presence_of_element_located((By.ID, "okButton")))
    driver.execute_script("arguments[0].click();", ok_btn)

    print("✓ Serial port dialog confirmed.")

except Exception as e:
    print(f"! Serial configuration failed: {e}")
# --------------------------------------------------
# 5️⃣ SWITCH TO PLOTS TAB
# --------------------------------------------------
try:
    plots_tab = wait.until(EC.element_to_be_clickable((By.ID, "ti_widget_tab_plot")))
    plots_tab.click()
    print("✓ Switched to Plots tab.")
    time.sleep(2)
except Exception as e:
    print(f"✗ Plots tab not found: {e}")

# --------------------------------------------------
# 6️⃣ START RECORDING (1000s)
# --------------------------------------------------
try:
    time_input_id = "ti_widget_textbox_record_time"
    record_btn_id = "ti_widget_button_record"
    
    # Use JS to set the text value to ensure the app's backend sees it
    wait.until(EC.presence_of_element_located((By.ID, time_input_id)))
    driver.execute_script(f"document.getElementById('{time_input_id}').value = '1000';")
    
    # Click the Record button
    rec_btn = wait.until(EC.element_to_be_clickable((By.ID, record_btn_id)))
    rec_btn.click()
    print("✓ Recording successfully started.")
except Exception as e:
    print(f"✗ Recording failed: {e}")

# Wait to observe the result
time.sleep(15)
# driver.quit()