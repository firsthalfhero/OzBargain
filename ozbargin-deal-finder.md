# Project Brief: OzBargain Deal Filter & Alert System

## Introduction / Problem Statement

OzBargain receives hundreds of deals daily, making it impractical to manually monitor for specific products or categories of interest. Users miss time-sensitive deals or waste time scrolling through irrelevant offers. This project addresses the need for an intelligent filtering system that monitors targeted OzBargain RSS feeds, evaluates deals against personalised criteria, and delivers real-time alerts with essential deal information through existing messaging platforms.

## Vision & Goals

- **Vision:** Enable users to never miss relevant, high-quality deals from OzBargain whilst eliminating noise from irrelevant offers, delivered instantly when action is required.

- **Primary Goals:**
  - Goal 1: Successfully filter and deliver relevant deals based on user-defined criteria within 5 minutes of RSS feed update
  - Goal 2: Provide sufficient deal information in alerts to enable quick decision-making without mandatory click-through
  - Goal 3: Deliver urgent/time-sensitive deals within 2 minutes of RSS feed update

- **Success Metrics (Initial Ideas):**
  - System successfully sends alerts for deals matching user criteria
  - Alerts are delivered within target timeframes (measured from RSS feed update)
  - User finds the alerts useful enough to continue using the system

## Target Audience / Users

Primary users are savvy Australian bargain hunters who:
- Have specific products or categories they're actively monitoring
- Value time efficiency over comprehensive browsing
- Need real-time alerts for time-sensitive deals
- Are comfortable with technology and messaging platforms
- Want to avoid missing deals due to timing or information overload

## Key Features / Scope (High-Level Ideas for MVP)

- **RSS Feed Monitoring:** Monitor 5-10 targeted OzBargain RSS feeds (category-based and keyword search-based)
- **Feed Management:** Simple configuration system (e.g., configuration file) to add, remove, and modify RSS feeds without code changes
- **Intelligent Deal Filtering:** LLM-powered evaluation of deals against user-provided interest descriptions/criteria
- **Price Threshold Alerts:** Monitor for deals meeting specified price points or percentage discount thresholds
- **Deal Authenticity Assessment:** Basic evaluation using OzBargain community votes/comments to flag potentially questionable deals
- **Multi-Platform Delivery:** Send formatted alerts via free messaging platforms (WhatsApp, Telegram, etc.)
- **Rich Notifications:** Include deal title, price, discount %, urgency indicator, and basic authenticity assessment
- **Urgency Classification:** Mirror OzBargain's existing urgency indicators without custom logic

## Known Technical Constraints or Preferences

- **Constraints:**
  - Must use free messaging/notification platforms only
  - RSS feed limit of 5-10 concurrent feeds for MVP
  - No learning/AI training component for MVP - static user criteria only
  - Must respect OzBargain's RSS feed terms and rate limits
  - Local hosting on Windows 11 machine via Docker
  - LLM options: Local Docker-hosted model or paid API usage (small fee acceptable)

- **Risks:**
  - RSS feed availability and structure changes from OzBargain
  - Local LLM performance vs API reliability trade-offs
  - Messaging platform API limitations or policy changes
  - False positive/negative rates affecting user trust
  - Deal authenticity assessment accuracy

## Relevant Research (Optional)

{To be completed if market research phase is conducted}

## PM Prompt

**Context:** User wants a focused, practical solution for OzBargain deal monitoring with intelligent filtering and real-time alerts.

**Key Requirements:**
- Prioritise speed and accuracy over feature complexity
- Keep authenticity checking simple but effective
- Focus on delivery platform options that are free and reliable
- Ensure alert format provides actionable information
- Design for 5-10 concurrent RSS feeds maximum

**Areas Requiring Attention:**
- Technical architecture for RSS monitoring and LLM integration
- LLM deployment options: local Docker vs API services (cost/performance analysis)
- Message formatting and delivery platform selection
- Rate limiting and API cost management strategies
- User onboarding flow for defining interests and thresholds
- Error handling for feed outages or platform issues
- RSS feed polling frequency and update detection mechanisms
- Docker containerisation for Windows 11 deployment
- Configuration file format and validation (JSON, YAML, or similar)

**Development Guidance:**
- Favour proven, stable technologies over cutting-edge solutions
- Design for easy scaling from MVP to multi-user system
- Consider webhook-based delivery for real-time performance
- Plan for graceful degradation if external services fail
- Ensure Docker setup is straightforward for Windows 11 users