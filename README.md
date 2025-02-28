# robofuse
## v0.3.5

A Python-based utility for interacting with Real-Debrid API services efficiently with smart rate limiting and parallel processing. Robofuse generates .strm files that can be used in media players like Infuse, Jellyfin, or Emby.

## Features

- Efficient API integration with Real-Debrid
- Automatic rate limiting to prevent API throttling
- Parallel processing for faster operations
- Colorful terminal interface with progress bars
- Smart optimization to reuse existing downloads from Real-Debrid "My Downloads"
- Intelligent selection of most recent valid downloads when duplicates exist
- Caching system to reduce redundant API calls
- Generates .strm files compatible with Infuse, Jellyfin, and Emby
- Configurable output directory for downloaded content
- Smart organization of media files into appropriate folders
- Link expiration management and automatic refresh
- Health checks for content integrity
- Watch mode for continuous monitoring of new content

## Installation

1. Clone this repository:
```bash
git clone https://github.com/Renoria/robofuse.git
cd robofuse
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

Create or edit the `config.json` file with your settings before running the script:

```json
{
    "token": "YOUR_RD_API_TOKEN",
    "output_dir": "./Library",
    "cache_dir": "./cache",
    "concurrent_requests": 32,
    "general_rate_limit": 60,
    "torrents_rate_limit": 25,
    "watch_mode_enabled": false,
    "watch_mode_refresh_interval": 10,
    "watch_mode_health_check_interval": 60,
    "repair_torrents_enabled": true
}
```

The configuration options explained:
- `token`: Your Real-Debrid API token
- `output_dir`: Directory where STRM files will be created
- `cache_dir`: Directory for caching data to minimize API calls
- `concurrent_requests`: Number of concurrent requests
- `general_rate_limit`: General API rate limit per minute
- `torrents_rate_limit`: Torrents API rate limit per minute
- `watch_mode_enabled`: Enable continuous watch mode
- `watch_mode_refresh_interval`: Seconds between refresh checks in watch mode
- `watch_mode_health_check_interval`: Minutes between health checks in watch mode
- `repair_torrents_enabled`: Enable automatic repair of content

### Getting Your API Token

1. Log in to Real-Debrid
2. Go to Account → API
3. Generate or copy your token

## Usage

After configuring your `config.json` file:

```bash
python robofuse.py [options]
```

### Available Options

| Option | Description |
|--------|-------------|
| `--skip-health-check` | Skip health checks for content and links |
| `--verbose` | Show detailed debug information |
| `--quiet` | Show minimal output |

## What's New in v0.3.5

- **Optimized Download Handling**: The script now intelligently identifies and reuses existing valid downloads from your Real-Debrid "My Downloads" section, significantly reducing API calls for unrestricting links.
- **Smart Duplicate Management**: When multiple download entries exist for the same link, the script now selects the most recent valid download based on generation date.
- **Enhanced Logging**: Improved verbose logging provides more detailed information about download selection and processing.

## Examples

### Basic Usage

The most basic way to run robofuse:

```bash
python robofuse.py
```

### Adjusting Output Verbosity

For use in automated jobs or when you only care about errors:
```bash
python robofuse.py --quiet
```

For troubleshooting or seeing every operation:
```bash
python robofuse.py --verbose
```

### Skipping Health Checks

For faster processing when you know your content is healthy:
```bash
python robofuse.py --skip-health-check
```

### Using Watch Mode

Run robofuse in continuous watch mode to monitor for new content:

```bash
python robofuse.py --watch
```

You can also configure watch mode in your config.json file by setting `watch_mode_enabled` to true.

## Requirements

- Python 3.6+
- requests
- tqdm
- colorama

## License

This project is provided as-is without any warranty. Use at your own risk. 