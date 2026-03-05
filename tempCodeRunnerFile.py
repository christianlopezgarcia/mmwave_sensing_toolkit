------------------------------------------------
# # 2️⃣ CLOSE POPUP (if appears)
# # --------------------------------------------------
# try:
#     close_button = wait.until(
#         EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'OK') or contains(text(),'Close')]"))
#     )
#     close_button.click()
# except:
#     print("No popup detected")


# # --------------------------------------------------
# # 3️⃣ SELECT PLATFORM → xWR68xx_AOP
# # --------------------------------------------------
# platform_dropdown = wait.until(
#     EC.presence_of_element_located((By.XPATH, "//select[contains(@ng-model,'platform')]"))
# )

# Select(platform_dropdown).select_by_visible_text("xWR68xx_AOP")


# # --------------------------------------------------
# # 4️⃣ CLICK CONNECT
# # --------------------------------------------------
# connect_button = wait.until(
#     EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Connect')]"))
# )
# connect_button.click()

# time.sleep(3)


# # --------------------------------------------------
# # 5️⃣ OPTIONS → SERIAL PORT CONFIGURATION
# # --------------------------------------------------
# options_menu = wait.until(
#     EC.element_to_be_clickable((By.XPATH, "//span[contains(text(),'Options')]"))
# )
# options_menu.click()

# configure_ports = wait.until(
#     EC.element_to_be_clickable((By.XPATH, "//span[contains(text(),'Serial Port')]"))
# )
# configure_ports.click()

# time.sleep(2)

# # Click OK in serial config dialog
# ok_button = wait.until(
#     EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'OK')]"))
# )
# ok_button.click()


# # --------------------------------------------------
# # 6️⃣ GO TO PLOTS TAB
# # --------------------------------------------------
# plots_tab = wait.until(
#     EC.element_to_be_clickable((By.XPATH, "//span[contains(text(),'Plots')]"))
# )
# plots_tab.click()

# time.sleep(2)


# # --------------------------------------------------
# # 7️⃣ SCROLL RIGHT
# # --------------------------------------------------
# driver.execute_script("window.scrollTo(document.body.scrollWidth, 0);")
# time.sleep(2)


# # --------------------------------------------------
# # 8️⃣ START RECORDING (SET 1000 / 1000)
# # --------------------------------------------------

# # Example: change frame count input
# frame_input = wait.until(
#     EC.presence_of_element_located((By.XPATH, "//input[contains(@ng-model,'numFrames')]"))
# )
# frame_input.clear()
# frame_input.send_keys("1000")

# # Example: change time duration input
# time_input = wait.until(
#     EC.presence_of_element_located((By.XPATH, "//input[contains(@ng-model,'recordTime')]"))
# )
# time_input.clear()
# time_input.send_keys("1000")

# # Click start record
# record_button = wait.until(
#     EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Record')]"))
# )
# record_button.click()

# print("Recording started for 1000 frames / 1000 seconds")

# time.sleep(10)