#!/usr/bin/env python3
import argparse
import concurrent.futures
import hashlib
import threading
import json
import os
import requests
import sys
import time
from tqdm import tqdm
from datetime import datetime, timedelta
from collections import deque
import ui_utils
from ui_utils import LogLevel

class RateLimiter:
    """Simple rate limiter using token bucket algorithm."""
    
    def __init__(self, requests_per_minute):
        self.rate = requests_per_minute
        self.tokens = requests_per_minute
        self.last_check = datetime.now()
        self.interval = 60.0  # seconds
        self.lock = threading.Lock()
        
    def acquire(self):
        """Acquire a token, blocking if necessary."""
        with self.lock:
            now = datetime.now()
            time_passed = (now - self.last_check).total_seconds()
            self.last_check = now
            
            # Add new tokens based on time passed
            self.tokens = min(self.rate, self.tokens + time_passed * (self.rate / self.interval))
            
            if self.tokens < 1:
                # Calculate sleep time needed to get a token
                sleep_time = (1 - self.tokens) * (self.interval / self.rate)
                time.sleep(sleep_time)
                self.tokens = 1
                
            self.tokens -= 1
            return True

class RealDebridClient:
    """Client for interacting with the Real-Debrid API with rate limiting."""
    
    def __init__(self, token, base_url="https://api.real-debrid.com/rest/1.0", 
                 concurrent_requests=32, 
                 general_rate_limit=60,
                 torrents_rate_limit=25):
        self.token = token
        self.base_url = base_url
        self.concurrent_requests = concurrent_requests
        
        # Create rate limiters
        self.general_limiter = RateLimiter(general_rate_limit)
        self.torrents_limiter = RateLimiter(torrents_rate_limit)
        
        # Setup session
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def api_request_with_backoff(self, url, method="get", data=None, max_retries=5, use_torrents_limiter=False):
        """Make API requests with rate limiting and exponential backoff."""
        # Determine which rate limiter to use
        limiter = self.torrents_limiter if use_torrents_limiter else self.general_limiter
        
        # Acquire permission from rate limiter
        limiter.acquire()
        
        retry_count = 0
        while retry_count < max_retries:
            try:
                if method.lower() == "get":
                    response = self.session.get(url)
                elif method.lower() == "delete":
                    response = self.session.delete(url)
                else:
                    response = self.session.post(url, data=data)
                    
                # Check specifically for 503 Service Unavailable errors
                if response.status_code == 503:
                    print(f"Service Unavailable (503) error for URL: {url}")
                    # Let this propagate as an exception to be caught by the caller
                    response.raise_for_status()
                
                response.raise_for_status()
                return response
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limited
                    retry_after = int(e.response.headers.get('Retry-After', 1))
                    print(f"Rate limited. Retrying after {retry_after} seconds")
                    time.sleep(retry_after)
                    retry_count += 1
                elif e.response.status_code == 503:  # Service Unavailable
                    # Don't retry for 503 errors, just pass the exception up
                    print(f"Real-Debrid service unavailable (503). Hoster may be offline.")
                    raise
                else:
                    raise
            except requests.RequestException:
                wait_time = 2 ** retry_count
                print(f"Request failed. Retrying in {wait_time} seconds")
                time.sleep(wait_time)
                retry_count += 1
        
        raise Exception("Maximum retries exceeded")
    
    def get_torrents_page(self, page=1, limit=100):
        """Retrieve a single page of torrents."""
        url = f"{self.base_url}/torrents?page={page}&limit={limit}"
        try:
            # Use the torrents rate limiter
            response = self.api_request_with_backoff(url, use_torrents_limiter=True)
            if not response.text.strip():
                return []
            return response.json()
        except Exception as e:
            print(f"Error fetching torrents (page {page}): {e}")
            return []
    
    def get_all_torrents(self):
        """Retrieve all torrents by paginating through the API."""
        all_torrents = []
        page = 1
        while True:
            torrents = self.get_torrents_page(page)
            if not torrents:
                break
            print(f"Retrieved {len(torrents)} torrents from page {page}.")
            all_torrents.extend(torrents)
            page += 1
        return all_torrents
    
    def get_all_torrents_concurrent(self):
        """First fetch initial page to determine total, then fetch remaining pages concurrently."""
        print("Fetching all torrents concurrently...")
        # Get first page to determine how many torrents exist
        first_page = self.get_torrents_page(page=1)
        if not first_page:
            return []
            
        all_torrents = first_page
        
        # If there's only one page, we're done
        if len(first_page) < 100:
            return all_torrents
            
        # Otherwise, let's fetch the next few pages to get a sense of how many there might be
        # This helps us avoid creating too many unnecessary threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(self.get_torrents_page, page) for page in range(2, 5)]
            for future in concurrent.futures.as_completed(futures):
                try:
                    page_torrents = future.result()
                    if page_torrents:
                        all_torrents.extend(page_torrents)
                except Exception as e:
                    print(f"Error getting torrent page: {e}")
                    
        # If we've got less than 400 torrents after grabbing 4 pages, we probably have them all
        if len(all_torrents) < 400:
            return all_torrents
            
        # Otherwise, continue fetching with more concurrency but controlled rate limiting
        estimated_pages = (len(all_torrents) // 100) + 10  # Add some buffer
        remaining_pages = list(range(5, estimated_pages + 1))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrent_requests) as executor:
            futures = [executor.submit(self.get_torrents_page, page) for page in remaining_pages]
            for future in tqdm(concurrent.futures.as_completed(futures), 
                              total=len(futures),
                              desc="Fetching remaining torrent pages"):
                try:
                    page_torrents = future.result()
                    if page_torrents:
                        all_torrents.extend(page_torrents)
                    else:
                        # Empty page means we've reached the end
                        break
                except Exception as e:
                    print(f"Error fetching torrent page: {e}")
                    
        return all_torrents
    
    def get_downloads_page(self, page=1, limit=100):
        """Retrieve a single page of downloads."""
        url = f"{self.base_url}/downloads?page={page}&limit={limit}"
        try:
            response = self.api_request_with_backoff(url)
            if not response.text.strip():
                return []
            return response.json()
        except Exception as e:
            print(f"Error fetching downloads (page {page}): {e}")
            return []
    
    def get_all_downloads_concurrent(self):
        """Fetch all downloads concurrently using the same pattern as torrents."""
        print("Fetching all downloads concurrently...")
        # Get first page to determine how many downloads exist
        first_page = self.get_downloads_page(page=1)
        if not first_page:
            return []
            
        all_downloads = first_page
        
        # If there's only one page, we're done
        if len(first_page) < 100:
            return all_downloads
            
        # Otherwise, let's fetch the next few pages to get a sense of how many there might be
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(self.get_downloads_page, page) for page in range(2, 5)]
            for future in concurrent.futures.as_completed(futures):
                try:
                    page_downloads = future.result()
                    if page_downloads:
                        all_downloads.extend(page_downloads)
                except Exception as e:
                    print(f"Error getting downloads page: {e}")
                    
        # If we've got less than 400 downloads after grabbing 4 pages, we probably have them all
        if len(all_downloads) < 400:
            return all_downloads
            
        # Otherwise, continue fetching with more concurrency but controlled rate limiting
        estimated_pages = (len(all_downloads) // 100) + 10  # Add some buffer
        remaining_pages = list(range(5, estimated_pages + 1))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrent_requests) as executor:
            futures = [executor.submit(self.get_downloads_page, page) for page in remaining_pages]
            for future in tqdm(concurrent.futures.as_completed(futures), 
                              total=len(futures),
                              desc="Fetching remaining download pages"):
                try:
                    page_downloads = future.result()
                    if page_downloads:
                        all_downloads.extend(page_downloads)
                    else:
                        # Empty page means we've reached the end
                        break
                except Exception as e:
                    print(f"Error fetching downloads page: {e}")
                    
        return all_downloads
    
    def delete_download(self, download_id):
        """Delete a download from the downloads list."""
        url = f"{self.base_url}/downloads/delete/{download_id}"
        try:
            response = self.api_request_with_backoff(url, method="delete")
            return response.status_code == 204
        except Exception as e:
            print(f"Error deleting download {download_id}: {e}")
            return False
    
    def delete_torrent(self, torrent_id):
        """Delete a torrent from the torrents list."""
        url = f"{self.base_url}/torrents/delete/{torrent_id}"
        try:
            response = self.api_request_with_backoff(url, method="delete")
            return response.status_code == 204
        except Exception as e:
            print(f"Error deleting torrent {torrent_id}: {e}")
            return False
    
    def get_torrent_info(self, torrent_id):
        """Get detailed information about a specific torrent."""
        url = f"{self.base_url}/torrents/info/{torrent_id}"
        try:
            response = self.api_request_with_backoff(url, use_torrents_limiter=True)
            return response.json()
        except Exception as e:
            print(f"Error getting info for torrent {torrent_id}: {e}")
            return None
    
    def add_magnet(self, magnet_link, host=None):
        """Add a magnet link to download."""
        url = f"{self.base_url}/torrents/addMagnet"
        data = {"magnet": magnet_link}
        if host:
            data["host"] = host
        
        try:
            response = self.api_request_with_backoff(url, method="post", data=data, use_torrents_limiter=True)
            return response.json()
        except Exception as e:
            print(f"Error adding magnet: {e}")
            return None
    
    def select_files(self, torrent_id, file_ids="all"):
        """Select which files to download from a torrent."""
        url = f"{self.base_url}/torrents/selectFiles/{torrent_id}"
        data = {"files": file_ids}
        
        try:
            response = self.api_request_with_backoff(url, method="post", data=data, use_torrents_limiter=True)
            return response.status_code in (200, 202, 204)
        except Exception as e:
            print(f"Error selecting files for torrent {torrent_id}: {e}")
            return False
    
    def check_link(self, link):
        """Check if a link is downloadable (no auth required)."""
        url = f"{self.base_url}/unrestrict/check"
        data = {"link": link}
        
        try:
            response = self.api_request_with_backoff(url, method="post", data=data)
            return response.json()
        except Exception as e:
            if hasattr(e, 'response') and e.response.status_code == 503:
                print(f"Link unavailable: {link}")
                return {"available": False}
            print(f"Error checking link {link}: {e}")
            return None
    
    def unrestrict_link(self, rd_link, password=None):
        """Unrestrict a Real-Debrid link to get the direct download URL."""
        url = f"{self.base_url}/unrestrict/link"
        data = {"link": rd_link}
        if password:
            data["password"] = password
            
        try:
            # Use general rate limiter for unrestrict
            response = self.api_request_with_backoff(url, method="post", data=data)
            return response.json()
        except Exception as e:
            # Check specifically for 503 Service Unavailable errors
            if hasattr(e, 'response') and e.response.status_code == 503:
                print(f"Hoster unavailable for link {rd_link}: 503 Service Unavailable")
                # Return a special error indicator for 503 errors
                return {"error": "hoster_unavailable", "code": 503}
            print(f"Error unrestricting link {rd_link}: {e}")
            return None
    
    def check_if_link_alive(self, link):
        """Check if a link is still alive."""
        try:
            # We'll just do a HEAD request to see if the link is still accessible
            response = requests.head(link, timeout=10)
            return response.status_code < 400
        except Exception:
            return False
    
    def reinsert_dead_torrent(self, torrent):
        """Re-add a dead torrent to the download queue."""
        if "hash" not in torrent:
            print(f"Torrent {torrent.get('id', 'unknown')} has no hash, can't reinsert")
            return None
            
        # Create a magnet link from the hash
        magnet_link = f"magnet:?xt=urn:btih:{torrent['hash']}"
        
        # Delete the old torrent first
        if self.delete_torrent(torrent['id']):
            print(f"Deleted dead torrent: {torrent.get('filename', torrent['id'])}")
            
            # Add the new magnet
            new_torrent = self.add_magnet(magnet_link)
            if new_torrent:
                print(f"Successfully reinserted torrent: {torrent.get('filename', torrent['id'])}")
                
                # Select all files
                if self.select_files(new_torrent['id']):
                    print(f"Selected all files for reinserted torrent")
                    return new_torrent
            
        print(f"Failed to reinsert torrent: {torrent.get('filename', torrent['id'])}")
        return None


