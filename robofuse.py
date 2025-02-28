#!/usr/bin/env python3
import argparse
import concurrent.futures
import hashlib
import threading
import json
import os
import re
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

def is_skip_file(filename):
    """
    Detect sample files and extras to skip processing
    Returns True if file should be skipped, False otherwise
    """
    # Check if this is an extra content and what type
    extras_type = classify_extra_content(filename)
    if extras_type:
        ui_utils.file_status(filename, "skipped", f"extra content: {extras_type}")
        return True
    
    # Sample file patterns
    sample_patterns = [
        r'(?i)[-_\.\s]sample[-_\.\s]',
        r'(?i)^sample[-_\.\s]',
        r'(?i)[-_\.\s]sample$',
        r'(?i)sample\.',
        r'(?i)[\[\(]sample[\]\)]'
    ]
    
    # Check against sample patterns
    for pattern in sample_patterns:
        if re.search(pattern, filename):
            ui_utils.file_status(filename, "skipped", "sample file")
            return True
    
    return False

def classify_extra_content(filename):
    """
    More detailed detection of extra content with categorization.
    
    Returns:
        str or None: The category of extra content, or None if not an extra
    """
    # Special case: Don't classify Extended Cut movies as extras
    # Common patterns for legitimate extended movies (not extras)
    extended_movie_patterns = [
        r'(?i)extended[\.\s]+(cut|edition|version)',  # Extended Cut, Extended Edition, Extended Version
        r'(?i)[\.\s]extended[\.\s]+', # .Extended. or "Extended" with spaces
        r'(?i)[\.\s]extended$',  # Ending with Extended
        r'(?i)extended[\.\s]+(bluray|uhd|2160p|1080p)' # Extended followed by quality indicators
    ]
    
    if any(re.search(pattern, filename) for pattern in extended_movie_patterns):
        return None
    
    extras_categories = {
        "trailer": [
            r'(?i)[-_\.\s]trailer[-_\.\s]', 
            r'(?i)[-_\.\s]teaser[-_\.\s]',
            r'(?i)[\[\(]trailer[\]\)]'
        ],
        "deleted_scene": [
            r'(?i)[-_\.\s]deleted[-_\.\s]scene', 
            r'(?i)[-_\.\s]deleted[-_\.\s]',
            r'(?i)[-_\.\s]removal[-_\.\s]'
        ],
        "interview": [
            r'(?i)[-_\.\s]interview[-_\.\s]', 
            r'(?i)[-_\.\s]cast[-_\.\s]',
            r'(?i)[-_\.\s]press[-_\.\s]'
        ],
        "behind_scenes": [
            r'(?i)[-_\.\s]behind[-_\.\s]the[-_\.\s]scenes[-_\.\s]', 
            r'(?i)[-_\.\s]making[-_\.\s]of[-_\.\s]', 
            r'(?i)[-_\.\s]bts[-_\.\s]'
        ],
        "featurette": [
            r'(?i)[-_\.\s]featurette[-_\.\s]', 
            r'(?i)[-_\.\s]short[-_\.\s]'
        ],
        "extra": [
            # Be more specific to avoid matching movie titles containing these words
            r'(?i)[-_\.\s](extra|extras)[-_\.\s]',  # More specific pattern 
            r'(?i)[-_\.\s]bonus[-_\.\s](feature|content|material)',
            r'(?i)[-_\.\s]special[-_\.\s]feature[-_\.\s]'
        ],
        "commentary": [
            r'(?i)[-_\.\s]commentary[-_\.\s]',
            r'(?i)[-_\.\s]blooper[-_\.\s]', 
            r'(?i)[-_\.\s]gag[-_\.\s]reel[-_\.\s]'
        ],
        "unrated": [
            # Specific unrated scenes, not full movies
            r'(?i)[-_\.\s]unrated[-_\.\s]scene', 
            r'(?i)[-_\.\s]uncensored[-_\.\s]scene'
        ]
    }
    
    # Special case for unrated movies (not extras)
    if re.search(r'(?i)unrated[\.\s]+(cut|edition|bluray|uhd|2160p|1080p)', filename):
        return None
        
    # Check against patterns and return category if matched
    for category, patterns in extras_categories.items():
        if any(re.search(pattern, filename) for pattern in patterns):
            return category
    
    return None  # Not an extra

