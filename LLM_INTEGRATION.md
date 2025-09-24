# LLM Integration Guide

This guide covers the Local LLM integration using Ollama in Docker containers for the OzBargain Deal Filter system.

## Overview

The system supports both local Docker-hosted LLM models and external API services for deal evaluation. This document focuses on the local Docker integration using Ollama.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  ozb-deal-filter│    │     ollama      │    │   LLM Models    │
│   (Python App) │◄──►│  (LLM Service)  │◄──►│  (llama2, etc.) │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        │                       │                       │
    Port: App              Port: 11434            Volume: ollama_data
```

## Quick Start

### 1. Start Services

```powershell
# Start all Docker services
docker-compose up -d

# Check service status
docker-compose ps
```

### 2. Install LLM Model

```powershell
# Install recommended model (3.8GB download)
./scripts/manage_models.ps1 -Pull -Model llama2:7b

# Check installation status
./scripts/manage_models.ps1 -Status
```

### 3. Test Integration

```powershell
# Run connectivity tests
python scripts/test_llm_connectivity.py

# Test specific model evaluation
./scripts/manage_models.ps1 -Test -Model llama2:7b
```

## Model Management

### Recommended Models

| Model | Size | Description | Use Case |
|-------|------|-------------|----------|
| `llama2:7b` | 3.8GB | Llama 2 7B | **Recommended** - Best balance of performance and resources |
| `mistral:7b` | 4.1GB | Mistral 7B | **Recommended** - Fast and efficient for text analysis |
| `codellama:7b` | 3.8GB | Code Llama 7B | Good for structured analysis |
| `llama2:13b` | 7.3GB | Llama 2 13B | Higher quality but resource intensive |

### Model Operations

#### Install Models

```powershell
# PowerShell
./scripts/manage_models.ps1 -Pull -Model llama2:7b
./scripts/manage_models.ps1 -Pull -Model mistral:7b

# Bash/Linux
./scripts/manage_models.sh pull llama2:7b
./scripts/manage_models.sh pull mistral:7b
```

#### List Installed Models

```powershell
# PowerShell
./scripts/manage_models.ps1 -List

# Bash/Linux
./scripts/manage_models.sh list
```

#### Remove Models

```powershell
# PowerShell
./scripts/manage_models.ps1 -Remove -Model llama2:7b

# Bash/Linux
./scripts/manage_models.sh remove llama2:7b
```

#### Test Model Performance

```powershell
# PowerShell
./scripts/manage_models.ps1 -Test -Model llama2:7b

# Bash/Linux
./scripts/manage_models.sh test llama2:7b
```

## Configuration

### Docker Compose Configuration

The `docker-compose.yml` includes the Ollama service:

```yaml
ollama:
  image: ollama/ollama:latest
  container_name: ollama
  restart: unless-stopped
  ports:
    - "11434:11434"
  volumes:
    - ollama_data:/root/.ollama
  environment:
    - OLLAMA_HOST=0.0.0.0
  networks:
    - ozb-network
```

### Application Configuration

In your `config/config.yaml`, configure the LLM provider:

```yaml
llm_provider:
  type: "local"  # Use local Docker-hosted models
  local:
    base_url: "http://ollama:11434"  # Internal Docker network
    model: "llama2:7b"
    timeout: 60
    options:
      temperature: 0.7
      top_p: 0.9
      max_tokens: 200
```

For external API access (from host machine):

```yaml
llm_provider:
  type: "local"
  local:
    base_url: "http://localhost:11434"  # External access
    model: "llama2:7b"
```

## Performance Considerations

### System Requirements

| Model Size | RAM Required | Disk Space | CPU Cores |
|------------|--------------|------------|-----------|
| 7B models  | 8GB+         | 5GB+       | 4+        |
| 13B models | 16GB+        | 10GB+      | 8+        |

### Response Times

Typical response times for deal evaluation:

- **First request**: 10-30 seconds (model loading)
- **Subsequent requests**: 2-10 seconds
- **Batch processing**: 1-5 seconds per request

### Optimization Tips

1. **Keep models loaded**: Avoid stopping containers frequently
2. **Use appropriate model size**: Balance quality vs. performance
3. **Adjust timeouts**: Set realistic timeout values in configuration
4. **Monitor resources**: Use `docker stats` to monitor usage

## Troubleshooting

### Common Issues

#### 1. Service Not Accessible

```
Error: Connection refused on localhost:11434
```

**Solutions:**
- Check if containers are running: `docker-compose ps`
- Restart services: `docker-compose restart ollama`
- Check port binding: `docker port ollama`

#### 2. Model Not Found

```
Error: model "llama2:7b" not found
```

**Solutions:**
- Install the model: `./scripts/manage_models.ps1 -Pull -Model llama2:7b`
- Check installed models: `./scripts/manage_models.ps1 -List`
- Verify model name spelling

#### 3. Timeout Errors

```
Error: Read timed out
```

**Solutions:**
- Increase timeout in configuration
- Use smaller model (7B instead of 13B)
- Check system resources with `docker stats`

#### 4. Out of Memory

```
Error: CUDA out of memory / System out of memory
```

**Solutions:**
- Use smaller model
- Increase Docker memory allocation
- Close other applications
- Consider using CPU-only mode

### Diagnostic Commands

```powershell
# Check service health
curl http://localhost:11434/api/tags