# --- Caching functions ---
def get_cache_key(torrent_id):
    """Generate a unique cache key for a torrent."""
    return hashlib.md5(torrent_id.encode()).hexdigest()

def is_cached(torrent_id, cache_dir):
    """Check if a torrent is already cached."""
    cache_path = os.path.join(cache_dir, f"{get_cache_key(torrent_id)}.json")
    return os.path.exists(cache_path)

def get_from_cache(torrent_id, cache_dir):
    """Retrieve torrent data from cache."""
    cache_path = os.path.join(cache_dir, f"{get_cache_key(torrent_id)}.json")
    try:
        with open(cache_path, 'r') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return None

def save_to_cache(torrent_id, data, cache_dir):
    """Save torrent data to cache."""
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    cache_path = os.path.join(cache_dir, f"{get_cache_key(torrent_id)}.json")
    with open(cache_path, 'w') as f:
        json.dump(data, f)

# --- Helper functions ---
def sanitize_filename(filename):
    """Returns a sanitized version of the filename."""
    return "".join(c for c in filename if c.isalnum() or c in (" ", ".", "_", "-")).rstrip()

def save_link(filename, download_link, output_dir, index=None):
    """Writes the download URL into a file, placing it in its own folder with the same name.
    
    Creates a folder structure like:
    output_dir/
      movie_name/
        movie_name.strm
    """
    safe_filename = sanitize_filename(filename)
    
    # Create the base name and file name
    if index is not None:
        base_name = f"{safe_filename}_{index}"
        strm_filename = f"{base_name}.strm"
    else:
        base_name = safe_filename
        strm_filename = f"{base_name}.strm"
    
    # Create folder with the same name as the file (without .strm extension)
    folder_path = os.path.join(output_dir, base_name)
    strm_file_path = os.path.join(folder_path, strm_filename)
    
    try:
        # Create the folder if it doesn't exist
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            ui_utils.file_status(folder_path, "success", "folder created")
        
        # Write or update the .strm file with the new link
        with open(strm_file_path, "w") as f:
            f.write(download_link)
        
        return strm_file_path
    except IOError as e:
        ui_utils.error(f"Error writing file: {e}")
        return None