def should_skip_content(strm_path, download_url):
    """
    Determine if we should skip creating this file
    by checking if content already exists in different folders
    
    Args:
        strm_path: Path of the .strm file to be created
        download_url: URL to be written to the file
        
    Returns:
        bool: True if content already exists and should be skipped, False otherwise
    """
    # 1. Check if the exact file exists with the same content
    if os.path.exists(strm_path):
        try:
            with open(strm_path, "r") as f:
                existing_content = f.read().strip()
            
            if existing_content == download_url.strip():
                return True
        except Exception:
            pass
    
    # 2. Check for same content in different folders
    filename = os.path.basename(strm_path)
    
    # For TV Shows, look in all TV Show directories
    if "TV Shows" in strm_path:
        parent_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(strm_path))), "TV Shows")
        
        # Extract episode information (SxxExx) from the filename to match similar files
        episode_match = re.search(r'[Ss](\d{1,2})[Ee](\d{1,2})', filename)
        
        if episode_match:
            episode_pattern = f"S{int(episode_match.group(1)):02d}E{int(episode_match.group(2)):02d}"
            
            # Walk through TV Shows directory to find matching episodes
            for root, dirs, files in os.walk(parent_dir):
                for file in files:
                    if episode_pattern in file and file.endswith(".strm"):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, "r") as f:
                                content = f.read().strip()
                            
                            if content == download_url.strip():
                                ui_utils.file_status(strm_path, "skipped", f"equivalent exists at {file_path}")
                                return True
                        except Exception:
                            continue
    
    # For Movies, look in all Movie directories
    elif "Movies" in strm_path:
        parent_dir = os.path.join(os.path.dirname(os.path.dirname(strm_path)), "Movies")
        
        # Use filename without extension for comparison (movie.strm)
        base_name_without_ext = os.path.splitext(filename)[0]
        
        # For movies, we'll need to be more careful due to potential false positives
        # We'll check for files with the same download URL
        for root, dirs, files in os.walk(parent_dir):
            for file in files:
                if file.endswith(".strm"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r") as f:
                            content = f.read().strip()
                        
                        if content == download_url.strip():
                            ui_utils.file_status(strm_path, "skipped", f"equivalent exists at {file_path}")
                            return True
                    except Exception:
                        continue
    
    return False

def save_link(filename, download_link, output_dir, index=None):
    """Writes the download URL into a file, placing it in the appropriate folder structure.
    
    Creates a folder structure like:
    For Movies:
    output_dir/
      Movies/
        movie_name/
          movie_name.strm
        
    For TV Shows:
    output_dir/
      TV Shows/
        series_name/
          Season X/
            series_name.SXXEXX.strm
    """
    # Check if this is an extra that should be organized rather than skipped
    extras_type = classify_extra_content(filename)
    
    # Skip sample files 
    if is_skip_file(filename):
        # Return a special marker indicating this was skipped as an extra
        return "skipped_extra"
        
    safe_filename = sanitize_filename(filename)
    
    # Create the base name and file name
    if index is not None:
        base_name = f"{safe_filename}_{index}"
        strm_filename = f"{base_name}.strm"
    else:
        base_name = safe_filename
        strm_filename = f"{base_name}.strm"
    
    # Check if this is a TV show episode
    tv_show_info = parse_tv_show_filename(filename)
    
    if tv_show_info:
        # This is a TV show episode
        series_name, season_num, episode_num = tv_show_info
        
        # Create folder structure: TV Shows/series_name/Season X/
        tv_shows_folder = os.path.join(output_dir, "TV Shows")
        series_folder = os.path.join(tv_shows_folder, sanitize_filename(series_name))
        
        # If this is an extra, put it in the Extras folder
        if extras_type:
            extras_folder = os.path.join(series_folder, "Extras")
            extras_type_folder = os.path.join(extras_folder, extras_type.capitalize())
            season_folder = extras_type_folder
            
            # Create the extras folders if they don't exist
            if not os.path.exists(extras_folder):
                os.makedirs(extras_folder)
                ui_utils.file_status(extras_folder, "success", "extras folder created")
                
            if not os.path.exists(extras_type_folder):
                os.makedirs(extras_type_folder)
                ui_utils.file_status(extras_type_folder, "success", f"{extras_type} folder created")
                
            # Use a different filename format for extras
            strm_filename = f"{sanitize_filename(series_name)}_extra_{base_name}.strm"
        else:
            # Normal episode
            season_folder = os.path.join(series_folder, f"Season {season_num}")
        
        # Create folders if they don't exist
        if not os.path.exists(tv_shows_folder):
            os.makedirs(tv_shows_folder)
            ui_utils.file_status(tv_shows_folder, "success", "TV Shows folder created")
            
        if not os.path.exists(series_folder):
            os.makedirs(series_folder)
            ui_utils.file_status(series_folder, "success", "series folder created")
            
        if not os.path.exists(season_folder):
            os.makedirs(season_folder)
            ui_utils.file_status(season_folder, "success", "season folder created")
        
        # Create more descriptive strm filename with show info
        if not extras_type:  # Only use the standard format for regular episodes
            strm_filename = f"{sanitize_filename(series_name)}.S{season_num:02d}E{episode_num:02d}.strm"
        
        # Create the .strm file in the season folder
        strm_file_path = os.path.join(season_folder, strm_filename)
    else:
        # This is a movie or unknown format - use the Movies folder
        movies_folder = os.path.join(output_dir, "Movies")
        movie_folder = os.path.join(movies_folder, base_name)
        
        # If this is an extra, put it in the Extras folder
        if extras_type:
            extras_folder = os.path.join(movie_folder, "Extras")
            extras_type_folder = os.path.join(extras_folder, extras_type.capitalize())
            target_folder = extras_type_folder
            
            # Create the extras folders if they don't exist
            if not os.path.exists(extras_folder):
                os.makedirs(extras_folder)
                ui_utils.file_status(extras_folder, "success", "extras folder created")
                
            if not os.path.exists(extras_type_folder):
                os.makedirs(extras_type_folder)
                ui_utils.file_status(extras_type_folder, "success", f"{extras_type} folder created")
                
            # Use a different filename format for extras
            strm_filename = f"{base_name}_extra_{extras_type}.strm"
        else:
            # Normal movie
            target_folder = movie_folder
        
        # Create the folders if they don't exist
        if not os.path.exists(movies_folder):
            os.makedirs(movies_folder)
            ui_utils.file_status(movies_folder, "success", "Movies folder created")
            
        if not os.path.exists(movie_folder):
            os.makedirs(movie_folder)
            ui_utils.file_status(movie_folder, "success", "movie folder created")
            
        if extras_type and not os.path.exists(target_folder):
            os.makedirs(target_folder)
            ui_utils.file_status(target_folder, "success", f"{extras_type} folder created")
        
        strm_file_path = os.path.join(target_folder, strm_filename)
    
    # Enhanced check for existing content across all directories
    if should_skip_content(strm_file_path, download_link):
        return strm_file_path
    
    try:
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
            # Replace Z with +00:00 to make it compatible with fromisoformat
            generated_date = datetime.fromisoformat(generated_date_str.replace('Z', '+00:00'))
            # Convert to naive datetime by removing timezone info for comparison
            if generated_date.tzinfo:
                generated_date = generated_date.replace(tzinfo=None) - timedelta(hours=generated_date.tzinfo.utcoffset(generated_date).total_seconds() / 3600)
            days_old = (now - generated_date).days
            return days_old >= 6  # Changed from 7 to 6 days for buffer
        except ValueError as e:
            pass  # If parsing fails, fall back to cache date
    
    # If we have a cached date, use that as fallback
    if cached_date_str:
        try:
            cached_date = datetime.fromisoformat(cached_date_str)
            # Ensure cached_date is timezone naive for comparison
            if cached_date.tzinfo:
                cached_date = cached_date.replace(tzinfo=None) - timedelta(hours=cached_date.tzinfo.utcoffset(cached_date).total_seconds() / 3600)
            days_old = (now - cached_date).days
            return days_old >= 6  # Changed from 7 to 6 days for buffer
        except ValueError:
            pass
    
    # If we can't determine expiration, assume it needs to be regenerated to be safe
    return True

def process_single_torrent(client, torrent, output_dir, downloads_dict, cache_dir=None):
    """Process a single torrent, considering downloads list and link expiration."""
    # Ensure we're working with a dictionary
    if not isinstance(torrent, dict):
        ui_utils.error(f"Torrent is not a dictionary but {type(torrent)}")
        return []
        
    torrent_id = torrent.get("id")
    torrent_filename = torrent.get("filename", f"torrent_{torrent_id}")
    torrent_links = torrent.get("links", [])
    
    # Check if links is a string and convert to list if needed
    if isinstance(torrent_links, str):
        ui_utils.warning(f"Torrent {torrent_id} has a string for links instead of a list. Converting.")
        torrent_links = [torrent_links]
        # Also update the torrent dictionary
        torrent["links"] = torrent_links
    
    # Skip torrents without the "downloaded" status or links
    if torrent.get("status") != "downloaded":
        ui_utils.file_status(torrent_filename, "skipped", f"status: {torrent.get('status')}")
        return []
    
    if not torrent_links:
        ui_utils.file_status(torrent_filename, "skipped", "no links available")
        return []
    
    saved_files = []
    skipped_extras_count = 0
    cached_data = None
    
    # Check cache if provided
    if cache_dir and is_cached(torrent_id, cache_dir):
        cached_data = get_from_cache(torrent_id, cache_dir)
        
    # Ensure downloads_dict is a dictionary
    if not isinstance(downloads_dict, dict):
        ui_utils.warning(f"downloads_dict is not a dictionary but {type(downloads_dict)}. Using empty dict.")
        downloads_dict = {}
        
    # Create a reverse lookup from links to download objects
    # For each link, keep the most recent valid download
    link_to_download = {}
    for download_id, download in downloads_dict.items():
        # Ensure download is a dictionary
        if not isinstance(download, dict):
            ui_utils.warning(f"Skipping non-dict download: {type(download)}")
            continue
            
        if 'link' in download:
            link = download['link']
            
            # If we haven't seen this link before, add it
            if link not in link_to_download:
                link_to_download[link] = download
            # If we have seen it, keep the one with the most recent generation date
            elif 'generated' in download and 'generated' in link_to_download[link]:
                try:
                    current_date = datetime.fromisoformat(link_to_download[link]['generated'].replace('Z', '+00:00'))
                    new_date = datetime.fromisoformat(download['generated'].replace('Z', '+00:00'))
                    
                    if new_date > current_date:
                        # Use debug log level for "Found newer download" messages
                        ui_utils.debug(f"Found newer download for link {link} ({new_date} vs {current_date})")
                        link_to_download[link] = download
                except ValueError:
                    # If date parsing fails, keep the current one
                    pass
    
    # Check if any torrent links already exist in downloads list
    existing_downloads = []
    for rd_link in torrent_links:
        # Skip if not a string
        if not isinstance(rd_link, str):
            ui_utils.warning(f"Skipping non-string link: {type(rd_link)}")
            continue
        
        # Use the full link to look up in our map
        if rd_link in link_to_download:
            existing_downloads.append(link_to_download[rd_link])
    
    for idx, link in enumerate(torrent["links"]):
        link_id = link
        
        # Check if download already exists for this link
        existing_download = link_to_download.get(link)
        
        if existing_download:
            # Use the existing download if it has all required fields
            has_download_url = "download" in existing_download
            has_mtime = "generated" in existing_download
            
            if has_download_url and has_mtime:
                # Check if the link is expired
                if check_if_link_expired(existing_download["generated"]):
                    if ui_utils.verbose:
                        print(f"Existing download is expired, recreating: {existing_download['filename']}")
                    # Delete the old download to avoid cluttering the downloads list
                    client.delete_download(existing_download["id"])
                else:
                    # Use the existing download URL
                    if ui_utils.verbose:
                        print(f"Using existing download: {existing_download['filename']}")
                    
                    download_url = existing_download["download"]
                    filename = sanitize_filename(existing_download["filename"])
                    
                    save_result = save_link(filename, download_url, output_dir, idx)
                    if save_result:
                        saved_files.append(save_result)
                    else:
                        # Count skipped extra content
                        is_extra = classify_extra_content(filename)
                        if is_extra:
                            skipped_extras_count += 1
                    continue
        
        # If we get here, we need to unrestrict the link
        try:
            # Check if we have valid cached link data
            if cached_data and idx < len(cached_data) and cached_data[idx]:
                unrestricted_link = cached_data[idx]
                if not check_if_link_expired(cached_date_str=unrestricted_link.get("cached_date")):
                    if ui_utils.verbose:
                        print(f"Using cached link for {unrestricted_link.get('filename', f'link {idx+1}')} ({idx+1}/{len(torrent['links'])})")
                    
                    download_url = unrestricted_link["download"]
                    filename = sanitize_filename(unrestricted_link["filename"])
                    streamable = unrestricted_link.get("streamable", 0)
                    
                    if streamable == 0 and should_skip_content(None, download_url):
                        continue
                    
                    save_result = save_link(filename, download_url, output_dir, idx)
                    if save_result:
                        saved_files.append(save_result)
                    else:
                        # Count skipped extra content
                        is_extra = classify_extra_content(filename)
                        if is_extra:
                            skipped_extras_count += 1
                    continue
            
            # Otherwise, unrestrict the link
            ui_utils.file_status(torrent.get('filename', torrent['id']), "processing", f"unrestricting link {idx+1}/{len(torrent['links'])}")
            result = client.unrestrict_link(link)
            
            # Check for hoster unavailable error
            if result and result.get('error') == 'hoster_unavailable':
                ui_utils.file_status(torrent.get('filename', torrent['id']), "error", "hoster unavailable, needs reinsertion")
                # Return a special marker that this torrent needs reinsertion
                return {"needs_reinsertion": True, "torrent": torrent}
            
            if result and 'download' in result and result.get('streamable') == 1:
                file_name = result.get('filename', torrent.get('filename', torrent['id']))
                download_url = result['download']
                save_result = save_link(file_name, download_url, output_dir, idx)
                
                # Check for skipped extras
                if save_result == "skipped_extra":
                    skipped_extras_count += 1
                elif save_result:
                    saved_files.append(save_result)
                    
                    # Cache this data
                    if cache_dir:
                        cache_data = {
                            'links': [result],
                            'saved_files': [save_result] if save_result != "skipped_extra" else [],
                            'skipped_extras': 1 if save_result == "skipped_extra" else 0,
                            'cached_date': datetime.now().isoformat()
                        }
                        save_to_cache(torrent["id"], cache_data, cache_dir)
                    
                    continue
            else:
                # If download URL is missing, we need to unrestrict it
                ui_utils.file_status(torrent.get('filename', torrent['id']), "processing", "missing download URL, unrestricting")
                result = client.unrestrict_link(link)
                
                # Check for hoster unavailable error
                if result and result.get('error') == 'hoster_unavailable':
                    ui_utils.file_status(torrent.get('filename', torrent['id']), "error", "hoster unavailable, needs reinsertion")
                    # Return a special marker that this torrent needs reinsertion
                    return {"needs_reinsertion": True, "torrent": torrent}
                
                if result and 'download' in result and result.get('streamable') == 1:
                    # Check if the link is expired based on generation date
                    generated_date = result.get('generated')
                    
                    if check_if_link_expired(generated_date, None):
                        ui_utils.file_status(torrent.get('filename', torrent['id']), "processing", "link expired, regenerating")
                        # Delete the old download if expired
                        client.delete_download(torrent['id'])
                    else:
                        # Link is still valid
                        file_name = result.get('filename', torrent.get('filename', torrent['id']))
                        download_url = result['download']
                        save_result = save_link(file_name, download_url, output_dir, idx)
                        
                        # Check for skipped extras
                        if save_result == "skipped_extra":
                            skipped_extras_count += 1
                        elif save_result:
                            saved_files.append(save_result)
                            
                            # Cache this data
                            if cache_dir:
                                cache_data = {
                                    'links': [result],
                                    'saved_files': [save_result] if save_result != "skipped_extra" else [],
                                    'skipped_extras': 1 if save_result == "skipped_extra" else 0,
                                    'cached_date': datetime.now().isoformat()
                                }
                                save_to_cache(torrent["id"], cache_data, cache_dir)
                            
                            continue
                
                # If we got here, the link needs to be regenerated
                client.delete_download(torrent['id'])
        except Exception as e:
            ui_utils.error(f"Error processing link {idx+1}/{len(torrent['links'])}: {e}")
            skipped_extras_count += 1
    
    # If we encountered a hoster unavailable error, mark this torrent for reinsertion
    if skipped_extras_count > 0:
        return {"needs_reinsertion": True, "torrent": torrent}
    
    # Cache the results
    if cache_dir and (saved_files or skipped_extras_count > 0):
        cache_data = {
            'links': [link for link in torrent['links'] if link in link_to_download],
            'saved_files': saved_files,
            'skipped_extras': skipped_extras_count,
            'cached_date': datetime.now().isoformat()
        }
        save_to_cache(torrent["id"], cache_data, cache_dir)
    
    # Return a dictionary with results
    if isinstance(saved_files, list):
        return {"saved_files": saved_files, "skipped_extras": skipped_extras_count}
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
    
    # Add debug info for downloads parameter
    if isinstance(downloads, list):
        ui_utils.info(f"Downloads is a list with {len(downloads)} items")
        if downloads and len(downloads) > 0:
            first_download = downloads[0]
            ui_utils.info(f"First download type: {type(first_download)}")
            if isinstance(first_download, dict):
                ui_utils.info(f"First download keys: {', '.join(first_download.keys())}")
    elif isinstance(downloads, dict):
        ui_utils.info(f"Downloads is a dictionary with {len(downloads)} keys")
        # Convert the dictionary to a list for backward compatibility
        try:
            downloads = list(downloads.values())
            ui_utils.info(f"Converted dictionary to list with {len(downloads)} items")
        except Exception as e:
            ui_utils.error(f"Failed to convert dictionary to list: {e}")
            downloads = []
    elif isinstance(downloads, str):
        ui_utils.info(f"WARNING: Downloads is a string: {downloads[:50]}...")
        downloads = []
    else:
        ui_utils.info(f"Downloads is of type: {type(downloads)}")
    
    # Ensure downloads is a list
    if not isinstance(downloads, list):
        ui_utils.error(f"Downloads parameter is not a list! Using empty list instead.")
        downloads = []
    
    downloads_dict = {}
    for download in downloads:
        # Ensure download is a dict before processing
        if not isinstance(download, dict):
            ui_utils.error(f"Found download that is not a dictionary: {type(download)}")
            continue
            
        # Use the ID as the key for quick lookup
        download_id = download.get('id')
        if download_id:
            downloads_dict[download_id] = download
    
    ui_utils.info(f"Found {len(downloads_dict)} downloads in your account")
    
    # Separate torrents by type for optimized processing
    tv_show_torrents = []
    movie_torrents = []
    unknown_torrents = []
    
    # Pre-categorize torrents for better thread allocation
    for torrent in torrents:
        # Ensure torrent is a dict
        if not isinstance(torrent, dict):
            ui_utils.error(f"Found torrent that is not a dictionary: {type(torrent)}")
            continue
            
        if torrent.get('status') != 'downloaded':
            continue
            
        filename = torrent.get('filename', '')
        if parse_tv_show_filename(filename):
            tv_show_torrents.append(torrent)
        elif any(re.search(pattern, filename, re.IGNORECASE) for pattern in [
            r'(?:19|20)\d{2}',
            r'(?:bluray|brrip|dvdrip|remux|webrip|web-dl)',
            r'(?:2160p|1080p|720p)'
        ]):
            movie_torrents.append(torrent)
        else:
            unknown_torrents.append(torrent)
    
    ui_utils.info(f"Categorized torrents: {len(tv_show_torrents)} TV shows, {len(movie_torrents)} movies, {len(unknown_torrents)} unknown")
    
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
        "torrents_with_errors": 0,
        "tv_shows_processed": 0,
        "movies_processed": 0,
        "unknown_processed": 0,
        "skipped_extras": 0
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
    
    # Remove unhealthy torrents from our type-specific lists
    tv_show_torrents = [t for t in tv_show_torrents if t not in unhealthy_torrents]
    movie_torrents = [t for t in movie_torrents if t not in unhealthy_torrents]
    unknown_torrents = [t for t in unknown_torrents if t not in unhealthy_torrents]
    
    # Recategorize reinserted torrents
    for torrent in reinserted_torrents:
        filename = torrent.get('filename', '')
        if parse_tv_show_filename(filename):
            tv_show_torrents.append(torrent)
        elif any(re.search(pattern, filename, re.IGNORECASE) for pattern in [
            r'(?:19|20)\d{2}',
            r'(?:bluray|brrip|dvdrip|remux|webrip|web-dl)',
            r'(?:2160p|1080p|720p)'
        ]):
            movie_torrents.append(torrent)
        else:
            unknown_torrents.append(torrent)
    
    # Process torrents by type for better efficiency
    # TV shows often have more complex patterns and folder structures
    process_start_time = time.time()
    
    # Torrents that need reinsertion due to 503 errors
    torrents_to_reinsert = []
    
    # Calculate optimal thread allocation based on content types and count
    total_workers = client.concurrent_requests
    
    # Process TV shows - allocate more threads since they're often more complex
    ui_utils.info(f"Processing {len(tv_show_torrents)} TV show torrents...")
    tv_max_workers = get_optimal_thread_count(len(tv_show_torrents), "tv_show", total_workers)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=tv_max_workers) as executor:
        future_to_torrent = {
            executor.submit(process_single_torrent, client, torrent, output_dir, downloads_dict, cache_dir): torrent
            for torrent in tv_show_torrents
        }
        
        for future in ui_utils.spinner("Processing TV shows", concurrent.futures.as_completed(future_to_torrent)):
            torrent = future_to_torrent[future]
            try:
                # Fix: Ensure we're handling all possible return types from process_single_torrent
                result = future.result()
                
                # Handle all possible return types correctly
                if isinstance(result, dict):
                    # Dictionary result - could be needs_reinsertion or saved_files + skipped_extras
                    if result.get('needs_reinsertion'):
                        ui_utils.warning(f"Marking torrent for reinsertion due to hoster unavailability: {torrent.get('filename', torrent['id'])}")
                        torrents_to_reinsert.append(result.get('torrent'))
                    else:
                        # It's a results dict with saved_files
                        if 'saved_files' in result and isinstance(result['saved_files'], list):
                            saved_paths.extend(result['saved_files'])
                            stats["saved_paths"] += len(result['saved_files'])
                        if 'skipped_extras' in result:
                            stats["skipped_extras"] += result['skipped_extras']
                        stats["tv_shows_processed"] += 1
                        if cache_dir and is_cached(torrent.get('id'), cache_dir):
                            stats["cached_torrents"] += 1
                elif isinstance(result, list):
                    # List of saved paths
                    saved_paths.extend(result)
                    stats["saved_paths"] += len(result)
                    stats["tv_shows_processed"] += 1
                    if cache_dir and is_cached(torrent.get('id'), cache_dir):
                        stats["cached_torrents"] += 1
                elif isinstance(result, str):
                    # Either a single saved path or "skipped_extra" marker
                    if result != "skipped_extra":
                        saved_paths.append(result)
                        stats["saved_paths"] += 1
                    else:
                        stats["skipped_extras"] += 1
                    stats["tv_shows_processed"] += 1
                    if cache_dir and is_cached(torrent.get('id'), cache_dir):
                        stats["cached_torrents"] += 1
            except Exception as e:
                ui_utils.error(f"Error processing TV show torrent {torrent.get('filename', 'unknown')}: {e}")
                stats["torrents_with_errors"] += 1
    
    # Process movie torrents - fewer threads since they're generally simpler
    ui_utils.info(f"Processing {len(movie_torrents)} movie torrents...")
    movie_max_workers = get_optimal_thread_count(len(movie_torrents), "movie", total_workers)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=movie_max_workers) as executor:
        future_to_torrent = {
            executor.submit(process_single_torrent, client, torrent, output_dir, downloads_dict, cache_dir): torrent
            for torrent in movie_torrents
        }
        
        for future in ui_utils.spinner("Processing movies", concurrent.futures.as_completed(future_to_torrent)):
            torrent = future_to_torrent[future]
            try:
                # Fix: Handle all possible return types from process_single_torrent
                result = future.result()
                
                # Handle all possible return types correctly
                if isinstance(result, dict):
                    # Dictionary result - could be needs_reinsertion or saved_files + skipped_extras
                    if result.get('needs_reinsertion'):
                        ui_utils.warning(f"Marking torrent for reinsertion due to hoster unavailability: {torrent.get('filename', torrent['id'])}")
                        torrents_to_reinsert.append(result.get('torrent'))
                    else:
                        # It's a results dict with saved_files
                        if 'saved_files' in result and isinstance(result['saved_files'], list):
                            saved_paths.extend(result['saved_files'])
                            stats["saved_paths"] += len(result['saved_files'])
                        if 'skipped_extras' in result:
                            stats["skipped_extras"] += result['skipped_extras']
                        stats["movies_processed"] += 1
                        if cache_dir and is_cached(torrent.get('id'), cache_dir):
                            stats["cached_torrents"] += 1
                elif isinstance(result, list):
                    # List of saved paths
                    saved_paths.extend(result)
                    stats["saved_paths"] += len(result)
                    stats["movies_processed"] += 1
                    if cache_dir and is_cached(torrent.get('id'), cache_dir):
                        stats["cached_torrents"] += 1
                elif isinstance(result, str):
                    # Either a single saved path or "skipped_extra" marker
                    if result != "skipped_extra":
                        saved_paths.append(result)
                        stats["saved_paths"] += 1
                    else:
                        stats["skipped_extras"] += 1
                    stats["movies_processed"] += 1
                    if cache_dir and is_cached(torrent.get('id'), cache_dir):
                        stats["cached_torrents"] += 1
            except Exception as e:
                ui_utils.error(f"Error processing movie torrent {torrent.get('filename', 'unknown')}: {e}")
                stats["torrents_with_errors"] += 1
    
    # Process unknown torrents with similar changes to handle all return types
    if unknown_torrents:
        ui_utils.info(f"Processing {len(unknown_torrents)} unknown torrents...")
        unknown_max_workers = get_optimal_thread_count(len(unknown_torrents), "unknown", total_workers)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=unknown_max_workers) as executor:
            future_to_torrent = {
                executor.submit(process_single_torrent, client, torrent, output_dir, downloads_dict, cache_dir): torrent
                for torrent in unknown_torrents
            }
            
            for future in ui_utils.spinner("Processing unknown torrents", concurrent.futures.as_completed(future_to_torrent)):
                torrent = future_to_torrent[future]
                try:
                    # Fix: Handle all possible return types from process_single_torrent
                    result = future.result()
                    
                    # Handle all possible return types correctly
                    if isinstance(result, dict):
                        # Dictionary result - could be needs_reinsertion or saved_files + skipped_extras
                        if result.get('needs_reinsertion'):
                            ui_utils.warning(f"Marking torrent for reinsertion due to hoster unavailability: {torrent.get('filename', torrent['id'])}")
                            torrents_to_reinsert.append(result.get('torrent'))
                        else:
                            # It's a results dict with saved_files
                            if 'saved_files' in result and isinstance(result['saved_files'], list):
                                saved_paths.extend(result['saved_files'])
                                stats["saved_paths"] += len(result['saved_files'])
                            if 'skipped_extras' in result:
                                stats["skipped_extras"] += result['skipped_extras']
                            stats["unknown_processed"] += 1
                            if cache_dir and is_cached(torrent.get('id'), cache_dir):
                                stats["cached_torrents"] += 1
                    elif isinstance(result, list):
                        # List of saved paths
                        saved_paths.extend(result)
                        stats["saved_paths"] += len(result)
                        stats["unknown_processed"] += 1
                        if cache_dir and is_cached(torrent.get('id'), cache_dir):
                            stats["cached_torrents"] += 1
                    elif isinstance(result, str):
                        # Either a single saved path or "skipped_extra" marker
                        if result != "skipped_extra":
                            saved_paths.append(result)
                            stats["saved_paths"] += 1
                        else:
                            stats["skipped_extras"] += 1
                        stats["unknown_processed"] += 1
                        if cache_dir and is_cached(torrent.get('id'), cache_dir):
                            stats["cached_torrents"] += 1
                except Exception as e:
                    ui_utils.error(f"Error processing unknown torrent {torrent.get('filename', 'unknown')}: {e}")
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
                    result = process_single_torrent(client, new_torrent, output_dir, downloads_dict, cache_dir)
                    
                    # Fix: Handle all possible return types
                    if isinstance(result, dict) and 'saved_files' in result:
                        saved_paths.extend(result['saved_files'])
                        stats["saved_paths"] += len(result['saved_files'])
                    elif isinstance(result, list):
                        saved_paths.extend(result)
                        stats["saved_paths"] += len(result)
                    elif isinstance(result, str) and result != "skipped_extra":
                        saved_paths.append(result)
                        stats["saved_paths"] += 1
                except Exception as e:
                    ui_utils.error(f"Error processing reinserted torrent: {e}")
                    stats["torrents_with_errors"] += 1
    
    # Report on reinserted torrents
    if reinserted_torrents:
        ui_utils.success(f"\nSuccessfully reinserted {len(reinserted_torrents)} torrents")
    
    # Add the statistics object to the return value
    return {"saved_paths": saved_paths, "stats": stats}

