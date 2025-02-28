#!/usr/bin/env python3
import time
import sys
import os
import shutil
from datetime import datetime, timedelta
from enum import IntEnum

# ANSI color codes
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    
    # Background colors
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

class LogLevel(IntEnum):
    ERROR = 0
    WARNING = 1
    INFO = 2
    DEBUG = 3
    TRACE = 4

# Global variables
CURRENT_LOG_LEVEL = LogLevel.INFO
SHOW_PROGRESS = True
TERMINAL_WIDTH = shutil.get_terminal_size().columns
verbose = False  # Add verbose flag global variable

def set_log_level(level):
    """Set the global log level."""
    global CURRENT_LOG_LEVEL, verbose
    CURRENT_LOG_LEVEL = level
    
    # Automatically set verbose flag based on log level
    # DEBUG and TRACE levels should enable verbose output
    verbose = (level.value >= LogLevel.DEBUG.value)

def set_progress_display(show):
    """Control whether to show progress indicators."""
    global SHOW_PROGRESS
    SHOW_PROGRESS = show

def log(message, level=LogLevel.INFO, end="\n"):
    """Log a message with the specified level."""
    if level.value > CURRENT_LOG_LEVEL.value:
        return
    
    prefix = ""
    color = ""
    
    if level == LogLevel.ERROR:
        prefix = "[ERROR] "
        color = Color.RED
    elif level == LogLevel.WARNING:
        prefix = "[WARNING] "
        color = Color.YELLOW
    elif level == LogLevel.INFO:
        prefix = "[INFO] "
        color = Color.GREEN
    elif level == LogLevel.DEBUG:
        prefix = "[DEBUG] "
        color = Color.BLUE
    elif level == LogLevel.TRACE:
        prefix = "[TRACE] "
        color = Color.MAGENTA
    
    print(f"{color}{prefix}{message}{Color.RESET}", end=end)

def success(message):
    """Log a success message."""
    # Success messages should be visible at INFO level and above
    if CURRENT_LOG_LEVEL.value >= LogLevel.INFO.value:
        print(f"{Color.BRIGHT_GREEN}✓ {message}{Color.RESET}")

def error(message):
    """Log an error message."""
    # Error messages are always visible
    print(f"{Color.BRIGHT_RED}✗ {message}{Color.RESET}")

def warning(message):
    """Log a warning message."""
    # Warning messages should be visible at WARNING level and above
    if CURRENT_LOG_LEVEL.value >= LogLevel.WARNING.value:
        print(f"{Color.BRIGHT_YELLOW}⚠ {message}{Color.RESET}")

def info(message):
    """Log an informational message."""
    # Info messages should be visible at INFO level and above
    if CURRENT_LOG_LEVEL.value >= LogLevel.INFO.value:
        print(f"{Color.BRIGHT_BLUE}ℹ {message}{Color.RESET}")

def debug(message):
    """Log a debug message."""
    # Debug messages should be visible at DEBUG level and above
    if CURRENT_LOG_LEVEL.value >= LogLevel.DEBUG.value:
        print(f"{Color.BLUE}🔍 {message}{Color.RESET}")

def trace(message):
    """Log a trace message."""
    # Trace messages should be visible at TRACE level
    if CURRENT_LOG_LEVEL.value >= LogLevel.TRACE.value:
        print(f"{Color.MAGENTA}🔎 {message}{Color.RESET}")

def processing(message):
    """Log a processing message."""
    print(f"{Color.BRIGHT_CYAN}⟳ {message}{Color.RESET}")

def file_status(filename, status, details=None):
    """Display a file with its status."""
    status_icon = ""
    color = ""
    
    if status == "success":
        status_icon = "✓"
        color = Color.BRIGHT_GREEN
    elif status == "error":
        status_icon = "✗"
        color = Color.BRIGHT_RED
    elif status == "warning":
        status_icon = "⚠"
        color = Color.BRIGHT_YELLOW
    elif status == "processing":
        status_icon = "⟳"
        color = Color.BRIGHT_CYAN
    elif status == "skipped":
        status_icon = "•"
        color = Color.BRIGHT_MAGENTA
    
    message = f"{color}{status_icon} {filename}{Color.RESET}"
    if details:
        message += f" {Color.BRIGHT_WHITE}({details}){Color.RESET}"
    
    print(message)

