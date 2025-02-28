# Cache System

robofuse includes a sophisticated caching system to minimize API calls to Real-Debrid, improve performance, and provide fallback during API outages. This page explains how the cache works, its benefits, and how to configure it for your specific needs.

## Table of Contents
- [Overview](#overview)
- [How Caching Works](#how-caching-works)
- [Cache Benefits](#cache-benefits)
- [Cache Limitations](#cache-limitations)
- [Configuration](#configuration)
- [Maintenance](#maintenance)
- [Disabling the Cache](#disabling-the-cache)

## Overview

The cache system in robofuse stores information about your torrents, downloads, and unrestricted links locally on your system. This reduces the need to request the same information repeatedly from Real-Debrid's API, resulting in faster performance and less API usage.

## How Caching Works

1. **Initial Data Collection**: When robofuse first runs, it collects information from Real-Debrid's API about your torrents and downloads.

2. **Local Storage**: This data is stored in JSON files in the cache directory (default: `./cache`).

3. **Cache Usage**: On subsequent runs, robofuse first checks the cache for information before making API requests.

4. **Cache Updates**: The cache is updated when:
   - New torrents or downloads are discovered
   - Existing torrents or downloads change state
   - The cache expiration time has passed for a particular entry

5. **Cache Structure**: Each piece of data is stored in a separate JSON file with a unique hash identifier, allowing for efficient retrieval.

## Cache Benefits

1. **Reduced API Calls**: Minimizes the number of requests made to Real-Debrid, helping you stay within rate limits.

2. **Faster Operation**: Retrieving data from local storage is much faster than making API requests.

3. **Offline Operation**: Limited functionality is still available even if Real-Debrid's API is temporarily unavailable.

4. **Reduced Load**: Helps reduce load on Real-Debrid's servers, being a good API citizen.

5. **Historical Data**: Maintains information about past torrents and downloads even if they are removed from Real-Debrid.

## Cache Limitations

1. **Potential Staleness**: If data changes on Real-Debrid's side (e.g., another client modifies a torrent), the cache might contain outdated information until it's refreshed.

2. **Storage Usage**: For users with many torrents or downloads, the cache can grow to occupy significant disk space.

3. **Initial Performance**: The first run requires more API calls to build the cache, resulting in slower initial performance.

## Configuration

The cache is configured through the `config.json` file:

```json
{
    "cache_dir": "./cache",
    "cache_expiration": 86400
}
```

### Options:

- **cache_dir**: Directory where cache files are stored
- **cache_expiration**: (Optional) Time in seconds before cache entries are considered stale (default: 24 hours)

## Maintenance

For optimal performance, consider these maintenance practices:

### Periodic Cache Clearing

If you experience issues or suspect stale data, you can clear the cache:

```bash
# Remove cache directory
rm -rf ./cache
# robofuse will recreate it on next run
```

### Cache Verification

To verify the cache is working correctly:

1. Run robofuse with verbose logging:
   ```bash
   python3 robofuse.py --verbose
   ```

2. Look for log messages indicating cache hits and misses:
   ```
   [CACHE] Hit: Found torrents in cache
   [CACHE] Miss: Downloading torrent info from Real-Debrid
   ```

## Disabling the Cache

While not recommended for most users, you can run robofuse without using the cache by setting the `--no-cache` flag:

```bash
python3 robofuse.py --no-cache
```

This will:
- Skip reading from the cache
- Skip writing to the cache
- Make all data requests directly to the Real-Debrid API

**Note**: Using `--no-cache` significantly increases API usage and may lead to rate limiting by Real-Debrid. 