def get_optimal_thread_count(file_count, file_type, max_threads):
    """
    Calculate optimal thread count based on file type and count.
    
    Args:
        file_count: Number of files to process
        file_type: Type of files ('tv_show', 'movie', or 'unknown')
        max_threads: Maximum number of threads available
        
    Returns:
        Optimal number of threads to use
    
    TV shows typically need more processing power due to complex folder structures,
    while movies are simpler to process. This function allocates threads accordingly.
    """
    if file_count == 0:
        return 1
        
    if file_type == "tv_show":
        # Allocate 70% of threads to TV shows (they have complex folder structures)
        return max(1, min(file_count, int(max_threads * 0.7)))
    elif file_type == "movie":
        # Allocate 30% of threads to movies (simpler processing)
        return max(1, min(file_count, int(max_threads * 0.3)))
    else:
        # For unknown types, use a middle ground allocation
        return max(1, min(file_count, int(max_threads * 0.5)))

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
        "cache_dir": os.environ.get("REALDEBRID_CACHE_DIR", ""),
        # Watch mode configurations
        "watch_mode_enabled": os.environ.get("REALDEBRID_WATCH_MODE", "false").lower() == "true",
        "watch_mode_refresh_interval": int(os.environ.get("REALDEBRID_REFRESH_INTERVAL", 10)),
        "watch_mode_health_check_interval": int(os.environ.get("REALDEBRID_HEALTH_CHECK_INTERVAL", 60)),
        "repair_torrents_enabled": os.environ.get("REALDEBRID_REPAIR_TORRENTS", "true").lower() == "true"
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