def progress_bar(current, total, prefix='', suffix='', length=50, fill='█'):
    """Display a progress bar."""
    if not SHOW_PROGRESS:
        return
    
    percent = int(100 * (current / float(total)))
    filled_length = int(length * current // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
    sys.stdout.flush()
    
    if current == total:
        sys.stdout.write('\n')
        sys.stdout.flush()

def spinner(message, iterable):
    """Display a spinner while iterating."""
    if not SHOW_PROGRESS:
        for item in iterable:
            yield item
        return
    
    spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    start_time = time.time()
    total = len(iterable) if hasattr(iterable, '__len__') else None
    
    for i, item in enumerate(iterable, 1):
        elapsed = time.time() - start_time
        spinner_char = spinner_chars[int(elapsed * 10) % len(spinner_chars)]
        
        if total:
            rate = i / elapsed if elapsed > 0 else 0
            eta = (total - i) / rate if rate > 0 else 0
            eta_str = f"ETA: {format_time(eta)}" if eta > 0 else ""
            status = f"{spinner_char} {message}: {i}/{total} [{format_time(elapsed)}] {eta_str} (Rate: {rate:.1f}/s)"
        else:
            status = f"{spinner_char} {message} [{format_time(elapsed)}]"
        
        status = status.ljust(TERMINAL_WIDTH)
        sys.stdout.write(f"\r{status}")
        sys.stdout.flush()
        
        yield item
    
    # Clear the spinner line when done
    sys.stdout.write("\r" + " " * TERMINAL_WIDTH + "\r")
    sys.stdout.flush()

def format_time(seconds):
    """Format time in seconds to a human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

def format_size(size_bytes):
    """Format size in bytes to a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes/(1024*1024):.1f} MB"
    else:
        return f"{size_bytes/(1024*1024*1024):.2f} GB"

def print_summary_box(title, items):
    """Print a fancy summary box with statistics."""
    # Check current log level - if in quiet mode, show minimal output
    if CURRENT_LOG_LEVEL <= LogLevel.WARNING:
        # For quiet mode, just show a minimal single-line summary with the most important stats
        critical_stats = []
        
        # Select only the most important statistics
        for key in ["Total download links saved", "Torrents with errors", "Total runtime"]:
            if key in items:
                critical_stats.append(f"{key}: {items[key]}")
        
        if critical_stats:
            print(f"{title}: {' | '.join(critical_stats)}")
        return
    
    # Full detailed box for normal and verbose modes
    # Find the longest item to determine box width
    max_length = max([len(f"{k}: {v}") for k, v in items.items()]) + 4
    width = max(max_length, len(title) + 4)
    
    # Print the box
    print(f"╭─ {title} {'─' * (width - len(title) - 4)}╮")
    
    for key, value in items.items():
        if isinstance(value, (int, float)) and value > 0:
            value_str = f"{Color.BRIGHT_GREEN}{value}{Color.RESET}"
        elif isinstance(value, (int, float)) and value < 0:
            value_str = f"{Color.BRIGHT_RED}{value}{Color.RESET}"
        elif isinstance(value, str) and ("success" in value.lower() or "complete" in value.lower()):
            value_str = f"{Color.BRIGHT_GREEN}{value}{Color.RESET}"
        elif isinstance(value, str) and ("error" in value.lower() or "fail" in value.lower()):
            value_str = f"{Color.BRIGHT_RED}{value}{Color.RESET}"
        elif isinstance(value, str) and ("warning" in value.lower() or "caution" in value.lower()):
            value_str = f"{Color.BRIGHT_YELLOW}{value}{Color.RESET}"
        else:
            value_str = str(value)
        
        line = f"│ {key}: {value_str}"
        padding = width - len(key) - len(str(value)) - 4
        print(f"{line}{' ' * padding}│")
    
    print(f"╰{'─' * width}╯") 