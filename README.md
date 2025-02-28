# robofuse
## v0.2.4

A Python-based utility for interacting with Real-Debrid API services efficiently with smart rate limiting and parallel processing. Robofuse generates .strm files that can be used in media players like Infuse, Jellyfin, or Emby.

## Features

- Efficient API integration with Real-Debrid
- Automatic rate limiting to prevent API throttling
- Parallel processing for faster operations
- Colorful terminal interface with progress bars
- Caching system to reduce redundant API calls
- Generates .strm files compatible with Infuse, Jellyfin, and Emby
- Configurable output directory for downloaded content

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
    "token": "RD_API",
    "output_dir": "./Library",
    "cache_dir": "./cache",
    "concurrent_requests": 32,
    "general_rate_limit": 60,
    "torrents_rate_limit": 25
}
```

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

### Examples

Basic usage (using settings from config.json):
```bash
python robofuse.py
```

With verbose output:
```bash
python robofuse.py --verbose
```

Skipping health checks:
```bash
python robofuse.py --skip-health-check
```

## Requirements

- Python 3.6+
- requests
- tqdm
- colorama

## License

This project is provided as-is without any warranty. Use at your own risk. 