def check_if_link_expired(generated_date_str=None, cached_date_str=None):
    """Check if a link is older than 6 days based on API data or local cache."""
    now = datetime.now()
    
    # If we have the API generation date, use that
    if generated_date_str:
        try:
            generated_date = datetime.fromisoformat(generated_date_str.replace('Z', '+00:00'))
            days_old = (now - generated_date).days
            return days_old >= 6  # Changed from 7 to 6 days for buffer
        except ValueError:
            pass  # If parsing fails, fall back to cache date
    
    # If we have a cached date, use that as fallback
    if cached_date_str:
        try:
            cached_date = datetime.fromisoformat(cached_date_str)
            days_old = (now - cached_date).days
            return days_old >= 6  # Changed from 7 to 6 days for buffer
        except ValueError:
            pass
    
    # If we can't determine expiration, assume it needs to be regenerated to be safe
    return True

def process_single_torrent(client, torrent, output_dir, downloads_dict, cache_dir=None):
    """Process a single torrent, considering downloads list and link expiration."""
    torrent_id = torrent.get("id")
    torrent_filename = torrent.get("filename", f"torrent_{torrent_id}")
    torrent_links = torrent.get("links", [])
    
    # Skip torrents without the "downloaded" status or links
    if torrent.get("status") != "downloaded":
        ui_utils.file_status(torrent_filename, "skipped", f"status: {torrent.get('status')}")
        return []
    
    if not torrent_links:
        ui_utils.file_status(torrent_filename, "skipped", "no links available")
        return []
    
    saved_files = []
    cached_data = None
    
    # Check cache if provided
    if cache_dir and is_cached(torrent_id, cache_dir):
        cached_data = get_from_cache(torrent_id, cache_dir)
        
    # Check if any torrent links already exist in downloads list
    existing_downloads = []
    for rd_link in torrent_links:
        link_id = rd_link.split('/')[-1]  # Extract ID from URL
        if link_id in downloads_dict:
            existing_downloads.append(downloads_dict[link_id])
    
    # If no download exists but we have cached data with non-expired links, use that
    if not existing_downloads and cached_data and 'links' in cached_data:
        current_time = datetime.now().isoformat()
        links_valid = all(not check_if_link_expired(link.get('generated'), 
                                             cached_data.get('cached_date')) 
                        for link in cached_data['links'])
        
        if links_valid:
            ui_utils.file_status(torrent_filename, "success", "using cached links")
            for cached_link in cached_data['links']:
                if cached_link.get('streamable') == 1 and cached_link.get('download'):
                    download_url = cached_link['download']
                    file_name = cached_link.get('filename', torrent_filename)
                    saved_path = save_link(file_name, download_url, output_dir)
                    if saved_path:
                        saved_files.append(saved_path)
            
            if saved_files:
                return saved_files
    
    # Process existing downloads first if they're valid
    if existing_downloads:
        for download in existing_downloads:
            # Check if existing unrestricted link exists and is not expired
            if 'link' in download:
                ui_utils.file_status(torrent_filename, "processing", "checking link")
                result = client.unrestrict_link(download['link'])
                
                # Check for hoster unavailable error
                if result and result.get('error') == 'hoster_unavailable':
                    ui_utils.file_status(torrent_filename, "error", "hoster unavailable, needs reinsertion")
                    # Return a special marker that this torrent needs reinsertion
                    return {"needs_reinsertion": True, "torrent": torrent}
                
                if result and 'download' in result and result.get('streamable') == 1:
                    # Check if the link is expired based on generation date
                    generated_date = result.get('generated')
                    
                    if check_if_link_expired(generated_date, None):
                        ui_utils.file_status(torrent_filename, "processing", "link expired, regenerating")
                        # Delete the old download if expired
                        client.delete_download(download['id'])
                    else:
                        # Link is still valid
                        file_name = download.get('filename', torrent_filename)
                        download_url = result['download']
                        saved_path = save_link(file_name, download_url, output_dir)
                        if saved_path:
                            saved_files.append(saved_path)
                            
                            # Cache this data
                            if cache_dir:
                                cache_data = {
                                    'links': [result],
                                    'saved_files': [saved_path],
                                    'cached_date': datetime.now().isoformat()
                                }
                                save_to_cache(torrent_id, cache_data, cache_dir)
                            
                            continue
                
                # If we got here, the link needs to be regenerated
                client.delete_download(download['id'])
    
    # At this point, either we have no downloads or they're all invalid/expired
    # We need to unrestrict each torrent link
    new_links = []
    hoster_unavailable = False
    
    for link_index, rd_link in enumerate(torrent_links, start=1):
        ui_utils.file_status(torrent_filename, "processing", f"unrestricting link {link_index}/{len(torrent_links)}")
        result = client.unrestrict_link(rd_link)
        
        # Check for hoster unavailable
        if result and result.get('error') == 'hoster_unavailable':
            ui_utils.file_status(torrent_filename, "error", "hoster unavailable, needs reinsertion")
            hoster_unavailable = True
            break
        
        if not result or 'download' not in result:
            ui_utils.file_status(torrent_filename, "error", f"failed to unrestrict link {link_index}")
            continue
            
        # Only use streamable links
        if result.get('streamable') != 1:
            ui_utils.file_status(torrent_filename, "skipped", "non-streamable link")
            continue
            
        # Use the returned filename if available; otherwise, fall back on torrent_filename
        file_name = result.get("filename", torrent_filename)
        download_url = result.get("download")
        
        if download_url:
            index_arg = link_index if len(torrent_links) > 1 else None
            saved_path = save_link(file_name, download_url, output_dir, index=index_arg)
            if saved_path:
                saved_files.append(saved_path)
                new_links.append(result)
    
    # If we encountered a hoster unavailable error, mark this torrent for reinsertion
    if hoster_unavailable:
        return {"needs_reinsertion": True, "torrent": torrent}
    
    # Cache the results
    if cache_dir and new_links:
        cache_data = {
            'links': new_links,
            'saved_files': saved_files,
            'cached_date': datetime.now().isoformat()
        }
        save_to_cache(torrent_id, cache_data, cache_dir)
        
    return saved_files

