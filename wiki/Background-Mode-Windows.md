# Running robofuse in Background Mode on Windows

This guide explains how to run the robofuse script in watch mode in the background on Windows, allowing it to continue running even after closing the command prompt window.

## Table of Contents
- [Initial Setup](#initial-setup)
- [Setting Up Watch Mode](#setting-up-watch-mode)
- [Using Task Scheduler (Recommended)](#using-task-scheduler-recommended)
- [Using PowerShell](#using-powershell)
- [Using NSSM (Non-Sucking Service Manager)](#using-nssm-non-sucking-service-manager)
- [Managing Background Processes](#managing-background-processes)

## Initial Setup

Before setting up robofuse in background mode, ensure you have completed these initial steps:

1. Clone the repository (if you haven't already):
   ```batch
   git clone -b features https://github.com/Renoria/robofuse.git
   cd robofuse
   ```

2. Install the required dependencies:
   ```batch
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
   ```batch
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

## Using Task Scheduler (Recommended)

Windows Task Scheduler provides a native way to run robofuse in the background and have it automatically start on system boot.

### Step 1: Create a Batch File

First, create a batch file to run robofuse:

1. Open Notepad and paste the following (adjust paths as needed):
```batch
@echo off
cd /d C:\path\to\robofuse
python3 robofuse.py --watch --summary > C:\path\to\robofuse\logs\robofuse.log 2>&1
```

2. Save the file as `run_robofuse.bat` in your robofuse directory.

### Step 2: Create a Scheduled Task

1. Open Task Scheduler (search for it in the Start menu)
2. Click "Create Basic Task..."
3. Enter a name (e.g., "robofuse") and description, then click "Next"
4. Select "When the computer starts" and click "Next"
5. Select "Start a program" and click "Next"
6. Click "Browse..." and select your `run_robofuse.bat` file
7. Click "Next" and then "Finish"

### Step 3: Configure Advanced Settings

1. Find your task in the Task Scheduler Library
2. Right-click it and select "Properties"
3. On the "General" tab, check "Run whether user is logged on or not"
4. On the "Conditions" tab, uncheck "Start the task only if the computer is on AC power"
5. On the "Settings" tab, uncheck "Stop the task if it runs longer than"
6. Click "OK" to save changes

## Using PowerShell

PowerShell can run processes in the background with the `Start-Process` cmdlet.

### Running in the Background

```powershell
Start-Process -FilePath "python3" -ArgumentList "robofuse.py --watch --summary" -WorkingDirectory "C:\path\to\robofuse" -WindowStyle Hidden -RedirectStandardOutput "C:\path\to\robofuse\logs\robofuse.log" -RedirectStandardError "C:\path\to\robofuse\logs\robofuse_error.log"
```

### Creating a PowerShell Script

1. Create a file named `start_robofuse.ps1` with the above command
2. To run it, right-click the file and select "Run with PowerShell"

### Auto-starting with PowerShell

To make the PowerShell script run at startup:

1. Press Win+R and type `shell:startup`
2. Create a shortcut to your PowerShell script in this folder
3. Right-click the shortcut, select Properties, and set the Run property to "Minimized"

## Using NSSM (Non-Sucking Service Manager)

NSSM allows you to create a Windows service that runs robofuse, which is ideal for servers or always-on systems.

### Step 1: Download NSSM

1. Download NSSM from [nssm.cc](https://nssm.cc/download)
2. Extract the zip file to a folder on your system

### Step 2: Install robofuse as a Service

1. Open Command Prompt as Administrator
2. Navigate to the NSSM directory
3. Run the following command:
```batch
nssm install robofuse
```
4. In the dialog that appears:
   - Path: `C:\Path\to\Python\python.exe`
   - Startup directory: `C:\path\to\robofuse`
   - Arguments: `robofuse.py --watch --summary`
   - On the I/O tab, set Output and Error to log files
5. Click "Install service"

### Step 3: Start the Service

1. Open Command Prompt as Administrator
2. Run:
```batch
net start robofuse
```

## Managing Background Processes

### Checking if robofuse is Running

To check if robofuse is running in the background:

```batch
tasklist | findstr python
```

### Stopping robofuse

#### If using Task Scheduler:
1. Open Task Scheduler
2. Right-click your robofuse task
3. Select "End"

#### If using PowerShell:
```powershell
Get-Process | Where-Object {$_.CommandLine -like "*robofuse.py*"} | Stop-Process
```

#### If using NSSM:
```batch
net stop robofuse
```

### Viewing Logs

To follow the log file in real-time using PowerShell:

```powershell
Get-Content -Path "C:\path\to\robofuse\logs\robofuse.log" -Wait
``` 