# Running Robofuse in Docker

This guide explains how to run Robofuse in a Docker container, which is ideal for always-on deployments and watch mode.

## Prerequisites

- Docker installed on your system
- Docker Compose (optional, but recommended)
- Your Real-Debrid API token

## Option 1: Using Docker Compose (Recommended)

### Step 1: Prepare Your Environment

Create a new directory for your Robofuse deployment:

```bash
mkdir robofuse-docker
cd robofuse-docker
```

### Step 2: Copy the Configuration Files

Download or copy the following files from the repository:
- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
- `robofuse.py`
- `ui_utils.py`

### Step 3: Configure Your Settings

Create a `config.json` file with your Real-Debrid API token:

```json
{
    "token": "YOUR_RD_API_TOKEN",
    "output_dir": "/data/output",
    "cache_dir": "/data/cache",
    "concurrent_requests": 32,
    "general_rate_limit": 60,
    "torrents_rate_limit": 25,
    "watch_mode_enabled": true,
    "watch_mode_refresh_interval": 10,
    "watch_mode_health_check_interval": 60,
    "repair_torrents_enabled": true
}
```

Make sure to replace `YOUR_RD_API_TOKEN` with your actual Real-Debrid API token.

### Step 4: Launch the Container

```bash
docker-compose up -d
```

This will:
1. Build the Docker image
2. Start the container in the background
3. Configure it to automatically restart if it crashes or if the system reboots

### Step 5: View Logs (Optional)

```bash
docker logs -f robofuse
```

## Option 2: Using Docker CLI

If you prefer not to use Docker Compose, you can use the Docker CLI directly:

### Step 1: Build the Docker Image

```bash
docker build -t robofuse .
```

### Step 2: Run the Container

```bash
docker run -d \
  --name robofuse \
  --restart unless-stopped \
  -v $(pwd)/config.json:/app/config.json \
  -v $(pwd)/output:/data/output \
  -v $(pwd)/cache:/data/cache \
  robofuse
```

## Container Management

### Stopping the Container

```bash
# With Docker Compose
docker-compose down

# With Docker CLI
docker stop robofuse
```

### Restarting the Container

```bash
# With Docker Compose
docker-compose restart

# With Docker CLI
docker restart robofuse
```

### Updating Robofuse

To update to a newer version of Robofuse:

```bash
# With Docker Compose
git pull  # Pull latest changes from the repository
docker-compose down
docker-compose up -d --build

# With Docker CLI
git pull  # Pull latest changes from the repository
docker stop robofuse
docker rm robofuse
docker build -t robofuse .
docker run -d --name robofuse --restart unless-stopped -v $(pwd)/config.json:/app/config.json -v $(pwd)/output:/data/output -v $(pwd)/cache:/data/cache robofuse
```

## Advanced Configuration

### Customizing Command Line Arguments

You can override the default command in the docker-compose.yml file:

```yaml
services:
  robofuse:
    build: .
    container_name: robofuse
    restart: unless-stopped
    volumes:
      - ./config.json:/app/config.json
      - ./output:/data/output
      - ./cache:/data/cache
    command: ["python", "robofuse.py", "--watch", "--verbose"]  # Custom command
```

### Setting Up Volume Mounts in NAS Systems

If you're running Docker on a NAS system like Synology or QNAP, you may need to adjust the volume paths:

```yaml
volumes:
  - /volume1/docker/robofuse/config.json:/app/config.json
  - /volume1/media/robofuse_output:/data/output
  - /volume1/docker/robofuse/cache:/data/cache
``` 