# Troubleshooting Guide

This guide provides solutions for common issues encountered when using robofuse.

## Table of Contents
- [API Authentication Issues](#api-authentication-issues)
- [Rate Limiting Problems](#rate-limiting-problems)
- [File Access Issues](#file-access-issues)
- [Performance Problems](#performance-problems)
- [Watch Mode Issues](#watch-mode-issues)
- [Docker Deployment Issues](#docker-deployment-issues)
- [Link Extraction Problems](#link-extraction-problems)
- [Media Player Compatibility](#media-player-compatibility)

## API Authentication Issues

### Invalid API Token

**Symptoms:**
- Error message: `401 Unauthorized`
- Error message: `Authentication failed`

**Solutions:**
1. Verify your token is correct in `config.json`
2. Generate a new token from Real-Debrid's website:
   - Log in to Real-Debrid
   - Go to Account → My Devices
   - Generate a new token
   - Update your `config.json` file

### API Connection Failed

**Symptoms:**
- Error message: `Could not connect to Real-Debrid API`
- Error message: `Connection timed out`

**Solutions:**
1. Check your internet connection
2. Verify that Real-Debrid services are operational
3. Try using a VPN if your ISP might be blocking the connection
4. Add the `--verbose` flag to get more detailed error information:
   ```bash
   python3 robofuse.py --verbose
   ```

## Rate Limiting Problems

### API Rate Limit Exceeded

**Symptoms:**
- Error message: `429 Too Many Requests`
- Error message: `Rate limit exceeded`

**Solutions:**
1. Decrease `concurrent_requests` in your config.json:
   ```json
   "concurrent_requests": 16  # Try a lower value than default
   ```
2. Adjust rate limits to be more conservative:
   ```json
   "general_rate_limit": 30,
   "torrents_rate_limit": 15
   ```
3. Add delay between runs if you're executing the script frequently
4. Enable the cache system if you've disabled it

## File Access Issues

### Permission Denied

**Symptoms:**
- Error message: `Permission denied when writing to output_dir`
- Error message: `Could not create directory`

**Solutions:**
1. Check directory permissions:
   ```bash
   ls -la ./Library
   ls -la ./cache
   ```
2. Change permissions if needed:
   ```bash
   chmod -R 755 ./Library
   chmod -R 755 ./cache
   ```
3. Run robofuse with elevated privileges (not recommended as permanent solution):
   ```bash
   sudo python3 robofuse.py
   ```

### Missing Directories

**Symptoms:**
- Error message: `No such file or directory`

**Solutions:**
1. Create the required directories manually:
   ```bash
   mkdir -p ./Library
   mkdir -p ./cache
   ```
2. Check if paths in `config.json` are correct and accessible

## Performance Problems

### Slow Processing

**Symptoms:**
- Script takes a very long time to complete
- High CPU usage

**Solutions:**
1. Lower the `concurrent_requests` setting if your system has limited resources
2. Ensure the cache directory is on a fast drive (SSD recommended)
3. Run with `--skip-health-check` to bypass link verification:
   ```bash
   python3 robofuse.py --skip-health-check
   ```
4. Check if other processes are consuming resources on your system

### Memory Usage Issues

**Symptoms:**
- Error message: `MemoryError`
- System becomes unresponsive

**Solutions:**
1. Lower the `concurrent_requests` setting
2. Process smaller batches of torrents at a time
3. Close other memory-intensive applications
4. Add more RAM to your system

## Watch Mode Issues

### Watch Mode Not Detecting New Torrents

**Symptoms:**
- New torrents added to Real-Debrid don't get processed
- No error messages, but nothing happens

**Solutions:**
1. Verify `watch_mode_refresh_interval` isn't set too high
2. Run with `--verbose` to see if API calls are being made:
   ```bash
   python3 robofuse.py --watch --verbose
   ```
3. Check if your API token has correct permissions
4. Try clearing the cache directory and restarting

### Watch Mode Crashes

**Symptoms:**
- Script terminates unexpectedly in watch mode
- Error message: `TypeError: ... has no attribute 'get'`

**Solutions:**
1. Check for error messages to identify the specific issue
2. Update to the latest version of robofuse
3. Run with error output redirected to a file for analysis:
   ```bash
   python3 robofuse.py --watch 2> error.log
   ```
4. If using Docker, check container logs:
   ```bash
   docker logs robofuse
   ```

## Docker Deployment Issues

### Container Fails to Start

**Symptoms:**
- Docker container exits immediately after starting
- Error in Docker logs

**Solutions:**
1. Check Docker logs:
   ```bash
   docker logs robofuse
   ```
2. Verify your config.json file has correct format and permissions
3. Ensure volume mounts are configured correctly in docker-compose.yml
4. Try building the container from scratch:
   ```bash
   docker-compose build --no-cache
   docker-compose up -d
   ```

### Volume Mount Issues

**Symptoms:**
- Files not being created in expected locations
- Error message: `The path /data/output does not exist`

**Solutions:**
1. Check volume mount configuration:
   ```bash
   docker-compose config
   ```
2. Ensure host directories exist before mounting
3. Fix permissions on host directories:
   ```bash
   mkdir -p ./output
   chmod 755 ./output
   ```
4. Use absolute paths in volume mounts

## Link Extraction Problems

### No Valid Links Found

**Symptoms:**
- Error message: `No valid links found for torrent`
- No STRM files are generated

**Solutions:**
1. Verify the torrent has completed downloading on Real-Debrid
2. Check if the torrent contains supported media files
3. Run with verbose logging to see what's happening:
   ```bash
   python3 robofuse.py --verbose
   ```
4. Try manually selecting the torrent on Real-Debrid's website to check available files

### Expired Links

**Symptoms:**
- Media players report errors when opening STRM files
- Error message: `Link expired` or similar in media player

**Solutions:**
1. robofuse automatically refreshes links when in watch mode
2. Re-run robofuse to generate fresh links:
   ```bash
   python3 robofuse.py
   ```
3. Check if `repair_torrents_enabled` is set to `true` in config.json

## Media Player Compatibility

### STRM Files Not Playing

**Symptoms:**
- Media player doesn't recognize STRM files
- Media player opens but doesn't play content

**Solutions:**
1. Verify your media player supports STRM files
2. Try opening the link directly in a web browser to check if it's valid
3. Check media player logs for specific errors
4. Ensure your media player has internet access to fetch the Real-Debrid content 