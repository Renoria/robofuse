# Advanced Configuration

This guide covers all configuration options available in robofuse, along with detailed explanations of each setting and recommendations for various use cases.

## Table of Contents
- [Configuration File Location](#configuration-file-location)
- [Core Settings](#core-settings)
- [Rate Limiting Configuration](#rate-limiting-configuration)
- [Watch Mode Settings](#watch-mode-settings)
- [Advanced Features](#advanced-features)
- [Configuration Examples](#configuration-examples)

## Configuration File Location

The configuration file (`config.json`) should be located in the root directory of your robofuse installation. If running in Docker, the file should be mounted as a volume (see [Docker Deployment](./Docker-Deployment.md)).

## Core Settings

### API Token

```json
"token": "YOUR_RD_API_TOKEN"
```

**Description:** Your Real-Debrid API token for authentication.  
**Required:** Yes  
**Default:** None  
**Recommendation:** Keep your token secure and never commit it to public repositories.  
**Location:** Find your token in Real-Debrid Account → My Devices

### Output Directory

```json
"output_dir": "./Library"
```

**Description:** Directory where STRM files will be created.  
**Required:** Yes  
**Default:** "./Library"  
**Recommendation:** Use a path accessible to your media player.

### Cache Directory

```json
"cache_dir": "./cache"
```

**Description:** Directory for caching data to minimize API calls.  
**Required:** Yes  
**Default:** "./cache"  
**Recommendation:** Keep on same volume as the application for best performance.

### Concurrent Requests

```json
"concurrent_requests": 32
```

**Description:** Maximum number of concurrent requests to the Real-Debrid API.  
**Required:** No  
**Default:** 32  
**Recommendation:** Adjust based on your network speed. Higher values improve processing speed but may cause rate limiting if too high.

## Rate Limiting Configuration

### General Rate Limit

```json
"general_rate_limit": 60
```

**Description:** Maximum number of general API requests per minute.  
**Required:** No  
**Default:** 60  
**Recommendation:** Stay under Real-Debrid's limits to avoid API throttling.

### Torrents Rate Limit

```json
"torrents_rate_limit": 25
```

**Description:** Maximum number of torrent-specific API requests per minute.  
**Required:** No  
**Default:** 25  
**Recommendation:** Real-Debrid has stricter limits for torrent operations, keep this lower than general rate limit.

## Watch Mode Settings

### Watch Mode Enabled

```json
"watch_mode_enabled": false
```

**Description:** Automatically enable watch mode on startup.  
**Required:** No  
**Default:** false  
**Recommendation:** Set to true if running as a service or in background mode.

### Watch Mode Refresh Interval

```json
"watch_mode_refresh_interval": 10
```

**Description:** Seconds between checking for new torrents in watch mode.  
**Required:** No  
**Default:** 10  
**Recommendation:** Lower values give faster response but generate more API requests. 10-30 seconds is usually sufficient.

### Watch Mode Health Check Interval

```json
"watch_mode_health_check_interval": 60
```

**Description:** Minutes between health checks for existing content in watch mode.  
**Required:** No  
**Default:** 60  
**Recommendation:** Depends on how often links expire in your account. 60 minutes is generally sufficient.

## Advanced Features

### Repair Torrents Enabled

```json
"repair_torrents_enabled": true
```

**Description:** Automatically attempt to repair broken or incomplete torrents.  
**Required:** No  
**Default:** true  
**Recommendation:** Keep enabled for most reliable operation.

## Configuration Examples

### Minimal Configuration

```json
{
    "token": "YOUR_RD_API_TOKEN",
    "output_dir": "./Library",
    "cache_dir": "./cache"
}
```

### Watch Mode Configuration

```json
{
    "token": "YOUR_RD_API_TOKEN",
    "output_dir": "./Library",
    "cache_dir": "./cache",
    "watch_mode_enabled": true,
    "watch_mode_refresh_interval": 30,
    "watch_mode_health_check_interval": 120
}
```

### High-Performance Configuration

```json
{
    "token": "YOUR_RD_API_TOKEN",
    "output_dir": "./Library",
    "cache_dir": "./cache",
    "concurrent_requests": 64,
    "general_rate_limit": 60,
    "torrents_rate_limit": 25
}
``` 