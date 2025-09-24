# Product Overview

OzBargain Deal Filter & Alert System is an intelligent monitoring solution that tracks OzBargain RSS feeds, filters deals based on user-defined criteria using LLM evaluation, and delivers real-time alerts through messaging platforms.

## Core Functionality

- **RSS Monitoring**: Continuously polls OzBargain RSS feeds for new deals
- **Deal Parsing**: Extracts structured data from RSS entries including price, discount, category
- **LLM Evaluation**: Uses AI to assess deal relevance against user criteria
- **Smart Filtering**: Applies price, discount percentage, and authenticity filters
- **Alert Delivery**: Sends formatted notifications via Telegram, Discord, Slack, or WhatsApp
- **Git Integration**: Automated commit generation for configuration changes

## Key Features

- Protocol-based architecture for dependency injection and testing
- Support for both local (Docker) and API-based LLM providers
- Configurable urgency levels for different alert types
- Comprehensive data validation throughout the pipeline
- Structured logging and monitoring capabilities
- YAML-based configuration with environment variable support

## Target Users

Bargain hunters and deal enthusiasts who want automated, intelligent filtering of OzBargain deals based on their specific interests and criteria.