def watch_mode(client, output_dir, cache_dir, config):
    """
    Continuously monitor Real-Debrid for new torrents and process them.
    
    Args:
        client: RealDebridClient instance
        output_dir: Directory to save the output files
        cache_dir: Directory for caching torrent data
        config: Configuration dictionary with watch mode settings
    """
    ui_utils.info(f"Starting watch mode. Refreshing every {config['watch_mode_refresh_interval']} seconds, "
                 f"health checks every {config['watch_mode_health_check_interval']} minutes.")
    
    # Keep track of processed torrents and downloads
    processed_torrent_ids = set()
    known_downloads = {}
    downloads_list = []  # Keep a reference to the original list for passing to process_torrents_concurrent
    
    # Track time for periodic health checks
    last_health_check_time = time.time()
    health_check_interval_seconds = config['watch_mode_health_check_interval'] * 60
    
    # Set flag for health check on first run
    needs_health_check = True
    repair_torrents = config['repair_torrents_enabled']
    
    try:
        while True:
            try:
                current_time = time.time()
                
                # Determine if we need a health check
                if needs_health_check or (current_time - last_health_check_time) >= health_check_interval_seconds:
                    ui_utils.info("Performing health check...")
                    needs_health_check = False
                    last_health_check_time = current_time
                    
                    # Refresh all downloads
                    ui_utils.info("Refreshing all downloads...")
                    downloads_list = client.get_all_downloads_concurrent()
                    
                    # Update known downloads dictionary
                    known_downloads = {}
                    for download in downloads_list:
                        if not isinstance(download, dict):
                            ui_utils.warning(f"Skipping non-dict download: {type(download)}")
                            continue
                        download_id = download.get('id')
                        if download_id:
                            known_downloads[download_id] = download
                    
                    # Get all torrents with health check
                    ui_utils.info("Retrieving all torrents with health check...")
                    torrents = client.get_all_torrents_concurrent()
                    
                    # Filter for only downloaded torrents
                    downloaded_torrents = [t for t in torrents if isinstance(t, dict) and t.get('status') == 'downloaded']
                    
                    # Process torrents with health check
                    results = process_torrents_concurrent(
                        client, 
                        downloaded_torrents, 
                        output_dir, 
                        cache_dir,
                        downloads_list,  # Pass the original list
                        skip_health_check=not repair_torrents  # Skip health check if repair is disabled
                    )
                    
                    # Update processed torrent IDs
                    for torrent in downloaded_torrents:
                        if isinstance(torrent, dict) and torrent.get('id'):
                            processed_torrent_ids.add(torrent.get('id'))
                            
                    # Report statistics
                    stats = results["stats"]
                    ui_utils.success(f"Health check completed. Processed {len(downloaded_torrents)} torrents, "
                                    f"saved {stats['saved_paths']} links, "
                                    f"reinserted {stats['reinserted_torrents']} torrents.")
                    
                else:
                    # Lighter check for new torrents only
                    ui_utils.info(f"Checking for new torrents...")
                    
                    # Get all torrents without health check
                    torrents = client.get_all_torrents_concurrent()
                    
                    # Find new torrents that haven't been processed yet
                    new_torrents = [t for t in torrents 
                                  if isinstance(t, dict)
                                  and t.get('status') == 'downloaded' 
                                  and t.get('id') not in processed_torrent_ids]
                    
                    if new_torrents:
                        ui_utils.info(f"Found {len(new_torrents)} new torrents to process.")
                        
                        # Debug info for each new torrent
                        for i, torrent in enumerate(new_torrents):
                            ui_utils.info(f"Debug - New torrent {i+1}:")
                            ui_utils.info(f"  ID: {torrent.get('id')}")
                            ui_utils.info(f"  Filename: {torrent.get('filename')}")
                            ui_utils.info(f"  Status: {torrent.get('status')}")
                            ui_utils.info(f"  Links type: {type(torrent.get('links', []))}")
                            
                            # Print links (safely)
                            links = torrent.get('links', [])
                            if isinstance(links, list):
                                ui_utils.info(f"  Links count: {len(links)}")
                                for j, link in enumerate(links[:3]):  # Show first 3 links max
                                    ui_utils.info(f"    Link {j+1}: {link} (type: {type(link)})")
                            elif isinstance(links, str):
                                ui_utils.info(f"  Links (string): {links}")
                            else:
                                ui_utils.info(f"  Links: {links}")
                        
                        # Get fresh downloads if we haven't done so recently
                        if current_time - last_health_check_time > 300:  # 5 minutes
                            ui_utils.info("Refreshing downloads data...")
                            downloads_list = client.get_all_downloads_concurrent()
                            # Update the known_downloads dictionary too
                            known_downloads = {}
                            for download in downloads_list:
                                if not isinstance(download, dict):
                                    continue
                                download_id = download.get('id')
                                if download_id:
                                    known_downloads[download_id] = download
                        
                        # Process only the new torrents
                        results = process_torrents_concurrent(
                            client, 
                            new_torrents, 
                            output_dir, 
                            cache_dir,
                            downloads_list,  # Make sure we pass the list, not the dictionary
                            skip_health_check=True  # Skip health check for incremental updates
                        )
                        
                        # Update processed torrent IDs
                        for torrent in new_torrents:
                            if torrent.get('id'):
                                processed_torrent_ids.add(torrent.get('id'))
                                
                        # Report statistics
                        stats = results["stats"]
                        ui_utils.success(f"Processed {len(new_torrents)} new torrents, "
                                        f"saved {stats['saved_paths']} links.")
                    else:
                        ui_utils.info("No new torrents found.")
                
                # Sleep before next check
                ui_utils.info(f"Next check in {config['watch_mode_refresh_interval']} seconds...")
                time.sleep(config['watch_mode_refresh_interval'])
                
            except KeyboardInterrupt:
                ui_utils.warning("Keyboard interrupt detected. Exiting watch mode...")
                break
                
            except Exception as e:
                ui_utils.error(f"Error during watch mode processing: {e}")
                # Print traceback for better debugging
                import traceback
                ui_utils.error(f"Traceback: {traceback.format_exc()}")
                ui_utils.warning(f"Continuing watch mode in {config['watch_mode_refresh_interval']} seconds...")
                time.sleep(config['watch_mode_refresh_interval'])
                
    except KeyboardInterrupt:
        ui_utils.warning("Watch mode stopped by user.")
    
    ui_utils.info("Watch mode terminated.")

