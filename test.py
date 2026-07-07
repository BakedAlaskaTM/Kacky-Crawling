# Import the necessary modules from Selenium
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys  # Added import for Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
import re
import json

def read_json(filename):
    try:
        file = open(filename, "r")
    except FileNotFoundError:
        print(f"FileNotFoundError: File '{filename}' does not exist.")
        return None
    else:
        file_str = file.read()
        file.close()
    return json.loads(file_str)

def write_json(filename: str, data):
    with open(filename, 'w') as json_file:
        json.dump(data, json_file, indent=4, ensure_ascii=True)

options = Options()
options.page_load_strategy = "normal"

map_recs = []
players = []

driver = webdriver.Chrome(options=options)

maps = read_json("map_info.json")
seen_players = set()
for map in maps:
    driver.get(f"https://kackiestkacky.com/hunting/editions/maps.php?uid={map['uid']}")
    map_table = driver.find_element(By.XPATH, "//table[@id='maps']/tbody")
    while True:
        rows = map_table.find_elements(By.TAG_NAME, "tr")
        if len(rows) > 1:
            break

    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) > 0:
            rank = cells[0].text
            player_link = cells[1].find_element(By.TAG_NAME, "a").get_attribute("href")
            match = re.search(r"pid=([^&]+)", player_link)
            if match:
                player_uid = match.group(1)
            else:
                player_uid = None
            player_html = cells[1].find_element(By.TAG_NAME, "a").get_attribute("innerHTML")
            player_name = cells[1].find_element(By.TAG_NAME, "a").text
            time = cells[2].text
            fin_count = cells[3].text
            map_data = {
                "rank": int(rank) if rank else None,
                "player_id": player_uid,
                "map_id": map['uid'],
                "time": time,
                "finishes": int(fin_count) if fin_count else None
            }
        
            player_data = {
                "pid": player_uid,
                "player_html": player_html,
                "name": player_name
            }
            if player_uid and player_uid not in seen_players:
                players.append(player_data)
                seen_players.add(player_uid)
            map_recs.append(map_data)

write_json("map_recs.json", map_recs)
write_json("players.json", players)
driver.quit()