# Running robofuse in Background Mode on macOS

This guide explains how to run the robofuse script in watch mode in the background on macOS, allowing it to continue running even after closing the terminal window.

## Table of Contents
- [Initial Setup](#initial-setup)
- [Setting Up Watch Mode](#setting-up-watch-mode)
- [Option 1: Using nohup (Simple Method)](#option-1-using-nohup-simple-method)
- [Option 2: Using launchd (macOS Native Method)](#option-2-using-launchd-macos-native-method)
- [Additional Tips](#additional-tips)

## Initial Setup

Before setting up robofuse in background mode, ensure you have completed these initial steps:

1. Clone the repository (if you haven't already):
   ```bash
   git clone -b features https://github.com/Renoria/robofuse.git
   cd robofuse
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your `config.json` file with your Real-Debrid API token:
   ```json
   {
       "token": "YOUR_RD_API_TOKEN",
       "output_dir": "./Library",
       "cache_dir": "./cache"
   }
   ```

4. Test the script first in normal mode to ensure it works correctly:
   ```bash
   python3 robofuse.py
   ```

## Setting Up Watch Mode

For background operation, you should enable watch mode in your `config.json` file:

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

Setting `watch_mode_enabled` to `true` ensures that robofuse automatically starts in watch mode, monitoring for new torrents. This is particularly important for background operation, as it allows robofuse to run continuously and process new content without manual intervention.

You can also pass the `--watch` flag in your commands, but setting it in the config file is more reliable for background operation.

## Option 1: Using nohup (Simple Method)

The quickest solution that requires no additional setup:

```bash
nohup python3 robofuse.py --watch > robofuse.log 2>&1 &
```

This command:
- `nohup` makes the process immune to hangups (continues after terminal closes)
- `> robofuse.log` redirects standard output to a log file
- `2>&1` redirects error messages to the same log file
- `&` runs the process in the background

### Managing the background process

To check if robofuse is running:
```bash
ps aux | grep robofuse
```

To stop the robofuse process:
```bash
pkill -f "python3 robofuse.py --watch"
```

To view the log file:
```bash
cat robofuse.log
```

Or to follow the log in real-time:
```bash
tail -f robofuse.log
```

## Option 2: Using launchd (macOS Native Method)

This is the recommended "Mac way" of creating background services that can auto-start with a virtual environment:

### Step 1: Create a virtual environment

```bash
# Create a virtual environment in the robofuse directory
cd /path/to/robofuse
python3 -m venv venv

# Activate it and install dependencies
source venv/bin/activate
pip install -r requirements.txt

# Deactivate when done with setup
deactivate
```

### Step 2: Create a launch agent plist file

```bash
mkdir -p ~/Library/LaunchAgents
```

Create the plist file (replace `/path/to/robofuse` with your actual path and USERNAME with your macOS username):

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
        <string>cd /path/to/robofuse && source venv/bin/activate && python robofuse.py --watch</string>
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

Make sure to edit the plist file to replace:
- `/path/to/robofuse` with the actual path to your robofuse directory
- `USERNAME` with your actual macOS username

### Step 3: Load the launch agent

```bash
# Set correct permissions
chmod 644 ~/Library/LaunchAgents/com.user.robofuse.plist

# Load the agent
launchctl load ~/Library/LaunchAgents/com.user.robofuse.plist

# Start the service
launchctl start com.user.robofuse
```

### Step 4: Managing the service

To stop the service:
```bash
launchctl unload ~/Library/LaunchAgents/com.user.robofuse.plist
```

To start the service again:
```bash
launchctl load ~/Library/LaunchAgents/com.user.robofuse.plist
```

To check if the service is running:
```bash
launchctl list | grep robofuse
```

### Troubleshooting

If robofuse isn't running correctly, check the error log:

```bash
cat ~/Library/Logs/robofuse_error.log
```

#### Common Issues

1. **Missing Dependencies**: If you see errors about missing modules, ensure your virtual environment is correctly set up:
   ```bash
   cd /path/to/robofuse
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **LibreSSL Warnings**: You might see warnings about LibreSSL compatibility with urllib3. These are generally safe to ignore, but can be fixed by downgrading urllib3:
   ```bash
   source venv/bin/activate
   pip install 'urllib3<2.0'
   ```

### Advantages of the launchd method with virtual environment:
- Uses an isolated Python environment that won't interfere with system packages
- Automatically restarts if it crashes
- Starts when you log in
- Integrates with macOS system management
- Provides separate log files for standard output and errors

## Additional Tips

### Adding Command Line Arguments

If you want to add additional command-line arguments (like `--verbose`), simply add them to the command or the ProgramArguments array in the plist file.

### Log Rotation

For long-running instances, consider implementing log rotation to prevent log files from growing too large:

```bash
logrotate -s /path/to/logrotate.status /path/to/logrotate.conf
```

Where logrotate.conf contains:
```
/path/to/robofuse/robofuse.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
``` 