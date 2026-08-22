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

MAX_RECS = 50

def parse_time(time_str):
    if ":" not in time_str:
        return None
    m, s = time_str.split(":")
    return int(60000*int(m)+1000*float(s))

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
    options.add_argument("--headless") 
    map_recs = []
    players = {}
    filtered_players = []
    recheck_players = set()
    records_dict = {}

    # 2. Use the Firefox Driver
    service = FirefoxService()
    driver = webdriver.Firefox(service=service, options=options)

    maps = read_json("map_info.json")

    print("Crawling...")
    for map in maps:
        get_map_data(driver, map["uid"], players, recheck_players, records_dict)

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
    write_json("map_recs.json", map_recs)
    write_json("players.json", filtered_players)
    print("Done")

def insert_map_data(map_data):
    # Insert the map data into the 'Maps' table
    try:
        supabase.table('Maps').insert(map_data).execute()
    except APIError as e:
        # This is how you access the actual HTTP status code and message!
        print(f"Error Code: {e.code}")        # e.g., '42501' (Postgres error code)
        print(f"Message: {e.message}")

def update_map_data(map_data):
    # Update the player data in the 'Players' table
    try:
        supabase.table('Maps').upsert(map_data, on_conflict='uid').execute()
    except APIError as e:
        # This is how you access the actual HTTP status code and message!
        print(f"Error Code: {e.code}")        # e.g., '42501' (Postgres error code)
        print(f"Message: {e.message}")

def insert_player_data(player_data):
    # Insert the player data into the 'Players' table
    try:
        supabase.table('Players').insert(player_data).execute()
    except APIError as e:
        # This is how you access the actual HTTP status code and message!
        print(f"Error Code: {e.code}")        # e.g., '42501' (Postgres error code)
        print(f"Message: {e.message}")

def insert_records_data(recs_data):
    # Insert the records data into the 'Records' table
    try:
        supabase.table('Records').insert(recs_data).execute()
    except APIError as e:
        # This is how you access the actual HTTP status code and message!
        print(f"Error Code: {e.code}")        # e.g., '42501' (Postgres error code)
        print(f"Message: {e.message}")

def update_players(player_data):
    # Update the player data in the 'Players' table
    try:
        supabase.table('Players').upsert(player_data, on_conflict='pid').execute()
    except APIError as e:
        # This is how you access the actual HTTP status code and message!
        print(f"Error Code: {e.code}")        # e.g., '42501' (Postgres error code)
        print(f"Message: {e.message}")

def update_recs(recs_data):
    try:
        supabase.table('Records').upsert(recs_data, on_conflict='rank,map_id').execute()
    except APIError as e:
        print(f"Error Code: {e.code}")        # e.g., '42501' (Postgres error code)
        print(f"Message: {e.message}")

def GET(table_name, columns='*'):
    """
    Fetches all rows from a Supabase table, automatically paginating 
    in chunks of 1,000 rows until the entire table is retrieved.
    """
    all_data = []
    chunk_size = 1000
    start_index = 0
    
    print(f"Starting bulk fetch from table: '{table_name}'...")
    
    while True:
        end_index = start_index + chunk_size - 1
        
        try:
            # Request a specific slice of rows (e.g., 0-999, 1000-1999)
            response = (
                supabase.table(table_name)
                .select(columns)
                .range(start_index, end_index)
                .execute()
            )
            
            chunk_data = response.data
            
            # If no data is returned, we've hit the end of the table
            if not chunk_data:
                break
                
            all_data.extend(chunk_data)
            print(f"Fetched rows {start_index} to {start_index + len(chunk_data) - 1}")
            
            # Move the window forward for the next loop
            start_index += chunk_size
            
            # If the chunk returned is smaller than 1000, it was the final page
            if len(chunk_data) < chunk_size:
                break
                
        except APIError as e:
            print(f"Supabase API Error during pagination: {e.message} (Code: {e.code})")
            raise e
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            raise e
            
    print(f"Successfully fetched all {len(all_data)} rows from '{table_name}'.")
    return all_data

def export_csv():
    recs = GET("Records", "Maps(*), Players(pid, name), time, rank")
    pd.json_normalize(recs, sep='_').to_csv("rec_export.csv", index=False)

if __name__ == "__main__":
    # Load variables from .env into system environment
    load_dotenv()

    # Replace with your actual project keys from Supabase dashboard
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY") # Use service role if bypasses RLS is needed for backend

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Starting scraper...")
    scrape()
    print("Scraping completed. Now updating the database...")
    update_players(read_json("players.json"))
    update_recs(read_json("map_recs.json"))
    print("Database update completed.")
    print("Exporting to CSV")
    export_csv()
    print("Export completed.")

