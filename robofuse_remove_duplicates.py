#!/usr/bin/env python3
"""
Robofuse Duplicate Download Remover

This script identifies and removes duplicate downloads from your Real-Debrid "My Downloads" section.
It keeps only the most recent download for each unique link and deletes the rest.
It uses the same config.json as robofuse.
"""

import os
import sys
import json
import time
import requests
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from collections import defaultdict

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
            
            # Add a small delay to avoid rate limiting
            time.sleep(0.2)
        
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

def find_duplicates(downloads):
    """
    Find duplicate downloads based on the 'link' field.
    Return a list of download IDs to delete (keeping only the newest for each link).
    """
    # Group downloads by link
    link_groups = defaultdict(list)
    for download in downloads:
        link = download.get("link", "")
        if link:
            link_groups[link].append(download)
    
    # Find duplicates (groups with more than one download)
    duplicates_to_delete = []
    duplicate_count = 0
    
    for link, group in link_groups.items():
        if len(group) > 1:
            duplicate_count += len(group) - 1
            
            # Sort by generation date (newest first)
            sorted_group = sorted(
                group, 
                key=lambda x: datetime.strptime(x.get("generated", "1970-01-01T00:00:00.000Z"), 
                                               "%Y-%m-%dT%H:%M:%S.%fZ"),
                reverse=True
            )
            
            # Keep the newest, delete the rest
            for download in sorted_group[1:]:
                duplicates_to_delete.append(download)
    
    log_info(f"Found {duplicate_count} duplicates across {len([g for g in link_groups.values() if len(g) > 1])} links")
    
    return duplicates_to_delete

def main():
    parser = argparse.ArgumentParser(description="Remove duplicate downloads from Real-Debrid")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without actually deleting")
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
    
    log_info(f"Found {len(downloads)} total downloads in your Real-Debrid account.")
    
    duplicates_to_delete = find_duplicates(downloads)
    
    if not duplicates_to_delete:
        log_success("No duplicate downloads found. Your account is already clean!")
        return
    
    log_warning(f"Found {len(duplicates_to_delete)} duplicate downloads to remove.")
    
    if args.dry_run:
        log_info("DRY RUN: The following downloads would be deleted:")
        for i, download in enumerate(duplicates_to_delete[:10], 1):
            log_info(f"{i}. ID: {download['id']}, Filename: {download['filename']}, Generated: {download['generated']}")
        
        if len(duplicates_to_delete) > 10:
            log_info(f"... and {len(duplicates_to_delete) - 10} more")
        
        return
    
    if not args.force:
        confirmation = input(f"\033[93mWARNING: This will delete {len(duplicates_to_delete)} duplicate downloads from your Real-Debrid account. Are you sure? (yes/no): \033[0m")
        if confirmation.lower() not in ["yes", "y"]:
            log_info("Operation cancelled by user.")
            return
    
    log_info(f"Deleting {len(duplicates_to_delete)} duplicate downloads...")
    deleted_count = 0
    failed_count = 0
    
    # Use ThreadPoolExecutor for parallel deletion
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(
            client.delete_download, 
            [download["id"] for download in duplicates_to_delete]
        ))
    
    deleted_count = sum(1 for r in results if r)
    failed_count = sum(1 for r in results if not r)
    
    if failed_count:
        log_warning(f"Failed to delete {failed_count} downloads.")
    
    log_success(f"Successfully deleted {deleted_count} duplicate downloads from Real-Debrid.")
    log_success(f"Your account now has {len(downloads) - deleted_count} unique downloads.")

if __name__ == "__main__":
    main() 