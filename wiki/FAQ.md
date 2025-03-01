# Frequently Asked Questions

## General Questions

### What is robofuse?
robofuse is a Python utility that interacts with Real-Debrid's API to process torrents and generate STRM files, which can be used in media players like Infuse, Jellyfin, or Emby.

### Is robofuse free to use?
Yes, robofuse is open-source software licensed under the MIT License. However, you will need a Real-Debrid subscription to use the service it connects to.

### Do I need a Real-Debrid account?
Yes, robofuse is designed to work with Real-Debrid and requires an account with them.

### What platforms does robofuse support?
robofuse works on any platform that supports Python 3.6 or newer, including Windows, macOS, Linux, and NAS devices that support Docker.

## Setup and Configuration

### How do I get my Real-Debrid API token?
Log in to Real-Debrid, go to Account → My Devices, and either copy your existing token or generate a new one.

### How often should I run robofuse?
It depends on your usage pattern:
- For active users who frequently add new torrents, running in watch mode (`--watch` flag) is recommended.
- For occasional users, running it manually when you add new torrents is sufficient.

### Can I use robofuse with multiple Real-Debrid accounts?
Not with a single instance. You would need to run separate instances with different configuration files.

### Where should I put my STRM files?
The STRM files are generated in the `output_dir` specified in your `config.json`. This directory should be accessible to your media player or media server.

## Functionality

### What is watch mode?
Watch mode is a feature that makes robofuse continuously check your Real-Debrid account for new torrents and automatically process them when detected.

### Does robofuse download the actual media files?
No, robofuse generates STRM files which contain links to stream the content directly from Real-Debrid's servers. Your media player will access these streams when you play the content.

### What are STRM files?
STRM files are simple text files containing URLs. When opened in a compatible media player, they tell the player to stream content from that URL rather than playing a local file.

### What media formats does robofuse support?
robofuse supports all media formats that Real-Debrid can handle, including:
- Video: MP4, MKV, AVI, etc.
- Audio: MP3, FLAC, etc.

### Does robofuse handle subtitles?
robofuse processes subtitle files if they are included in the torrent, but displaying them depends on your media player's capabilities.

## Performance and Optimization

### Why is robofuse slow on first run?
The first run requires fetching all your torrents and download information from Real-Debrid. This data is then cached locally for faster access in subsequent runs.

### How can I make robofuse run faster?
- Increase the `concurrent_requests` value in your config (if your system can handle it)
- Use an SSD for the cache directory
- Run with `--skip-health-check` if you're confident in your link quality

### How much disk space does robofuse require?
The space required depends on the number of torrents in your Real-Debrid account:
- STRM files are tiny (a few KB each)
- Cache files take up more space, typically a few MB to GB for accounts with many torrents

### Is there a limit to how many torrents robofuse can handle?
There is no hard limit within robofuse, but Real-Debrid has its own limitations on how many torrents you can have active.

## Troubleshooting

### Why am I getting "API rate limit exceeded" errors?
Real-Debrid limits how many API requests you can make. Try lowering the `concurrent_requests` setting in your config.json.

### My STRM files don't play in my media player. What's wrong?
- Verify your media player supports STRM files
- Check if your media player has internet access
- The link may have expired; try re-running robofuse to refresh it
- Run robofuse with `--verbose` to get more information

### robofuse doesn't see all my torrents. Why?
- Check if the torrents are actually visible in your Real-Debrid account
- Verify your API token has the correct permissions
- Try clearing the cache directory and restarting

### Do I need to keep robofuse running all the time?
Only if you're using watch mode to automatically process new torrents. Otherwise, you can run it manually as needed.

### What command-line options are available?
robofuse supports several command-line options to control its behavior:

- `--watch`: Run in watch mode to continuously monitor for new torrents
- `--verbose`: Enable verbose logging for debugging
- `--quiet`: Suppress most output
- `--summary`: Show only summary information, reducing output
- `--skip-health-check`: Skip checking health of existing links
- `--repair-torrents`: Enable automatic repair of unhealthy torrents
- `--no-repair-torrents`: Disable automatic repair of unhealthy torrents
- `--no-cache`: Disable using the cache
- `--output-dir PATH`: Override the output directory specified in config.json
- `--cache-dir PATH`: Override the cache directory specified in config.json
- `--concurrent N`: Number of concurrent requests
- `--general-rate-limit N`: General API rate limit in requests per minute
- `--torrents-rate-limit N`: Torrents API rate limit in requests per minute
- `--watch-refresh-interval N`: Refresh interval in minutes for watch mode
- `--watch-health-interval N`: Health check interval in minutes for watch mode
- `--help` or `-h`: Display all available options and their descriptions

You can see the complete list of options by running: `python3 robofuse.py --help`

## Docker and Deployment

### Can I run robofuse in a Docker container?
Yes, robofuse supports Docker deployment. See [Docker Deployment](Docker-Deployment.md) for instructions.

### How do I make robofuse start automatically on system boot?
- On Linux/macOS: Set up a systemd service or launchd agent
- On Windows: Create a scheduled task
- Using Docker: Configure the container with `restart: always`

### Can robofuse run on a NAS device?
Yes, if your NAS supports Docker or Python. Many users run robofuse on Synology or QNAP NAS devices.

### How do I update robofuse to the newest version?
```bash
git pull
```

If you're using Docker:
```bash
docker-compose pull
docker-compose up -d --build
``` 