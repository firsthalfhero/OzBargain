# OzBargain Deal Filter - Docker Deployment Script for Windows 11
# This script handles the complete deployment process

param(
    [switch]$Build,
    [switch]$Start,
    [switch]$Stop,
    [switch]$Restart,
    [switch]$Logs,
    [switch]$Status,
    [switch]$Clean,
    [string]$Service = ""
)

# Colors for output
$Red = "`e[31m"
$Green = "`e[32m"
$Yellow = "`e[33m"
$Blue = "`e[34m"
$Reset = "`e[0m"

function Write-ColorOutput {
    param([string]$Message, [string]$Color = $Reset)
    Write-Host "$Color$Message$Reset"
}

function Test-DockerRunning {
    try {
        docker version | Out-Null
        return $true
    }
    catch {
        Write-ColorOutput "Docker is not running. Please start Docker Desktop." $Red
        return $false
    }
}

function Test-ConfigExists {
    if (-not (Test-Path "config/config.yaml")) {
        Write-ColorOutput "Configuration file not found. Creating from template..." $Yellow
        if (Test-Path "config/config.example.yaml") {
            Copy-Item "config/config.example.yaml" "config/config.yaml"
            Write-ColorOutput "Please edit config/config.yaml with your settings before starting." $Yellow
            return $false
        }
        else {
            Write-ColorOutput "No configuration template found. Please create config/config.yaml" $Red
            return $false
        }
    }
    return $true
}

function Build-Services {
    Write-ColorOutput "Building Docker images..." $Blue
    docker-compose build --no-cache
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput "Build completed successfully!" $Green
    }
    else {
        Write-ColorOutput "Build failed!" $Red
        exit 1
    }
}

function Start-Services {
    Write-ColorOutput "Starting services..." $Blue
    docker-compose up -d
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput "Services started successfully!" $Green
        Write-ColorOutput "Use 'docker-compose logs -f' to view logs" $Yellow
    }
    else {
        Write-ColorOutput "Failed to start services!" $Red
        exit 1
    }
}

function Stop-Services {
    Write-ColorOutput "Stopping services..." $Blue
    docker-compose down
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput "Services stopped successfully!" $Green
    }
    else {
        Write-ColorOutput "Failed to stop services!" $Red
    }
}

function Show-Logs {
    if ($Service) {
        docker-compose logs -f $Service
    }
    else {
        docker-compose logs -f
    }
}

function Show-Status {
    Write-ColorOutput "Service Status:" $Blue
    docker-compose ps
    Write-ColorOutput "`nContainer Health:" $Blue
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

function Clean-Environment {
    Write-ColorOutput "Cleaning up Docker environment..." $Yellow
    docker-compose down -v --remove-orphans
    docker system prune -f
    Write-ColorOutput "Cleanup completed!" $Green
}

# Main execution
if (-not (Test-DockerRunning)) {
    exit 1
}

if ($Build) {
    Build-Services
}
elseif ($Start) {
    if (-not (Test-ConfigExists)) {
        exit 1
    }
    Start-Services
}
elseif ($Stop) {
    Stop-Services
}
elseif ($Restart) {
    Stop-Services
    Start-Services
}
elseif ($Logs) {
    Show-Logs
}
elseif ($Status) {
    Show-Status
}
elseif ($Clean) {
    Clean-Environment
}
else {
    Write-ColorOutput "OzBargain Deal Filter - Docker Deployment" $Blue
    Write-ColorOutput "Usage: .\deploy.ps1 [OPTIONS]" $Yellow
    Write-ColorOutput ""
    Write-ColorOutput "Options:" $Yellow
    Write-ColorOutput "  -Build     Build Docker images" $Green
    Write-ColorOutput "  -Start     Start all services" $Green
    Write-ColorOutput "  -Stop      Stop all services" $Green
    Write-ColorOutput "  -Restart   Restart all services" $Green
    Write-ColorOutput "  -Logs      Show service logs (use -Service <name> for specific service)" $Green
    Write-ColorOutput "  -Status    Show service status" $Green
    Write-ColorOutput "  -Clean     Clean up Docker environment" $Green
    Write-ColorOutput ""
    Write-ColorOutput "Examples:" $Yellow
    Write-ColorOutput "  .\deploy.ps1 -Build" $Green
    Write-ColorOutput "  .\deploy.ps1 -Start" $Green
    Write-ColorOutput "  .\deploy.ps1 -Logs -Service ozb-deal-filter" $Green
    Write-ColorOutput "  .\deploy.ps1 -Status" $Green
}