# --- Main Program ---
def main():
    """Main function to run the script."""
    global ui_utils

    parser = argparse.ArgumentParser(description="RoboFuse: Organize your Real-Debrid downloads")
    parser.add_argument("--output-dir", help="Directory to save generated .strm files")
    parser.add_argument("--cache-dir", help="Directory to cache API responses")
    parser.add_argument("--concurrent", type=int, help="Number of concurrent requests")
    parser.add_argument("--general-rate-limit", type=int, help="General API rate limit in requests per minute")
    parser.add_argument("--torrents-rate-limit", type=int, help="Torrents API rate limit in requests per minute")
    parser.add_argument("--skip-health-check", action="store_true", help="Skip torrent health checks")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    parser.add_argument("--quiet", action="store_true", help="Suppress most output")
    parser.add_argument("--watch", action="store_true", help="Run in watch mode")
    parser.add_argument("--watch-refresh-interval", type=int, help="Refresh interval in minutes for watch mode")
    parser.add_argument("--watch-health-interval", type=int, help="Health check interval in minutes for watch mode")
    parser.add_argument("--repair-torrents", action="store_true", help="Enable automatic repair of unhealthy torrents")
    parser.add_argument("--no-repair-torrents", action="store_true", help="Disable automatic repair of unhealthy torrents")
    parser.add_argument("--summary", action="store_true", help="Show only summary information")
    args = parser.parse_args()

    # Load configuration
    config = load_config()
    
    # Apply command line overrides
    if args.output_dir:
        config["output_dir"] = args.output_dir
    if args.cache_dir:
        config["cache_dir"] = args.cache_dir
    if args.concurrent:
        config["concurrent_requests"] = args.concurrent
    if args.general_rate_limit:
        config["general_rate_limit"] = args.general_rate_limit
    if args.torrents_rate_limit:
        config["torrents_rate_limit"] = args.torrents_rate_limit
    if args.watch:
        config["watch_mode_enabled"] = True
    if args.watch_refresh_interval:
        config["watch_mode_refresh_interval"] = args.watch_refresh_interval
    if args.watch_health_interval:
        config["watch_mode_health_check_interval"] = args.watch_health_interval
    if args.repair_torrents:
        config["repair_torrents_enabled"] = True
    if args.no_repair_torrents:
        config["repair_torrents_enabled"] = False
    
    # Configure logging based on verbosity
    if args.verbose:
        ui_utils.set_log_level(ui_utils.LogLevel.DEBUG)
    elif args.quiet:
        ui_utils.set_log_level(ui_utils.LogLevel.ERROR)
    elif args.summary:
        # Summary mode shows only important summary info
        ui_utils.set_log_level(ui_utils.LogLevel.WARNING)  # Show warnings and errors
        ui_utils.set_progress_display(False)  # Hide progress indicators
    else:
        ui_utils.set_log_level(ui_utils.LogLevel.INFO)
    
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
    
    # Override watch mode settings if provided
    watch_mode_enabled = args.watch or config["watch_mode_enabled"]
    if args.watch_refresh_interval:
        config["watch_mode_refresh_interval"] = args.watch_refresh_interval
    if args.watch_health_interval:
        config["watch_mode_health_check_interval"] = args.watch_health_interval
    
    # Handle repair torrents flags (command line overrides config)
    if args.repair_torrents:
        config["repair_torrents_enabled"] = True
    elif args.no_repair_torrents:
        config["repair_torrents_enabled"] = False
    
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
        "Health checks": 'Disabled' if args.skip_health_check and not watch_mode_enabled else 'Enabled',
        "Output directory": output_dir,
        "Cache directory": cache_dir or "Not used",
        "Verbosity": "Debug" if args.verbose else ("Quiet" if args.quiet else "Normal"),
        "Repair torrents": "Enabled" if config["repair_torrents_enabled"] else "Disabled"
    }
    
    if watch_mode_enabled:
        config_items.update({
            "Watch mode": "Enabled",
            "Refresh interval": f"{config['watch_mode_refresh_interval']} seconds",
            "Health check interval": f"{config['watch_mode_health_check_interval']} minutes"
        })
    
    # Only show the configuration summary if not in quiet mode
    if not args.quiet:
        ui_utils.print_summary_box("Configuration", config_items)
    
    # Run in watch mode if enabled
    if watch_mode_enabled:
        watch_mode(client, output_dir, cache_dir, config)
        return
        
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
    
    # Skip health check if specified or repair torrents is disabled
    skip_health_check = args.skip_health_check or not config["repair_torrents_enabled"]
    
    # Process torrents concurrently with health checks if enabled
    ui_utils.info("\nProcessing torrents to extract download links...")
    process_start = time.time()
    
    results = process_torrents_concurrent(
        client, 
        downloaded_torrents, 
        output_dir, 
        cache_dir,
        downloads,
        skip_health_check
    )
    
    saved_paths = results["saved_paths"]
    stats = results["stats"]
    
    process_time = time.time() - process_start
    
    # Summary statistics
    summary_items = {
        "Total torrents processed": len(downloaded_torrents),
        "Total download links saved": len(saved_paths),
        "Processed by type": f"TV Shows: {stats['tv_shows_processed']}, Movies: {stats['movies_processed']}, Unknown: {stats['unknown_processed']}",
        "Healthy torrents": stats["healthy_torrents"],
        "Unhealthy torrents": stats["unhealthy_torrents"],
        "Reinserted torrents": stats["reinserted_torrents"],
        "Torrents with errors": stats["torrents_with_errors"],
        "Skipped files": stats.get("skipped_extras", 0),
        "Torrents using cache": stats["cached_torrents"],
        "Health check time": ui_utils.format_time(stats["health_check_time"]),
        "Processing time": ui_utils.format_time(stats["torrent_process_time"]),
        "Average per torrent": ui_utils.format_time(process_time/max(1, len(downloaded_torrents))),
        "Total runtime": ui_utils.format_time(process_time + fetch_time)
    }
    ui_utils.print_summary_box("Processing Summary", summary_items)