# View container logs
docker-compose logs ollama
docker-compose logs ozb-deal-filter

# Monitor resource usage
docker stats

# Test connectivity
python scripts/test_llm_connectivity.py

# Check model status
./scripts/manage_models.ps1 -Status
```

## API Integration

### Direct API Usage

The Ollama API is accessible at `http://localhost:11434` when containers are running.

#### Generate Text

```bash
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama2:7b",
    "prompt": "Analyze this deal: iPhone 14 Pro - $899 (was $1399)",
    "stream": false
  }'
```

#### List Models

```bash
curl http://localhost:11434/api/tags
```

### Python Integration

```python
import requests

def evaluate_deal(deal_text: str, model: str = "llama2:7b") -> str:
    """Evaluate a deal using local LLM"""

    payload = {
        "model": model,
        "prompt": f"Analyze this deal for relevance: {deal_text}",
        "stream": False,
        "options": {
            "temperature": 0.7,
            "max_tokens": 200
        }
    }

    response = requests.post(
        "http://localhost:11434/api/generate",
        json=payload,
        timeout=60
    )

    if response.status_code == 200:
        return response.json()["response"]
    else:
        raise Exception(f"API error: {response.status_code}")

# Usage
result = evaluate_deal("Gaming laptop RTX 4060 - $1200 (was $1500)")
print(result)
```

## Security Considerations

### Network Security

- Ollama service is only accessible within Docker network by default
- External access requires explicit port mapping
- No authentication required for local access

### Data Privacy

- All processing happens locally
- No data sent to external services
- Models and data stored in Docker volumes

### Resource Limits

```yaml
# Add resource limits to docker-compose.yml
ollama:
  # ... other config
  deploy:
    resources:
      limits:
        memory: 8G
        cpus: '4'
      reservations:
        memory: 4G
        cpus: '2'
```

## Backup and Recovery

### Model Backup

```powershell
# Backup all models
docker run --rm -v ozbargin_ollama_data:/data -v ${PWD}:/backup alpine tar czf /backup/ollama_models.tar.gz -C /data .

# Restore models
docker run --rm -v ozbargin_ollama_data:/data -v ${PWD}:/backup alpine tar xzf /backup/ollama_models.tar.gz -C /data
```

### Configuration Backup

```powershell
# Backup configuration
Copy-Item config/config.yaml config/config.backup.yaml

# Backup scripts
Copy-Item -Recurse scripts scripts.backup
```

## Monitoring and Maintenance

### Health Monitoring

```powershell
# Check service health
docker-compose ps
docker-compose logs --tail=50 ollama

# Monitor resource usage
docker stats ollama

# Test API responsiveness
curl -f http://localhost:11434/api/tags
```

### Maintenance Tasks

```powershell
# Update Ollama image
docker pull ollama/ollama:latest
docker-compose up -d --force-recreate ollama

# Clean up unused models
./scripts/manage_models.ps1 -Remove -Model <unused-model>

# Clean up Docker resources
docker system prune -f
```

### Log Management

```powershell
# View recent logs
docker-compose logs --tail=100 -f ollama

# Export logs for analysis
docker-compose logs ollama > ollama.log
```

## Advanced Configuration

### Custom Model Parameters

```yaml
llm_provider:
  local:
    options:
      temperature: 0.7      # Creativity (0.0-1.0)
      top_p: 0.9           # Nucleus sampling
      top_k: 40            # Top-k sampling
      repeat_penalty: 1.1   # Repetition penalty
      max_tokens: 200      # Maximum response length
      stop: ["END", "\n\n"] # Stop sequences
```

### Multiple Model Support

```yaml
llm_provider:
  local:
    models:
      primary: "llama2:7b"
      fallback: "mistral:7b"
    load_balancing: true
    retry_attempts: 3
```

### Performance Tuning

```yaml
ollama:
  environment:
    - OLLAMA_NUM_PARALLEL=2      # Parallel requests
    - OLLAMA_MAX_LOADED_MODELS=2 # Keep models in memory
    - OLLAMA_FLASH_ATTENTION=1   # Enable flash attention
```

This completes the comprehensive LLM integration documentation for the OzBargain Deal Filter system.
