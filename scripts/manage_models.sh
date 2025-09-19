#!/bin/bash

# OzBargain Deal Filter - LLM Model Management Script
# This script manages Ollama models for local LLM evaluation

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_color() {
    printf "${2}${1}${NC}\n"
}

# Recommended models for deal evaluation
declare -A RECOMMENDED_MODELS
RECOMMENDED_MODELS[llama2]="llama2:7b|Llama 2 7B - Good balance of performance and resource usage|3.8GB|true"
RECOMMENDED_MODELS[mistral]="mistral:7b|Mistral 7B - Fast and efficient for text analysis|4.1GB|true"
RECOMMENDED_MODELS[codellama]="codellama:7b|Code Llama 7B - Good for structured analysis|3.8GB|false"
RECOMMENDED_MODELS[llama2-13b]="llama2:13b|Llama 2 13B - Higher quality but more resource intensive|7.3GB|false"

check_ollama_running() {
    if ! curl -s -f http://localhost:11434/api/tags > /dev/null 2>&1; then
        print_color "Ollama service is not running or not accessible on localhost:11434" $RED
        print_color "Make sure Docker containers are running: docker-compose up -d" $YELLOW
        return 1
    fi
    return 0
}

get_installed_models() {
    curl -s http://localhost:11434/api/tags | jq -r '.models[]?.name // empty' 2>/dev/null || echo ""
}

install_model() {
    local model_name="$1"
    
    print_color "Installing model: $model_name" $BLUE
    print_color "This may take several minutes depending on model size..." $YELLOW
    
    if docker exec ollama ollama pull "$model_name"; then
        print_color "Successfully installed model: $model_name" $GREEN
        return 0
    else
        print_color "Failed to install model: $model_name" $RED
        return 1
    fi
}

remove_model() {
    local model_name="$1"
    
    print_color "Removing model: $model_name" $YELLOW
    
    if docker exec ollama ollama rm "$model_name"; then
        print_color "Successfully removed model: $model_name" $GREEN
        return 0
    else
        print_color "Failed to remove model: $model_name" $RED
        return 1
    fi
}

test_model_evaluation() {
    local model_name="$1"
    
    print_color "Testing model evaluation: $model_name" $BLUE
    
    local test_prompt='{
        "model": "'$model_name'",
        "prompt": "Analyze this deal: '\''iPhone 14 Pro 128GB - $899 (was $1399, save $500)'\''. Is this a good deal for electronics enthusiasts? Respond with YES or NO and brief reasoning.",
        "stream": false
    }'
    
    local response
    if response=$(curl -s -X POST http://localhost:11434/api/generate \
        -H "Content-Type: application/json" \
        -d "$test_prompt" \
        --max-time 30); then
        
        print_color "Model Response:" $GREEN
        echo "$response" | jq -r '.response // "No response received"'
        print_color "Evaluation completed successfully!" $GREEN
        return 0
    else
        print_color "Failed to test model evaluation" $RED
        return 1
    fi
}

show_model_status() {
    print_color "Ollama Model Status" $BLUE
    print_color "==================" $BLUE
    
    if ! check_ollama_running; then
        return 1
    fi
    
    local installed_models
    installed_models=$(get_installed_models)
    
    print_color "\nInstalled Models:" $YELLOW
    if [ -z "$installed_models" ]; then
        print_color "No models installed" $RED
    else
        while IFS= read -r model; do
            [ -n "$model" ] && print_color "  - $model" $GREEN
        done <<< "$installed_models"
    fi
    
    print_color "\nRecommended Models:" $YELLOW
    for key in "${!RECOMMENDED_MODELS[@]}"; do
        IFS='|' read -r name description size recommended <<< "${RECOMMENDED_MODELS[$key]}"
        
        local status="NOT INSTALLED"
        local color=$RED
        if echo "$installed_models" | grep -q "^$name$"; then
            status="INSTALLED"
            color=$GREEN
        fi
        
        local rec_text=""
        if [ "$recommended" = "true" ]; then
            rec_text=" (RECOMMENDED)"
        fi
        
        print_color "  - $name - $description$rec_text" $NC
        printf "    Size: $size | Status: "
        print_color "$status" $color
    done
}

list_models() {
    local models
    models=$(get_installed_models)
    
    print_color "Installed Models:" $BLUE
    if [ -z "$models" ]; then
        print_color "No models installed" $RED
    else
        while IFS= read -r model; do
            [ -n "$model" ] && print_color "  - $model" $GREEN
        done <<< "$models"
    fi
}

show_help() {
    print_color "OzBargain Deal Filter - LLM Model Management" $BLUE
    print_color "Usage: ./manage_models.sh [COMMAND] [OPTIONS]" $YELLOW
    echo
    print_color "Commands:" $YELLOW
    print_color "  list                    List all installed models" $GREEN
    print_color "  pull <model_name>       Install a specific model" $GREEN
    print_color "  remove <model_name>     Remove a specific model" $GREEN
    print_color "  test <model_name>       Test model evaluation" $GREEN
    print_color "  status                  Show comprehensive model status" $GREEN
    echo
    print_color "Examples:" $YELLOW
    print_color "  ./manage_models.sh status" $GREEN
    print_color "  ./manage_models.sh pull llama2:7b" $GREEN
    print_color "  ./manage_models.sh test llama2:7b" $GREEN
    print_color "  ./manage_models.sh list" $GREEN
    echo
    print_color "Recommended Models for Deal Evaluation:" $YELLOW
    print_color "  - llama2:7b (3.8GB) - Best balance of performance and resources" $GREEN
    print_color "  - mistral:7b (4.1GB) - Fast and efficient for text analysis" $GREEN
}

# Check dependencies
if ! command -v curl &> /dev/null; then
    print_color "curl is required but not installed" $RED
    exit 1
fi

if ! command -v jq &> /dev/null; then
    print_color "jq is required but not installed" $RED
    print_color "Install with: sudo apt-get install jq" $YELLOW
    exit 1
fi

# Main execution
if ! check_ollama_running; then
    print_color "Please start the Docker containers first:" $YELLOW
    print_color "  docker-compose up -d" $GREEN
    exit 1
fi

case "$1" in
    list)
        list_models
        ;;
    pull)
        if [ -z "$2" ]; then
            print_color "Please specify a model name" $RED
            print_color "Example: ./manage_models.sh pull llama2:7b" $YELLOW
            exit 1
        fi
        install_model "$2"
        ;;
    remove)
        if [ -z "$2" ]; then
            print_color "Please specify a model name" $RED
            print_color "Example: ./manage_models.sh remove llama2:7b" $YELLOW
            exit 1
        fi
        remove_model "$2"
        ;;
    test)
        if [ -z "$2" ]; then
            print_color "Please specify a model name" $RED
            print_color "Example: ./manage_models.sh test llama2:7b" $YELLOW
            exit 1
        fi
        test_model_evaluation "$2"
        ;;
    status)
        show_model_status
        ;;
    *)
        show_help
        ;;
esac