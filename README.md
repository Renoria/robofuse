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
- Docker support for containerized deployments

## Documentation

For detailed documentation, check the [wiki](wiki/Home.md) in this repository:

- [Running in Background Mode (macOS)](wiki/Background-Mode.md)
- [Docker Deployment](wiki/Docker-Deployment.md)

## Installation

1. Clone this repository:

### Stable version
```bash
git clone https://github.com/Renoria/robofuse.git
cd robofuse
```

### Latest improvements (v0.3.5+)
```bash
git clone -b features https://github.com/Renoria/robofuse.git
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
| `--quiet` | Show minimal output (errors only) |
| `--summary` | Show only summary and warning information (great for cron jobs) |
| `--watch` | Run in continuous watch mode |

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

For concise summaries with warnings (ideal for cron jobs):
```bash
python robofuse.py --summary
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

## Utility Scripts

Robofuse includes additional utility scripts to help manage your Real-Debrid account:

### Cleaning Up Downloads

To remove all downloads from your Real-Debrid "My Downloads" section:

```bash
python robofuse_clear_downloads.py
```

Options:
- `--force`: Skip confirmation prompt
  
### Removing Duplicate Downloads

To find and remove duplicate downloads, keeping only the most recent one for each unique link:

```bash
python robofuse_remove_duplicates.py
```

Options:
- `--force`: Skip confirmation prompt
- `--dry-run`: Show what would be deleted without actually deleting anything

## Requirements

- Python 3.6+
- requests
- tqdm
- colorama

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2024 Renoria

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files, to deal in the software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the software, and to permit persons to whom the software is furnished to do so, subject to the following conditions:

The software is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages or other liability, whether in an action of contract, tort or otherwise, arising from, out of or in connection with the software or the use or other dealings in the software. 