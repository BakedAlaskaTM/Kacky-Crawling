import os
from postgrest.exceptions import APIError
from supabase import create_client, Client
import json
from dotenv import load_dotenv

# Load variables from .env into system environment
load_dotenv()

# Replace with your actual project keys from Supabase dashboard
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY") # Use service role if bypasses RLS is needed for backend

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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

def insert_map_data(map_data):
    # Insert the map data into the 'Maps' table
    try:
        supabase.table('Maps').insert(map_data).execute()
    except APIError as e:
        # This is how you access the actual HTTP status code and message!
        print(f"Error Code: {e.code}")        # e.g., '42501' (Postgres error code)
        print(f"Message: {e.message}")