def check_torrent_health(client, torrent):
    """Check if a torrent is healthy (accessible).
    
    A torrent is considered healthy if its status is "downloaded".
    A torrent is considered unhealthy if its status is "dead".
    """
    # Simply check the status field directly
    if torrent.get('status') == 'downloaded':
        return True
    elif torrent.get('status') == 'dead':
        ui_utils.file_status(torrent.get('filename', torrent['id']), "error", "dead torrent")
        return False
    else:
        # For any other status, consider it as in progress or in error state
        # but not a candidate for reinsertion
        ui_utils.file_status(torrent.get('filename', torrent['id']), "skipped", f"status: {torrent.get('status')}")
        return True

def process_torrents_concurrent(client, torrents, output_dir, cache_dir=None, downloads=None, skip_health_check=False):
    """Process torrents concurrently with healthchecks and expiration checks."""
    saved_paths = []
    
    # First, get all downloads and organize them for faster lookup
    if downloads is None:
        downloads = client.get_all_downloads_concurrent()
    
    downloads_dict = {}
    for download in downloads:
        # Use the ID as the key for quick lookup
        download_id = download.get('id')
        if download_id:
            downloads_dict[download_id] = download
    
    ui_utils.info(f"Found {len(downloads_dict)} downloads in your account")
    
    # Keep track of reinserted torrents
    reinserted_torrents = []
    stats = {
        "total_torrents": len(torrents),
        "healthy_torrents": 0,
        "unhealthy_torrents": 0,
        "reinserted_torrents": 0,
        "skipped_torrents": 0,
        "torrent_process_time": 0,
        "health_check_time": 0,
        "saved_paths": 0,
        "cached_torrents": 0,
        "torrents_with_errors": 0
    }
    
    # First, check health of each torrent if not skipped
    unhealthy_torrents = []
    
    if not skip_health_check:
        ui_utils.info("Checking torrent health...")
        health_start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=client.concurrent_requests) as executor:
            future_to_torrent = {
                executor.submit(check_torrent_health, client, torrent): torrent
                for torrent in torrents if torrent.get('status') == 'downloaded'
            }
            
            for future in ui_utils.spinner("Checking torrent health", 
                                          concurrent.futures.as_completed(future_to_torrent)):
                torrent = future_to_torrent[future]
                try:
                    is_healthy = future.result()
                    if not is_healthy:
                        stats["unhealthy_torrents"] += 1
                        unhealthy_torrents.append(torrent)
                    else:
                        stats["healthy_torrents"] += 1
                except Exception as e:
                    ui_utils.error(f"Error checking health for torrent {torrent.get('filename', 'unknown')}: {e}")
                    stats["torrents_with_errors"] += 1
        
        stats["health_check_time"] = time.time() - health_start_time
        
        # Try to reinsert unhealthy torrents
        if unhealthy_torrents:
            ui_utils.warning(f"Attempting to reinsert {len(unhealthy_torrents)} unhealthy torrents...")
            
            for torrent in ui_utils.spinner("Reinserting torrents", unhealthy_torrents):
                new_torrent = client.reinsert_dead_torrent(torrent)
                if new_torrent:
                    reinserted_torrents.append(new_torrent)
                    stats["reinserted_torrents"] += 1
    else:
        ui_utils.info("Health checks skipped.")
        stats["skipped_torrents"] = len([t for t in torrents if t.get('status') != 'downloaded'])
        stats["healthy_torrents"] = len([t for t in torrents if t.get('status') == 'downloaded'])
    
    # Combine original healthy torrents with reinserted ones
    healthy_torrents = [t for t in torrents if t not in unhealthy_torrents] + reinserted_torrents
    
    # Process healthy torrents and reinserted torrents concurrently
    ui_utils.info(f"Processing {len(healthy_torrents)} torrents...")
    
    torrents_to_reinsert = []
    process_start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=client.concurrent_requests) as executor:
        future_to_torrent = {
            executor.submit(process_single_torrent, client, torrent, output_dir, downloads_dict, cache_dir): torrent
            for torrent in healthy_torrents
        }
        
        for future in ui_utils.spinner("Processing torrents", concurrent.futures.as_completed(future_to_torrent)):
            torrent = future_to_torrent[future]
            try:
                results = future.result()
                # Check if this torrent needs reinsertion due to 503 error
                if isinstance(results, dict) and results.get('needs_reinsertion'):
                    ui_utils.warning(f"Marking torrent for reinsertion due to hoster unavailability: {torrent.get('filename', torrent['id'])}")
                    torrents_to_reinsert.append(results.get('torrent'))
                else:
                    if cache_dir and is_cached(torrent.get('id'), cache_dir):
                        stats["cached_torrents"] += 1
                    saved_paths.extend(results)
                    stats["saved_paths"] += len(results)
            except Exception as e:
                ui_utils.error(f"Error processing torrent {torrent.get('filename', 'unknown')}: {e}")
                stats["torrents_with_errors"] += 1
    
    stats["torrent_process_time"] = time.time() - process_start_time
    
    # Handle any torrents that need reinsertion due to 503 errors
    if torrents_to_reinsert:
        ui_utils.warning(f"\nAttempting to reinsert {len(torrents_to_reinsert)} torrents with hoster unavailability...")
        
        for torrent in ui_utils.spinner("Reinserting torrents with unavailable hosters", torrents_to_reinsert):
            new_torrent = client.reinsert_dead_torrent(torrent)
            if new_torrent:
                reinserted_torrents.append(new_torrent)
                stats["reinserted_torrents"] += 1
                
                # Process the reinserted torrent immediately
                ui_utils.info(f"Processing reinserted torrent: {new_torrent.get('filename', new_torrent['id'])}")
                try:
                    results = process_single_torrent(client, new_torrent, output_dir, downloads_dict, cache_dir)
                    if not isinstance(results, dict):  # Ensure it's not another reinsertion request
                        saved_paths.extend(results)
                        stats["saved_paths"] += len(results)
                except Exception as e:
                    ui_utils.error(f"Error processing reinserted torrent: {e}")
                    stats["torrents_with_errors"] += 1
    
    # Report on reinserted torrents
    if reinserted_torrents:
        ui_utils.success(f"\nSuccessfully reinserted {len(reinserted_torrents)} torrents")
    
    # Add the statistics object to the return value
    return {"saved_paths": saved_paths, "stats": stats}

