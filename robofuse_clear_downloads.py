#!/usr/bin/env python3
"""
robofuse Download Cleaner

This script removes all downloads from your Real-Debrid "My Downloads" section.
It requires confirmation before deletion and uses the same config.json as robofuse.
"""

import os
import sys
import json
import time
import requests
import argparse
from concurrent.futures import ThreadPoolExecutor

# Set up basic logging
def log_info(message):
    print(f"\033[94m[INFO]\033[0m {message}")

def log_warning(message):
    print(f"\033[93m[WARNING]\033[0m {message}")

def log_error(message):
    print(f"\033[91m[ERROR]\033[0m {message}")

def log_success(message):
    print(f"\033[92m[SUCCESS]\033[0m {message}")

class RealDebridClient:
    """Simple client for Real-Debrid API operations."""
    
    def __init__(self, token, base_url="https://api.real-debrid.com/rest/1.0"):
        self.base_url = base_url
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def get_downloads(self, page=1):
        """Get a page of downloads from Real-Debrid."""
        response = self.session.get(f"{self.base_url}/downloads", params={"page": page})
        response.raise_for_status()
        return response.json()
    
    def get_all_downloads(self):
        """Get all downloads from Real-Debrid."""
        all_downloads = []
        page = 1
        
        while True:
            log_info(f"Fetching downloads page {page}...")
            downloads = self.get_downloads(page)
            
            if not downloads:
                break
                
            all_downloads.extend(downloads)
            page += 1
        
        return all_downloads
    
    def delete_download(self, download_id):
        """Delete a download from Real-Debrid."""
        try:
            response = self.session.delete(f"{self.base_url}/downloads/delete/{download_id}")
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            log_error(f"Failed to delete download {download_id}: {str(e)}")
            return False

def load_config():
    """Load the config file."""
    config_path = "config.json"
    
    if not os.path.exists(config_path):
        log_error(f"Config file not found: {config_path}")
        sys.exit(1)
    
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        
        if not config.get("token"):
            log_error("Real-Debrid token not found in config file")
            sys.exit(1)
        
        return config
    except json.JSONDecodeError:
        log_error(f"Invalid JSON in config file: {config_path}")
        sys.exit(1)
    except Exception as e:
        log_error(f"Error loading config: {str(e)}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Remove all downloads from Real-Debrid")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()
    
    config = load_config()
    client = RealDebridClient(config["token"])
    
    log_info("Fetching all downloads from Real-Debrid...")
    try:
        downloads = client.get_all_downloads()
    except requests.RequestException as e:
        log_error(f"Failed to fetch downloads: {str(e)}")
        sys.exit(1)
    
    if not downloads:
        log_info("No downloads found in your Real-Debrid account.")
        return
    
    log_warning(f"Found {len(downloads)} downloads in your Real-Debrid account.")
    
    if not args.force:
        confirmation = input(f"\033[93mWARNING: This will delete ALL {len(downloads)} downloads from your Real-Debrid account. Are you sure? (yes/no): \033[0m")
        if confirmation.lower() not in ["yes", "y"]:
            log_info("Operation cancelled by user.")
            return
    
    log_info(f"Deleting {len(downloads)} downloads...")
    deleted_count = 0
    failed_count = 0
    
    # Use ThreadPoolExecutor for parallel deletion
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(
            client.delete_download, 
            [download["id"] for download in downloads]
        ))
    
    deleted_count = sum(1 for r in results if r)
    failed_count = sum(1 for r in results if not r)
    
    if failed_count:
        log_warning(f"Failed to delete {failed_count} downloads.")
    
    log_success(f"Successfully deleted {deleted_count} downloads from Real-Debrid.")

if __name__ == "__main__":
    main() 