#!/bin/bash

# OzBargain Deal Filter - Docker Deployment Script
# This script handles the complete deployment process

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

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_color "Docker is not installed!" $RED
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_color "Docker is not running!" $RED
        exit 1
    fi
}

check_config() {
    if [ ! -f "config/config.yaml" ]; then
        print_color "Configuration file not found. Creating from template..." $YELLOW
        if [ -f "config/config.example.yaml" ]; then
            cp config/config.example.yaml config/config.yaml
            print_color "Please edit config/config.yaml with your settings before starting." $YELLOW
            return 1
        else
            print_color "No configuration template found. Please create config/config.yaml" $RED
            return 1
        fi
    fi
    return 0
}

build_services() {
    print_color "Building Docker images..." $BLUE
    docker-compose build --no-cache
    print_color "Build completed successfully!" $GREEN
}

start_services() {
    print_color "Starting services..." $BLUE
    docker-compose up -d
    print_color "Services started successfully!" $GREEN
    print_color "Use 'docker-compose logs -f' to view logs" $YELLOW
}

stop_services() {
    print_color "Stopping services..." $BLUE
    docker-compose down
    print_color "Services stopped successfully!" $GREEN
}

show_logs() {
    if [ -n "$2" ]; then
        docker-compose logs -f "$2"
    else
        docker-compose logs -f
    fi
}

show_status() {
    print_color "Service Status:" $BLUE
    docker-compose ps
    print_color "\nContainer Health:" $BLUE
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

clean_environment() {
    print_color "Cleaning up Docker environment..." $YELLOW
    docker-compose down -v --remove-orphans
    docker system prune -f
    print_color "Cleanup completed!" $GREEN
}

show_help() {
    print_color "OzBargain Deal Filter - Docker Deployment" $BLUE
    print_color "Usage: ./deploy.sh [COMMAND] [OPTIONS]" $YELLOW
    echo
    print_color "Commands:" $YELLOW
    print_color "  build     Build Docker images" $GREEN
    print_color "  start     Start all services" $GREEN
    print_color "  stop      Stop all services" $GREEN
    print_color "  restart   Restart all services" $GREEN
    print_color "  logs      Show service logs (add service name for specific service)" $GREEN
    print_color "  status    Show service status" $GREEN
    print_color "  clean     Clean up Docker environment" $GREEN
    echo
    print_color "Examples:" $YELLOW
    print_color "  ./deploy.sh build" $GREEN
    print_color "  ./deploy.sh start" $GREEN
    print_color "  ./deploy.sh logs ozb-deal-filter" $GREEN
    print_color "  ./deploy.sh status" $GREEN
}

# Main execution
check_docker

case "$1" in
    build)
        build_services
        ;;
    start)
        if check_config; then
            start_services
        fi
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        start_services
        ;;
    logs)
        show_logs "$@"
        ;;
    status)
        show_status
        ;;
    clean)
        clean_environment
        ;;
    *)
        show_help
        ;;
esac