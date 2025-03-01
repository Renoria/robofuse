# Running robofuse in Background Mode on macOS

This guide explains how to set up robofuse to run automatically in the background on macOS using Launch Agents with a Python virtual environment.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Setting Up robofuse as a Background Service](#setting-up-robofuse-as-a-background-service)
- [Managing the Service](#managing-the-service)
- [Troubleshooting](#troubleshooting)
- [Additional Tips](#additional-tips)

## Prerequisites

- macOS 10.15 (Catalina) or newer
- Python 3.6 or newer
- Terminal access

## Setting Up robofuse as a Background Service

### Step 1: Clone the Repository

Clone the repository to your home directory:

```bash
git clone -b features https://github.com/Renoria/robofuse.git ~/robofuse
```

Navigate to the robofuse directory:

```bash
cd ~/robofuse
```

### Step 2: Create and Configure a Virtual Environment

Create a virtual environment:

```bash
python3 -m venv venv
```

Activate the virtual environment:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Deactivate the virtual environment when done:

```bash
deactivate
```

### Step 3: Configure robofuse

Create or edit your `config.json` file with your Real-Debrid API token and watch mode settings:

```bash
# Edit the configuration file
nano config.json
```

Your config.json should include:

```json
{
    "token": "YOUR_RD_API_TOKEN",
    "output_dir": "./Library",
    "cache_dir": "./cache",
    "watch_mode_enabled": true,
    "watch_mode_refresh_interval": 10,
    "watch_mode_health_check_interval": 60
}
```

The `watch_mode_enabled` setting ensures robofuse automatically monitors for new torrents. You can also pass the `--watch` flag in your launch agent, but setting it in the config file provides redundancy.

### Step 4: Create a Launch Agent

Create a new file in ~/Library/LaunchAgents directory:

```bash
mkdir -p ~/Library/LaunchAgents
```

Create the plist file (replacing USERNAME with your actual macOS username):

```bash
cat > ~/Library/LaunchAgents/com.user.robofuse.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.robofuse</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>cd ~/robofuse && source venv/bin/activate && python robofuse.py --watch</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/USERNAME/Library/Logs/robofuse.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/USERNAME/Library/Logs/robofuse_error.log</string>
</dict>
</plist>
EOF
```

Make sure to edit the plist file to replace `USERNAME` with your actual macOS username.

### Step 5: Load the Launch Agent

Set correct permissions:

```bash
chmod 644 ~/Library/LaunchAgents/com.user.robofuse.plist
```

Load the agent:

```bash
launchctl load ~/Library/LaunchAgents/com.user.robofuse.plist
```

Start the service:

```bash
launchctl start com.user.robofuse
```

## Managing the Service

### Checking Service Status

Check if service is listed:

```bash
launchctl list | grep robofuse
```

View the log output:

```bash
cat ~/Library/Logs/robofuse.log
```

### Starting and Stopping the Service

To stop the service:
```bash
launchctl unload ~/Library/LaunchAgents/com.user.robofuse.plist
```

To start the service again:
```bash
launchctl load ~/Library/LaunchAgents/com.user.robofuse.plist
```

To restart the service (for example, after updating robofuse):
```bash
launchctl unload ~/Library/LaunchAgents/com.user.robofuse.plist
launchctl load ~/Library/LaunchAgents/com.user.robofuse.plist
```

## Troubleshooting

### Checking for Errors

If robofuse isn't running correctly, check the error log:

```bash
cat ~/Library/Logs/robofuse_error.log
```

For real-time monitoring:
```bash
tail -f ~/Library/Logs/robofuse.log
```

### Common Issues

1. **Missing Dependencies**: If you see errors about missing modules:
   ```bash
   cd ~/robofuse
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **LibreSSL Warnings**: You might see warnings about LibreSSL compatibility with urllib3. These are generally safe to ignore, but can be fixed by:
   ```bash
   cd ~/robofuse
   source venv/bin/activate
   pip install 'urllib3<2.0'
   ```

3. **Permission Issues**: Ensure robofuse.py is executable:
   ```bash
   chmod +x ~/robofuse/robofuse.py
   ```

## Additional Tips

### Adding Command Line Arguments

If you want to add additional command-line arguments (like `--verbose`), modify the string in your plist file:

```xml
<string>cd ~/robofuse && source venv/bin/activate && python robofuse.py --watch --verbose</string>
```

### Updating robofuse

When a new version is available:

```bash
# Stop the service
launchctl unload ~/Library/LaunchAgents/com.user.robofuse.plist

# Update the repository
cd ~/robofuse
git pull

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt
deactivate

# Restart the service
launchctl load ~/Library/LaunchAgents/com.user.robofuse.plist
```

### Log Rotation

For long-running instances, consider implementing log rotation.

Create the logrotate configuration (replace USERNAME with your actual macOS username):

```bash
cat > ~/robofuse_logrotate.conf << EOF
/Users/USERNAME/Library/Logs/robofuse.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
/Users/USERNAME/Library/Logs/robofuse_error.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
EOF
```

Make sure to edit the configuration file to replace `USERNAME` with your actual macOS username.

Add to your crontab (opens editor):

```bash
crontab -e
```

Add this line to your crontab:

```
0 0 * * * /usr/sbin/logrotate -s ~/robofuse_logrotate.status ~/robofuse_logrotate.conf
``` 