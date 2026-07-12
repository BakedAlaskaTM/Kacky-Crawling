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

def scrape():
    options = FirefoxOptions()
    options.page_load_strategy = "normal"
    
    # Headless mode args for Firefox
    options.add_argument("--headless") 

    map_recs = []
    players = []

    # 2. Use the Firefox Driver
    service = FirefoxService()
    driver = webdriver.Firefox(service=service, options=options)

    map_recs = []
    players = []

    maps = read_json("map_info.json")
    seen_players = set()
    for map in maps:
        driver.get(f"https://kackiestkacky.com/hunting/editions/maps.php?uid={map['uid']}")
        map_table = driver.find_element(By.XPATH, "//table[@id='maps']/tbody")
        retries = 0
        while retries < 50:
            rows = map_table.find_elements(By.TAG_NAME, "tr")
            if len(rows) > 1:
                break
            T.sleep(0.5)
            retries += 1
        for row in rows:
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