def load_config():
    """Load configuration from config file or environment variables."""
    # Default config
    config = {
        "token": os.environ.get("REALDEBRID_TOKEN"),
        "limit": int(os.environ.get("REALDEBRID_LIMIT", 100)),
        "concurrent_requests": int(os.environ.get("REALDEBRID_CONCURRENT", 32)),
        "general_rate_limit": int(os.environ.get("REALDEBRID_GENERAL_RATE_LIMIT", 60)),
        "torrents_rate_limit": int(os.environ.get("REALDEBRID_TORRENTS_RATE_LIMIT", 25)),
        "output_dir": os.environ.get("REALDEBRID_OUTPUT_DIR", ""),
        "cache_dir": os.environ.get("REALDEBRID_CACHE_DIR", "")
    }
    
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    
    # Try loading from config file in script directory
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                file_config = json.load(f)
                config.update(file_config)
            print(f"Loaded configuration from {config_path}")
        except Exception as e:
            print(f"Error loading config file: {e}")
    
    # Also try loading from ~/.config/robofuse/config.json if it exists
    user_config_path = os.path.expanduser("~/.config/robofuse/config.json")
    if os.path.exists(user_config_path):
        try:
            with open(user_config_path, 'r') as f:
                user_config = json.load(f)
                # User config overrides script directory config
                config.update(user_config)
            print(f"Loaded user configuration from {user_config_path}")
        except Exception as e:
            print(f"Error loading user config file: {e}")
    
    return config

