# Import the necessary modules from Selenium
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys  # Added import for Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
import re
import json

options = Options()
options.page_load_strategy = "normal"

map_info = []

driver = webdriver.Chrome(options=options)

driver.get("https://kackiestkacky.com/hunting/editions/records.php?edition=0")

while True:
    try:
        select = driver.find_element(By.CLASS_NAME, "select2-selection__arrow")
        select.click()
        option = driver.find_element(By.XPATH, "//li[text()='All']")
        option.click()
        break
    except:
        continue

map_table = driver.find_element(By.XPATH, "//table[@id='records']/tbody")
while True:
    rows = map_table.find_elements(By.TAG_NAME, "tr")
    if len(rows) > 1:
        break



print(f"Found {len(rows)} rows in the map table.")

for row in rows:
    cells = row.find_elements(By.TAG_NAME, "td")
    if len(cells) > 0:
        match_1 = re.search(r"uid=([^&]+)", cells[0].find_element(By.TAG_NAME, "a").get_attribute("href"))
        if match_1:
            map_uid = match_1.group(1)
        else:
            map_uid = None
        match_2 = re.search(r"#([^&]+)", cells[0].find_element(By.TAG_NAME, "a").text)
        if match_2:
            map_num = match_2.group(1)
        else:
            map_num = None
        map_data = {
            "uid": map_uid,
            "number": map_num
        }
        map_info.append(map_data)

json_data = json.dumps(map_info, indent=4)
with open("map_info.json", "w") as json_file:
    json_file.write(json_data)

driver.quit()