def parse_tv_show_filename(filename):
    """
    Enhanced pattern detection for TV shows without using external APIs.
    Returns (series_name, season_number, episode_number) or None if not a TV show.
    """
    # First, check if this has a clear TV show format with SxxExx pattern
    # This takes precedence over any year patterns
    sxxexx_patterns = [
        # Standard SxxExx pattern
        r'(.*?)[.\s][Ss](\d{1,2})[Ee](\d{1,2})',
        # Alternative format without series name captured directly
        r'[Ss](\d{1,2})[\s]*[Ee](\d{1,2})',
        # Show.Name.2019.S01E01 (year before season)
        r'(.*?)(?:\.\d{4}\.)[Ss](\d{1,2})[Ee](\d{1,2})',
        # Show Name (2019) - S01E01 (year in parentheses)
        r'(.*?)\(\d{4}\).*?[Ss](\d{1,2})[Ee](\d{1,2})',
        # S01E01.Show.Name - reverse order
        r'[Ss](\d{1,2})[Ee](\d{1,2})(?:[.\s_-]+)(.*?)[.\s]'
    ]
    
    # Try all SxxExx patterns
    for pattern in sxxexx_patterns:
        match = re.search(pattern, filename)
        if match:
            # This is most likely a TV show, even if it has a year
            if len(match.groups()) == 3:
                # Standard format with series name captured directly
                series = match.group(1).replace('.', ' ').strip()
                season = int(match.group(2))
                episode = int(match.group(3))
            elif len(match.groups()) == 2:
                # Handle patterns without series name directly captured
                pre_pattern = re.search(r'(.*?)[.\s][Ss]', filename)
                if pre_pattern:
                    series = pre_pattern.group(1).replace('.', ' ').strip()
                else:
                    # Fall back to everything before the SxxExx
                    series_pattern = re.search(r'^(.*?)[Ss](?:\d{1,2})[Ee](?:\d{1,2})', filename, re.IGNORECASE)
                    series = series_pattern.group(1).strip() if series_pattern else "Unknown Series"
                season = int(match.group(1))
                episode = int(match.group(2))
            
            # Clean up the series name
            series = re.sub(r'[.\s-]+$', '', series)  # Remove trailing separators
            
            # Handle edge cases with brackets/parentheses
            series = re.sub(r'\([^)]*\)', '', series).strip()  # Remove content in parentheses
            series = re.sub(r'\[[^]]*\]', '', series).strip()  # Remove content in brackets
            
            return (series, season, episode)
    
    # Check for movie patterns first - if it has a clear movie pattern and no SxxExx match, it's a movie
    movie_markers = [
        r'\((?:19|20)\d{2}\)',  # Year in parentheses: (2022)
        r'\[(?:19|20)\d{2}\]',  # Year in brackets: [2022]
        r'(?:19|20)\d{2}(?:\.|\s)[^S\d]', # Year followed by dot/space not followed by S or digit
        r'(?:bluray|brrip|dvdrip|remux|webrip|web-dl).+(?:19|20)\d{2}', # Source format + year
        r'(?:19|20)\d{2}.+(?:bluray|brrip|dvdrip|remux|webrip|web-dl)', # Year + source format
        r'(?:2160p|1080p|720p).+(?:bluray|brrip|remux|dvdrip)', # Resolution + source
        r'(?:uhd|hdr10|hdr|dv).+(?:19|20)\d{2}', # HDR format + year
        r'(?:hybrid|extended|directors).+(?:cut|edition)', # Special editions
        r'(?:x264|x265|hevc|xvid|divx|avc)', # Common video codecs
        r'(?:aac|dd5|dts|dolby|atmos|truehd)', # Common audio codecs
    ]
    
    # Check if this is a movie first
    for pattern in movie_markers:
        if re.search(pattern, filename, re.IGNORECASE):
            # Before confirming it's a movie, check if there's any TV show markers
            tv_markers = [r'[Ss]\d{1,2}[Ee]\d{1,2}', r'season', r'episode', r'complete']
            if not any(re.search(pattern, filename, re.IGNORECASE) for pattern in tv_markers):
                return None  # This is a movie
    
    # Handle other TV show patterns if no movie patterns matched
    other_tv_patterns = [
        # Series.Name.1x01.Title - alternative format (1x01)
        (r'^(.*?)(?:[.\s]|^)(\d{1,2})x(\d{2})(?:[.\s]|$)', "alternative_format"),
        
        # Series.Name.Season.1.Episode.01 - spelled out format
        (r'^(.*?)(?:[.\s])Season[.\s](\d{1,2})[.\s]Episode[.\s](\d{1,2})(?:[.\s]|$)', "spelled_out"),
        
        # Series Name - S01E01 - Title - dashed format
        (r'^(.*?)\s-\s[Ss](\d{1,2})[Ee](\d{1,2})\s-\s', "dashed_format"),
        
        # Common typos like S01.E01 or S01 E01 (space or dot between S and E)
        (r'(.*?)[Ss](\d{1,2})[\s.]+[Ee](\d{1,2})', "typo_format"),
        
        # Japanese-style episodes like [Group] Show - 01v2 (1080p)
        (r'\][\s.]*([^-\[\]]+?)[\s.]*-[\s.]*(\d{1,2})(?:v\d)?[\s.]*(?:\(|\[)', "anime_format_1"),
        
        # Japanese-style episodes with just number, assuming season 1
        (r'(.*?)[\s.]*-[\s.]*(\d{1,2})[\s.]*\[[^\]]*\]', "anime_format_2")
    ]
    
    for pattern, pattern_type in other_tv_patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            series_name = match.group(1).replace('.', ' ').strip()
            # Remove trailing separators
            series_name = re.sub(r'[.\s-]+$', '', series_name)
            
            # Handle specific pattern types
            if pattern_type in ["anime_format_1", "anime_format_2"]:
                # Anime formats often only have episode numbers, no season
                season_num = 1
                episode_num = int(match.group(2))
            else:
                # Standard format with season and episode
                season_num = int(match.group(2))
                episode_num = int(match.group(3))
                
            # Handle edge cases with brackets/parentheses
            series_name = re.sub(r'\([^)]*\)', '', series_name).strip()  # Remove content in parentheses
            series_name = re.sub(r'\[[^]]*\]', '', series_name).strip()  # Remove content in brackets
            
            return (series_name, season_num, episode_num)
    
    # Check for anime-style patterns like "One Piece - 1073"
    anime_pattern = r'(.*?)(?:\s-\s|\s)(\d{2,4})(?:\s|$|\[|\(|\.|_)'
    anime_match = re.search(anime_pattern, filename)
    
    # Only match anime pattern if:
    # 1. It's not a year (1900-2099)
    # 2. It doesn't have typical movie markers
    if anime_match and not re.search(r'(?:19|20)\d{2}', anime_match.group(2)):
        if not re.search(r'(?:bluray|brrip|dvdrip|webrip|web-dl)', filename, re.IGNORECASE):
            series = anime_match.group(1).strip()
            # For anime pattern, assume episode only (season 1)
            episode = int(anime_match.group(2))
            
            # Clean up series name
            series = re.sub(r'\([^)]*\)', '', series).strip()  # Remove content in parentheses
            series = re.sub(r'\[[^]]*\]', '', series).strip()  # Remove content in brackets
            
            return (series, 1, episode)
    
    # Special pattern for 3-digit episode numbers like "101" (S01E01)
    # Only match this if it's in a clear episode context
    episode_context = r'^(.*?)(?:[.\s]|^|-\s)(\d)(\d{2})(?:\s-\s|\s|\.)'
    episode_match = re.search(episode_context, filename)
    if episode_match and len(episode_match.group(1).strip()) > 0:
        series = episode_match.group(1).replace('.', ' ').strip()
        # Remove trailing separators
        series = re.sub(r'[.\s-]+$', '', series)
        season = int(episode_match.group(2))
        episode = int(episode_match.group(3))
        
        # Only accept if:
        # 1. Season is a small number (1-9)
        # 2. Episode is reasonable (1-99)
        # 3. Series name is at least 2 characters
        if 0 < season < 10 and 0 < episode < 100 and len(series) >= 2:
            # Clean up series name
            series = re.sub(r'\([^)]*\)', '', series).strip()  # Remove content in parentheses
            series = re.sub(r'\[[^]]*\]', '', series).strip()  # Remove content in brackets
            
            return (series, season, episode)
    
    # Special handling for episodes with clear numbering
    # Only for CLEAR show patterns like "Series Name - 01 - Title"
    if " - " in filename:
        ep_pattern = r'^(.*?)\s-\s(\d{1,2})\s-\s'
        ep_match = re.search(ep_pattern, filename)
        if ep_match:
            series = ep_match.group(1).strip()
            # Remove trailing separators
            series = re.sub(r'[.\s-]+$', '', series)
            episode = int(ep_match.group(2))
            
            # Clean up series name
            series = re.sub(r'\([^)]*\)', '', series).strip()  # Remove content in parentheses
            series = re.sub(r'\[[^]]*\]', '', series).strip()  # Remove content in brackets
            
            # Assume season 1 for episode-only naming
            return (series, 1, episode)
    
    return None

if __name__ == "__main__":
    main()