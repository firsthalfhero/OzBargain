# OzBargain Deal Filter - LLM Model Management Script
# This script manages Ollama models for local LLM evaluation

param(
    [string]$Action = "",
    [string]$Model = "",
    [switch]$List,
    [switch]$Pull,
    [switch]$Remove,
    [switch]$Test,
    [switch]$Status
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

# Recommended models for deal evaluation
$RecommendedModels = @{
    "llama2" = @{
        "name" = "llama2:7b"
        "description" = "Llama 2 7B - Good balance of performance and resource usage"
        "size" = "3.8GB"
        "recommended" = $true
    }
    "mistral" = @{
        "name" = "mistral:7b"
        "description" = "Mistral 7B - Fast and efficient for text analysis"
        "size" = "4.1GB"
        "recommended" = $true
    }
    "codellama" = @{
        "name" = "codellama:7b"
        "description" = "Code Llama 7B - Good for structured analysis"
        "size" = "3.8GB"
        "recommended" = $false
    }
    "llama2-13b" = @{
        "name" = "llama2:13b"
        "description" = "Llama 2 13B - Higher quality but more resource intensive"
        "size" = "7.3GB"
        "recommended" = $false
    }
}

function Test-OllamaRunning {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method GET -TimeoutSec 5
        return $true
    }
    catch {
        Write-ColorOutput "Ollama service is not running or not accessible on localhost:11434" $Red
        Write-ColorOutput "Make sure Docker containers are running: docker-compose up -d" $Yellow
        return $false
    }
}

function Get-InstalledModels {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method GET
        return $response.models
    }
    catch {
        Write-ColorOutput "Failed to get model list from Ollama" $Red
        return @()
    }
}

function Install-Model {
    param([string]$ModelName)

    Write-ColorOutput "Installing model: $ModelName" $Blue
    Write-ColorOutput "This may take several minutes depending on model size..." $Yellow

    try {
        # Use docker exec to pull the model
        $result = docker exec ollama ollama pull $ModelName
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "Successfully installed model: $ModelName" $Green
            return $true
        }
        else {
            Write-ColorOutput "Failed to install model: $ModelName" $Red
            return $false
        }
    }
    catch {
        Write-ColorOutput "Error installing model: $($_.Exception.Message)" $Red
        return $false
    }
}

function Remove-Model {
    param([string]$ModelName)

    Write-ColorOutput "Removing model: $ModelName" $Yellow

    try {
        $result = docker exec ollama ollama rm $ModelName
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "Successfully removed model: $ModelName" $Green
            return $true
        }
        else {
            Write-ColorOutput "Failed to remove model: $ModelName" $Red
            return $false
        }
    }
    catch {
        Write-ColorOutput "Error removing model: $($_.Exception.Message)" $Red
        return $false
    }
}

function Test-ModelEvaluation {
    param([string]$ModelName)

    Write-ColorOutput "Testing model evaluation: $ModelName" $Blue

    $testPrompt = @{
        model = $ModelName
        prompt = "Analyze this deal: 'iPhone 14 Pro 128GB - $899 (was $1399, save $500)'. Is this a good deal for electronics enthusiasts? Respond with YES or NO and brief reasoning."
        stream = $false
    } | ConvertTo-Json

    try {
        $response = Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method POST -Body $testPrompt -ContentType "application/json" -TimeoutSec 30

        Write-ColorOutput "Model Response:" $Green
        Write-ColorOutput $response.response $Reset
        Write-ColorOutput "Evaluation completed successfully!" $Green
        return $true
    }
    catch {
        Write-ColorOutput "Failed to test model evaluation: $($_.Exception.Message)" $Red
        return $false
    }
}

function Show-ModelStatus {
    Write-ColorOutput "Ollama Model Status" $Blue
    Write-ColorOutput "==================" $Blue

    if (-not (Test-OllamaRunning)) {
        return
    }

    $installedModels = Get-InstalledModels

    Write-ColorOutput "`nInstalled Models:" $Yellow
    if ($installedModels.Count -eq 0) {
        Write-ColorOutput "No models installed" $Red
    }
    else {
        foreach ($model in $installedModels) {
            $sizeGB = [math]::Round($model.size / 1GB, 2)
            Write-ColorOutput "  - $($model.name) (${sizeGB}GB)" $Green
        }
    }

    Write-ColorOutput "`nRecommended Models:" $Yellow
    foreach ($key in $RecommendedModels.Keys) {
        $model = $RecommendedModels[$key]
        $status = if ($installedModels.name -contains $model.name) { "INSTALLED" } else { "NOT INSTALLED" }
        $color = if ($installedModels.name -contains $model.name) { $Green } else { $Red }
        $recommended = if ($model.recommended) { " (RECOMMENDED)" } else { "" }

        Write-ColorOutput "  - $($model.name) - $($model.description)$recommended" $Reset
        Write-ColorOutput "    Size: $($model.size) | Status: " -NoNewline
        Write-ColorOutput $status $color
    }
}

function Show-Help {
    Write-ColorOutput "OzBargain Deal Filter - LLM Model Management" $Blue
    Write-ColorOutput "Usage: .\manage_models.ps1 [OPTIONS]" $Yellow
    Write-ColorOutput ""
    Write-ColorOutput "Options:" $Yellow
    Write-ColorOutput "  -List              List all installed models" $Green
    Write-ColorOutput "  -Pull -Model <name> Install a specific model" $Green
    Write-ColorOutput "  -Remove -Model <name> Remove a specific model" $Green
    Write-ColorOutput "  -Test -Model <name>  Test model evaluation" $Green
    Write-ColorOutput "  -Status            Show comprehensive model status" $Green
    Write-ColorOutput ""
    Write-ColorOutput "Examples:" $Yellow
    Write-ColorOutput "  .\manage_models.ps1 -Status" $Green
    Write-ColorOutput "  .\manage_models.ps1 -Pull -Model llama2:7b" $Green
    Write-ColorOutput "  .\manage_models.ps1 -Test -Model llama2:7b" $Green
    Write-ColorOutput "  .\manage_models.ps1 -List" $Green
    Write-ColorOutput ""
    Write-ColorOutput "Recommended Models for Deal Evaluation:" $Yellow
    Write-ColorOutput "  - llama2:7b (3.8GB) - Best balance of performance and resources" $Green
    Write-ColorOutput "  - mistral:7b (4.1GB) - Fast and efficient for text analysis" $Green
}

# Main execution
if (-not (Test-OllamaRunning)) {
    Write-ColorOutput "Please start the Docker containers first:" $Yellow
    Write-ColorOutput "  docker-compose up -d" $Green
    exit 1
}

if ($List) {
    $models = Get-InstalledModels
    Write-ColorOutput "Installed Models:" $Blue
    if ($models.Count -eq 0) {
        Write-ColorOutput "No models installed" $Red
    }
    else {
        foreach ($model in $models) {
            $sizeGB = [math]::Round($model.size / 1GB, 2)
            Write-ColorOutput "  - $($model.name) (${sizeGB}GB)" $Green
        }
    }
}
elseif ($Pull -and $Model) {
    Install-Model $Model
}
elseif ($Remove -and $Model) {
    Remove-Model $Model
}
elseif ($Test -and $Model) {
    Test-ModelEvaluation $Model
}
elseif ($Status) {
    Show-ModelStatus
}
else {
    Show-Help
}
