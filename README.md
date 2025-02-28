# robofuse

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Version](https://img.shields.io/badge/version-0.3.6-green)

A Python-based utility for interacting with Real-Debrid API services efficiently with smart rate limiting and parallel processing. robofuse generates .strm files that can be used in media players like Infuse, Jellyfin, or Emby.

## Table of Contents
- [Quick Start](#quick-start)
- [Features](#features)
- [Documentation](#documentation)
- [Installation](#installation)
- [Basic Configuration](#basic-configuration)
- [Common Usage](#common-usage)
- [Requirements](#requirements)
- [License](#license)

## Quick Start

```bash
# Clone repository (features branch for latest improvements)
git clone -b features https://github.com/Renoria/robofuse.git
cd robofuse

# Install dependencies
pip install -r requirements.txt

# Configure with your API token
# Edit config.json and replace YOUR_RD_API_TOKEN with your actual token

# Run
python3 robofuse.py
```

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

- [Getting Started Guide](wiki/Getting-Started.md) - Detailed setup instructions
- [User Guide](wiki/User-Guide.md) - Complete usage documentation
- [Running in Background Mode (macOS)](wiki/Background-Mode.md) - Run in background on macOS
- [Running in Background Mode (Windows)](wiki/Background-Mode-Windows.md) - Run in background on Windows
- [Running in Background Mode (Linux)](wiki/Background-Mode-Linux.md) - Run in background on Linux
- [Docker Deployment](wiki/Docker-Deployment.md) - Deploy with Docker
- [Advanced Configuration](wiki/Advanced-Configuration.md) - All configuration options
- [Troubleshooting](wiki/Troubleshooting.md) - Common issues and solutions
- [FAQ](wiki/FAQ.md) - Frequently asked questions

## Installation

1. Clone this repository:

### Stable version
```bash
git clone https://github.com/Renoria/robofuse.git
cd robofuse
```

### Latest improvements (v0.3.6+)
```bash
git clone -b features https://github.com/Renoria/robofuse.git
cd robofuse
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Basic Configuration

Create or edit the `config.json` file with your settings:

```json
{
    "token": "YOUR_RD_API_TOKEN",
    "output_dir": "./Library",
    "cache_dir": "./cache"
}
```

**Essential settings:**
- `token`: Your Real-Debrid API token (required)
- `output_dir`: Directory where STRM files will be created
- `cache_dir`: Directory for caching data to minimize API calls

See [Advanced Configuration](wiki/Advanced-Configuration.md) for all options.

### Getting Your API Token

1. Log in to Real-Debrid
2. Go to Account → My Devices
3. Generate or copy your token

## Common Usage

Basic operation:
```bash
python3 robofuse.py
```

Run in watch mode (monitors for new torrents):
```bash
python3 robofuse.py --watch
```

For more examples and advanced usage, see the [User Guide](wiki/User-Guide.md).

## Requirements

- Python 3.6+
- requests
- tqdm
- colorama

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

_This documentation and the robofuse improvements were made possible by my good friend Claude 3.7 Sonnet. Thanks, buddy!_ 