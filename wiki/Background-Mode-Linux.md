# Running robofuse in Background Mode on Linux

This guide explains how to run the robofuse script in watch mode in the background on Linux, allowing it to continue running even after closing the terminal.

## Table of Contents
- [Initial Setup](#initial-setup)
- [Setting Up Watch Mode](#setting-up-watch-mode)
- [Using Systemd (Recommended)](#using-systemd-recommended)
- [Using Screen or Tmux](#using-screen-or-tmux)
- [Using nohup](#using-nohup)
- [Managing Background Processes](#managing-background-processes)

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

## Using Systemd (Recommended)

Systemd is the modern service manager on most Linux distributions and provides the best way to run robofuse as a background service that automatically starts on boot.

### Step 1: Create a Systemd Service File

1. Create a service file:

```bash
sudo nano /etc/systemd/system/robofuse.service
```

2. Add the following content (adjust paths as needed):

```ini
[Unit]
Description=robofuse Real-Debrid Client
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/path/to/robofuse
ExecStart=/usr/bin/python3 /path/to/robofuse/robofuse.py --watch --summary
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. Replace `YOUR_USERNAME` with your actual username and adjust the paths to match your robofuse installation.

### Step 2: Enable and Start the Service

```bash
# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Enable the service to start automatically on boot
sudo systemctl enable robofuse

# Start the service now
sudo systemctl start robofuse
```

### Step 3: Check Service Status

```bash
sudo systemctl status robofuse
```

You should see output indicating that the service is active (running).

## Using Screen or Tmux

Screen and Tmux are terminal multiplexers that allow you to run sessions in the background.

### Using Screen

1. Install Screen if it's not already installed:

```bash
# Debian/Ubuntu
sudo apt update && sudo apt install screen

# RHEL/CentOS/Fedora
sudo dnf install screen
```

2. Start a new Screen session:

```bash
screen -S robofuse
```

3. Inside the Screen session, start robofuse:

```bash
cd /path/to/robofuse
python3 robofuse.py --watch --summary
```

4. Detach from the Screen session by pressing `Ctrl+A` followed by `D`.

5. To reattach to the session later:

```bash
screen -r robofuse
```

### Using Tmux

1. Install Tmux if it's not already installed:

```bash
# Debian/Ubuntu
sudo apt update && sudo apt install tmux

# RHEL/CentOS/Fedora
sudo dnf install tmux
```

2. Start a new Tmux session:

```bash
tmux new -s robofuse
```

3. Inside the Tmux session, start robofuse:

```bash
cd /path/to/robofuse
python3 robofuse.py --watch --summary
```

4. Detach from the Tmux session by pressing `Ctrl+B` followed by `D`.

5. To reattach to the session later:

```bash
tmux attach -t robofuse
```

## Using nohup

The simplest (but less robust) method is to use `nohup` to make the process immune to hangups.

```bash
cd /path/to/robofuse
nohup python3 robofuse.py --watch --summary > robofuse.log 2>&1 &
```

This will:
- Start robofuse in watch mode
- Redirect output to robofuse.log
- Run the process in the background (the & at the end)
- Make it immune to terminal closing (nohup)

## Managing Background Processes

### Checking if robofuse is Running

```bash
# Find the process ID
ps aux | grep robofuse

# Or if using systemd
sudo systemctl status robofuse
```

### Stopping robofuse

#### If using Systemd:
```bash
sudo systemctl stop robofuse
```

#### If using Screen:
```bash
# Reattach first
screen -r robofuse
# Then press Ctrl+C to stop the script
# To exit the screen session, type 'exit'
```

#### If using Tmux:
```bash
# Reattach first
tmux attach -t robofuse
# Then press Ctrl+C to stop the script
# To exit the tmux session, type 'exit'
```

#### If using nohup:
```bash
# Find the PID
ps aux | grep robofuse
# Kill the process
kill <PID>
```

### Viewing Logs

#### If using Systemd:
```bash
sudo journalctl -u robofuse -f
```

#### If using nohup:
```bash
tail -f robofuse.log
```

### Auto-starting on Boot

If using Systemd, the service will automatically start on boot if you've enabled it.

For other methods, you can add the appropriate command to your user's crontab:

```bash
crontab -e
```

Then add:

```
@reboot cd /path/to/robofuse && nohup python3 robofuse.py --watch --summary > robofuse.log 2>&1 &
``` 