# Docker Deployment Guide

This guide covers deploying the OzBargain Deal Filter & Alert System using Docker containers on Windows 11.

## Prerequisites

- Docker Desktop for Windows 11
- Git (for automated commits)
- At least 4GB RAM available for containers
- 10GB free disk space for images and volumes

## Quick Start

### 1. Configuration Setup

First, create your configuration file:

```powershell
# Copy the example configuration
Copy-Item config/config.example.yaml config/config.yaml

# Edit the configuration with your settings
notepad config/config.yaml
```

### 2. Build and Start Services

Using PowerShell deployment script:

```powershell
# Build Docker images
.\deploy.ps1 -Build

# Start all services
.\deploy.ps1 -Start
```

Or using docker-compose directly:

```powershell
# Build and start services
docker-compose up -d --build
```

### 3. Monitor Services

```powershell
# Check service status
.\deploy.ps1 -Status

# View logs
.\deploy.ps1 -Logs

# View logs for specific service
.\deploy.ps1 -Logs -Service ozb-deal-filter
```

## Service Architecture

The deployment includes two main services:

### ozb-deal-filter
- Main application container
- Monitors RSS feeds and processes deals
- Sends alerts via configured messaging platform
- Performs automated git commits

### ollama
- Local LLM service for deal evaluation
- Provides AI-powered deal relevance assessment
- Runs models like Llama 2, Mistral, etc.
- Accessible on port 11434

## Volume Mounts

The following directories are mounted as volumes:

- `./config` → `/app/config` (read-only) - Configuration files
- `./prompts` → `/app/prompts` (read-only) - LLM prompt templates
- `./logs` → `/app/logs` - Application logs
- `./.git` → `/app/.git` - Git repository for automated commits
- `ollama_data` - Persistent storage for LLM models

## Configuration

### Environment Variables

The following environment variables are set automatically:

- `CONFIG_PATH=/app/config/config.yaml` - Configuration file path
- `PYTHONPATH=/app` - Python module path
- `PYTHONUNBUFFERED=1` - Unbuffered Python output
- `OLLAMA_HOST=0.0.0.0` - Ollama service host

### Network Configuration

Services communicate via the `ozb-network` bridge network:

- `ozb-deal-filter` → `ollama:11434` for LLM evaluation
- External access to Ollama API on `localhost:11434`

## Health Checks

Both services include health checks:

### ozb-deal-filter
- Command: `python -c "import ozb_deal_filter; print('OK')"`
- Interval: 30 seconds
- Timeout: 10 seconds
- Start period: 40 seconds

### ollama
- Command: `curl -f http://localhost:11434/api/tags`
- Interval: 30 seconds
- Timeout: 10 seconds
- Start period: 60 seconds

## Management Commands

### PowerShell Script (deploy.ps1)

```powershell
# Build images
.\deploy.ps1 -Build

# Start services
.\deploy.ps1 -Start

# Stop services
.\deploy.ps1 -Stop

# Restart services
.\deploy.ps1 -Restart

# View logs
.\deploy.ps1 -Logs
.\deploy.ps1 -Logs -Service ozb-deal-filter

# Check status
.\deploy.ps1 -Status

# Clean up environment
.\deploy.ps1 -Clean
```

### Direct Docker Compose

```powershell
# Build and start
docker-compose up -d --build

# Stop services
docker-compose down

# View logs
docker-compose logs -f
docker-compose logs -f ozb-deal-filter

# Check status
docker-compose ps

# Clean up
docker-compose down -v --remove-orphans
```

## Troubleshooting

### Common Issues

1. **Configuration file not found**
   ```
   Solution: Copy config.example.yaml to config.yaml and edit settings
   ```

2. **Docker not running**
   ```
   Solution: Start Docker Desktop and wait for it to be ready
   ```

3. **Port 11434 already in use**
   ```
   Solution: Stop other Ollama instances or change port in docker-compose.yml
   ```

4. **Permission denied on logs directory**
   ```
   Solution: Ensure logs directory exists and is writable
   mkdir logs
   ```

### Viewing Logs

```powershell
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f ozb-deal-filter
docker-compose logs -f ollama

# Last 100 lines
docker-compose logs --tail=100 ozb-deal-filter
```

### Container Shell Access

```powershell
# Access main application container
docker exec -it ozb-deal-filter bash

# Access Ollama container
docker exec -it ollama bash
```

### Resource Monitoring

```powershell
# Container resource usage
docker stats

# Disk usage
docker system df

# Clean up unused resources
docker system prune -f
```

## Security Considerations

- Application runs as non-root user `app`
- Configuration and prompts mounted read-only
- No sensitive data in environment variables (use config file)
- Git repository mounted for automated commits
- Network isolation via custom bridge network

## Performance Tuning

### Memory Allocation

For better performance, consider adjusting Docker Desktop memory allocation:

1. Open Docker Desktop Settings
2. Go to Resources → Advanced
3. Increase Memory to at least 4GB
4. Apply & Restart

### Ollama Model Management

```powershell
# Pull specific model
docker exec ollama ollama pull llama2

# List available models
docker exec ollama ollama list

# Remove unused models
docker exec ollama ollama rm <model-name>
```

## Backup and Recovery

### Configuration Backup

```powershell
# Backup configuration
Copy-Item config/config.yaml config/config.backup.yaml

# Backup prompts
Copy-Item -Recurse prompts prompts.backup
```

### Volume Backup

```powershell
# Backup Ollama models
docker run --rm -v ozbargin_ollama_data:/data -v ${PWD}:/backup alpine tar czf /backup/ollama_backup.tar.gz -C /data .

# Restore Ollama models
docker run --rm -v ozbargin_ollama_data:/data -v ${PWD}:/backup alpine tar xzf /backup/ollama_backup.tar.gz -C /data
```

## Monitoring and Maintenance

### Log Rotation

Logs are stored in the `./logs` directory. Consider implementing log rotation:

```powershell
# Manual log cleanup (keep last 7 days)
Get-ChildItem logs/*.log | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | Remove-Item
```

### Updates

```powershell
# Update application
git pull
.\deploy.ps1 -Build
.\deploy.ps1 -Restart

# Update Ollama
docker pull ollama/ollama:latest
.\deploy.ps1 -Restart
```