# --- Main Program ---
def main():
    parser = argparse.ArgumentParser(description="Download direct links for all torrents in your Real-Debrid account.")
    parser.add_argument("--output-dir", help="Directory to save the files containing download links.")
    parser.add_argument("--cache-dir", help="Directory for caching torrent data to avoid reprocessing.")
    parser.add_argument("--concurrent", type=int, help="Number of concurrent requests (default: from config or 32)")
    parser.add_argument("--general-rate-limit", type=int, help="General API rate limit per minute (default: from config or 60)")
    parser.add_argument("--torrents-rate-limit", type=int, help="Torrents API rate limit per minute (default: from config or 25)")
    parser.add_argument("--skip-health-check", action="store_true", help="Skip health checks for torrents and links")
    parser.add_argument("--verbose", action="store_true", help="Show detailed debug information")
    parser.add_argument("--quiet", action="store_true", help="Show minimal output")
    args = parser.parse_args()

    # Set the log level based on arguments
    if args.verbose:
        ui_utils.set_log_level(LogLevel.DEBUG)
    elif args.quiet:
        ui_utils.set_log_level(LogLevel.WARNING)
    else:
        ui_utils.set_log_level(LogLevel.INFO)

    # Load configuration
    config = load_config()
    token = config["token"]
    
    if not token:
        ui_utils.error("Please set your REALDEBRID_TOKEN environment variable or include it in your config file.")
        sys.exit(1)

    # Use config file values as defaults, but override with command line arguments if provided
    output_dir = args.output_dir or config.get("output_dir")
    cache_dir = args.cache_dir or config.get("cache_dir")
    
    if not output_dir:
        ui_utils.error("Please specify an output directory with --output-dir or in your config file.")
        sys.exit(1)
        
    # Override config with command line arguments if provided
    if args.concurrent:
        config["concurrent_requests"] = args.concurrent
    if args.general_rate_limit:
        config["general_rate_limit"] = args.general_rate_limit
    if args.torrents_rate_limit:
        config["torrents_rate_limit"] = args.torrents_rate_limit
        
    # Ensure the output directory exists
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            ui_utils.success(f"Created output directory: {output_dir}")
        except OSError as e:
            ui_utils.error(f"Error creating directory {output_dir}: {e}")
            sys.exit(1)

    # Create cache directory if specified
    if cache_dir and not os.path.exists(cache_dir):
        try:
            os.makedirs(cache_dir)
            ui_utils.success(f"Created cache directory: {cache_dir}")
        except OSError as e:
            ui_utils.error(f"Error creating cache directory {cache_dir}: {e}")
            cache_dir = None

    # Initialize the Real-Debrid client with rate limiting
    client = RealDebridClient(
        token=token, 
        concurrent_requests=config["concurrent_requests"],
        general_rate_limit=config["general_rate_limit"],
        torrents_rate_limit=config["torrents_rate_limit"]
    )

    # Display configuration
    config_items = {
        "Concurrent workers": config['concurrent_requests'],
        "General API rate limit": f"{config['general_rate_limit']} requests/minute",
        "Torrents API rate limit": f"{config['torrents_rate_limit']} requests/minute",
        "Health checks": 'Disabled' if args.skip_health_check else 'Enabled',
        "Output directory": output_dir,
        "Cache directory": cache_dir or "Not used",
        "Verbosity": "Debug" if args.verbose else ("Quiet" if args.quiet else "Normal")
    }
    
    # Only show the configuration summary if not in quiet mode
    if not args.quiet:
        ui_utils.print_summary_box("Configuration", config_items)
    
    # Retrieve all downloads first
    ui_utils.info("\nRetrieving downloads from Real-Debrid...")
    start_time = time.time()
    downloads = client.get_all_downloads_concurrent()
    fetch_time = time.time() - start_time
    ui_utils.success(f"\nRetrieved {len(downloads)} download(s) in {ui_utils.format_time(fetch_time)}")
    
    # Retrieve all torrents
    ui_utils.info("\nRetrieving torrents from Real-Debrid...")
    start_time = time.time()
    torrents = client.get_all_torrents_concurrent()
    fetch_time = time.time() - start_time
    total = len(torrents)
    
    # Filter for only downloaded torrents
    downloaded_torrents = [t for t in torrents if t.get('status') == 'downloaded']
    ui_utils.success(f"\nRetrieved {total} torrent(s) in {ui_utils.format_time(fetch_time)}")
    ui_utils.info(f"Found {len(downloaded_torrents)} downloaded torrents out of {total} total")
    
    if not downloaded_torrents:
        ui_utils.error("No downloaded torrents found. Exiting.")
        return
    
    # Process torrents concurrently with health checks if enabled
    ui_utils.info("\nProcessing torrents to extract download links...")
    process_start = time.time()
    
    results = process_torrents_concurrent(
        client, 
        downloaded_torrents, 
        output_dir, 
        cache_dir,
        downloads,
        args.skip_health_check
    )
    
    saved_paths = results["saved_paths"]
    stats = results["stats"]
    
    process_time = time.time() - process_start
    
    # Summary statistics
    summary_items = {
        "Total torrents processed": len(downloaded_torrents),
        "Total download links saved": len(saved_paths),
        "Healthy torrents": stats["healthy_torrents"],
        "Unhealthy torrents": stats["unhealthy_torrents"],
        "Reinserted torrents": stats["reinserted_torrents"],
        "Torrents with errors": stats["torrents_with_errors"],
        "Torrents using cache": stats["cached_torrents"],
        "Health check time": ui_utils.format_time(stats["health_check_time"]),
        "Processing time": ui_utils.format_time(stats["torrent_process_time"]),
        "Average per torrent": ui_utils.format_time(process_time/max(1, len(downloaded_torrents))),
        "Total runtime": ui_utils.format_time(process_time + fetch_time)
    }
    ui_utils.print_summary_box("Processing Summary", summary_items)

if __name__ == "__main__":
    main()