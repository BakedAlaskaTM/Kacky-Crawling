from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.common.by import By
import re
import json
import os
import time as T
from postgrest.exceptions import APIError
from supabase import create_client, Client
from dotenv import load_dotenv
import pandas as pd

SAMPLES = 2
MAX_RECS = 50


def parse_time(time_str):
    if ":" not in time_str:
        return None
    m, s = time_str.split(":")
    return int(60000*int(m)+1000*float(s))

def format_time(ms):
    return f"{ms // 60000}:{(ms % 60000) / 1000:.2f}"

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

def get_map_data(driver, map_id, players, recheck_players, records_dict):
    unprocessed_recs = []
    driver.get(f"https://kackiestkacky.com/hunting/editions/maps.php?uid={map_id}")
    while True:
        try:
            select = driver.find_element(By.CLASS_NAME, "select2-selection__arrow")
            select.click()
            option = driver.find_element(By.XPATH, "//li[text()='All']")
            option.click()
            break
        except:
            continue
    map_table = driver.find_element(By.XPATH, "//table[@id='maps']/tbody")
    retries = 0
    while retries < 50:
        rows = map_table.find_elements(By.TAG_NAME, "tr")
        if len(rows) > 1:
            break
        T.sleep(0.5)
        retries += 1

    count = 0
    for row in rows:
        if count >= MAX_RECS:
            break
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) >= 3:
            rank = cells[0].text
            a_tag = cells[1].find_element(By.TAG_NAME, "a")
            player_link = a_tag.get_attribute("href")
            match = re.search(r"pid=([^&]+)", player_link)
            if match:
                player_uid = match.group(1)
            else:
                player_uid = None
            player_html = a_tag.get_attribute("innerHTML")
            player_name = a_tag.text
            time = cells[2].text
            fin_count = cells[3].text
            map_data = {
                "rank": int(rank) if rank else None,
                "player_id": player_uid,
                "map_id": map_id,
                "time": time,
                "finishes": int(fin_count) if fin_count else None
            }
        
            players[player_uid] = {
                "pid": player_uid,
                "player_html": player_html,
                "name": player_name
            }

            unprocessed_recs.append(map_data)
            count += 1
    cut_extra_recs(unprocessed_recs, recheck_players, records_dict)

def cut_extra_recs(recs: list, recheck_players: set, records_dict: dict):
    ptr = 0
    prev_time = ""
    prev_pid = ""
    for rec in recs:
        records_dict[f"{rec["map_id"]}+{rec["player_id"]}"] = rec
        if parse_time(rec["time"]) == parse_time(prev_time):
            recheck_players.add(rec["player_id"])
            records_dict[f"{rec["map_id"]}+{rec["player_id"]}"]["rank"] = 11
            recheck_players.add(prev_pid)
            records_dict[f"{rec["map_id"]}+{prev_pid}"]["rank"] = 11
        elif ptr >= 10:
            del records_dict[f"{rec["map_id"]}+{rec["player_id"]}"]
            return
        prev_time = rec["time"]
        prev_pid = rec["player_id"]
        ptr += 1

def get_player_recs(driver, pid, records_dict):
    driver.get(f"https://kackiestkacky.com/hunting/editions/players.php?pid={pid}&edition=0")
    while True:
        try:
            sort_rank = driver.find_element(By.XPATH, "//*[@aria-label='Current rank: activate to sort column ascending']")
            sort_rank.click()
            break
        except:
            continue
    map_table = driver.find_element(By.XPATH, "//table[@id='history']/tbody")
    retries = 0
    while retries < 50:
        rows = map_table.find_elements(By.TAG_NAME, "tr")
        if len(rows) == 1:
            try:
                cells = rows[0].find_elements(By.TAG_NAME, "td")
            except:
                pass
            else:
                if len(cells) >= 3:
                    break
        if len(rows) > 1:
            break
        T.sleep(0.5)
        retries += 1

    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) >= 3:
            a_tag = cells[1].find_element(By.TAG_NAME, "a")
            map_id = a_tag.get_attribute("data-uid")
            rank = int(cells[2].text)
            if rank > 10:
                return
            try:
                records_dict[f"{map_id}+{pid}"]["rank"] = rank
            except KeyError:
                pass
def scrape():
    print("Starting...")
    options = FirefoxOptions()
    options.page_load_strategy = "normal"
    
    # Headless mode args for Firefox
    #options.add_argument("--headless") 
    map_recs = []
    players = {}
    filtered_players = []
    recheck_players = set()
    records_dict = {}

    # 2. Use the Firefox Driver
    service = FirefoxService()
    driver = webdriver.Firefox(service=service, options=options)

    maps = read_json("map_info.json")

    n = 0
    print("Crawling...")
    for map in maps:
        if n >= SAMPLES:
            break
        get_map_data(driver, map["uid"], players, recheck_players, records_dict)
        n += 1

    print("Maps done, onto players")

    for pid in recheck_players:
        get_player_recs(driver, pid, records_dict)

    driver.quit()
    seen_pids = set()
    for rec in records_dict.values():
        if rec["rank"] <= 10:
            map_recs.append(rec)
            if rec["player_id"] not in seen_pids:
                filtered_players.append(players[rec["player_id"]])
                seen_pids.add(rec["player_id"])
    write_json("recs_sample.json", map_recs)
    write_json("players_sample.json", filtered_players)
    print("Done")


if __name__ == "__main__":
    scrape()