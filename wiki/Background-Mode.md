# Running Robofuse in Background Mode on macOS

This guide explains how to run the Robofuse script in watch mode in the background on macOS, allowing it to continue running even after closing the terminal window.

## Option 1: Using `nohup` (Simple Method)

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

To check if Robofuse is running:
```bash
ps aux | grep robofuse
```

To stop the Robofuse process:
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

This is the recommended "Mac way" of creating background services that can auto-start:

### Step 1: Create a launch agent plist file

```bash
mkdir -p ~/Library/LaunchAgents
```

Create the plist file (replace `/path/to/robofuse` with your actual path):

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
        <string>/usr/bin/python3</string>
        <string>/path/to/robofuse/robofuse.py</string>
        <string>--watch</string>
        <string>--summary</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/path/to/robofuse/robofuse.log</string>
    <key>StandardErrorPath</key>
    <string>/path/to/robofuse/robofuse.error.log</string>
    <key>WorkingDirectory</key>
    <string>/path/to/robofuse</string>
</dict>
</plist>
EOF
```

Make sure to edit the plist file to replace `/path/to/robofuse` with the actual path to your robofuse directory.

### Step 2: Load the launch agent

```bash
launchctl load ~/Library/LaunchAgents/com.user.robofuse.plist
```

### Step 3: Managing the service

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

### Advantages of the launchd method:
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