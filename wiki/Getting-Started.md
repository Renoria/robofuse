# Getting Started with robofuse

This guide will help you get robofuse installed, configured, and running quickly.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Basic Configuration](#basic-configuration)
- [First Run](#first-run)
- [Next Steps](#next-steps)

## Prerequisites

Before installing robofuse, ensure you have:

- Python 3.6 or newer installed
- A Real-Debrid account with an API token
- Basic familiarity with command-line interface

## Installation

### Option 1: Stable Version

```bash
# Clone repository
git clone https://github.com/Renoria/robofuse.git
cd robofuse

# Install dependencies
pip install -r requirements.txt
```

### Option 2: Latest Features (v0.3.6+)

```bash
# Clone repository with features branch
git clone -b features https://github.com/Renoria/robofuse.git
cd robofuse

# Install dependencies
pip install -r requirements.txt
```

### Verification

Verify your installation by running:

```bash
python3 robofuse.py --help
```

You should see the help message listing available command options.

## Basic Configuration

Edit the `config.json` file in the robofuse directory with your Real-Debrid API token:

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

Replace `YOUR_RD_API_TOKEN` with your actual Real-Debrid API token.

### Getting Your API Token

1. Log in to your Real-Debrid account at https://real-debrid.com/
2. Go to Account → My Devices
3. Generate or copy your existing token

## First Run

After configuring robofuse, run it for the first time:

```bash
python3 robofuse.py
```

This will:
1. Process any existing torrents in your Real-Debrid account
2. Generate .strm files in the output directory
3. Create a cache for faster future processing

You should see output similar to:

```
robofuse v0.3.6
Checking for existing torrents and downloads...
Found 12 torrents in your Real-Debrid account
Processing torrents...
[================================================] 12/12
Successfully processed 12 torrents.
Generated 58 STRM files in ./Library
```

## Next Steps

Now that you have robofuse up and running, you can:

- Learn about command-line options by running `python3 robofuse.py --help`
- Set up [watch mode](Background-Mode.md#setting-up-watch-mode) to automatically process new torrents
- Deploy using [Docker](Docker-Deployment.md) for a containerized setup
- Configure robofuse to [run in the background](Background-Mode.md)
- Explore [advanced configuration options](Advanced-Configuration.md) 