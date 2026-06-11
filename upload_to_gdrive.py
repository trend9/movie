import os
import sys
import json
import glob
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def upload_videos():
    # 1. Load SA JSON
    sa_json_str = os.environ.get("GDRIVE_SA_JSON")
    if not sa_json_str:
        print("Error: GDRIVE_SA_JSON environment variable is not set.")
        sys.exit(1)
        
    try:
        info = json.loads(sa_json_str)
    except Exception as e:
        print(f"Error parsing GDRIVE_SA_JSON: {e}")
        sys.exit(1)
        
    # 2. Authenticate
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    )
    service = build("drive", "v3", credentials=creds)
    
    # 3. Get folder ID (optional, default to root or search)
    folder_id = os.environ.get("GDRIVE_FOLDER_ID")
    
    # Find all mp4 files in output_action
    mp4_files = glob.glob(os.path.join("output_action", "*.mp4"))
    if not mp4_files:
        print("No MP4 files found in output_action/")
        return
        
    for filepath in mp4_files:
        filename = os.path.basename(filepath)
        print(f"Checking if {filename} is already on Google Drive...")
        
        query = f"name = '{filename}' and trashed = false"
        if folder_id:
            query += f" and '{folder_id}' in parents"
            
        try:
            results = service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
            files = results.get("files", [])
        except Exception as e:
            print(f"Error checking file presence on Google Drive: {e}")
            files = []
        
        if files:
            print(f"File {filename} already exists on Google Drive (ID: {files[0]['id']}). Skipping.")
            continue
            
        print(f"Uploading {filename} to Google Drive...")
        file_metadata = {"name": filename}
        if folder_id:
            file_metadata["parents"] = [folder_id]
            
        media = MediaFileUpload(filepath, mimetype="video/mp4", resumable=True)
        try:
            file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
            print(f"Successfully uploaded! File ID: {file.get('id')}")
        except Exception as e:
            print(f"Failed to upload {filename}: {e}")

if __name__ == "__main__":
    upload_videos()
