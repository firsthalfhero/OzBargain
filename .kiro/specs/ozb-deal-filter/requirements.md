# Requirements Document

## Introduction

The OzBargain Deal Filter & Alert System is an intelligent monitoring solution that tracks OzBargain RSS feeds, filters deals based on user-defined criteria using LLM evaluation, and delivers real-time alerts through messaging platforms. The system addresses the challenge of monitoring hundreds of daily deals by providing personalized, actionable notifications for time-sensitive bargains while eliminating irrelevant noise.

## Requirements

### Requirement 1

**User Story:** As a bargain hunter, I want to monitor specific OzBargain RSS feeds so that I can track deals in categories or keywords of interest without manual browsing.

#### Acceptance Criteria

1. WHEN the system starts THEN it SHALL load and monitor up to 10 configured RSS feeds simultaneously
2. WHEN an RSS feed is updated THEN the system SHALL detect new deals within 2 minutes
3. IF an RSS feed becomes unavailable THEN the system SHALL log the error and continue monitoring other feeds
4. WHEN RSS feed structure changes THEN the system SHALL handle parsing errors gracefully without crashing

### Requirement 2

**User Story:** As a user, I want to configure RSS feeds and filtering criteria through a simple configuration system so that I can customize monitoring without code changes.

#### Acceptance Criteria

1. WHEN the system initializes THEN it SHALL read configuration from a structured file (JSON/YAML)
2. WHEN configuration includes RSS feed URLs THEN the system SHALL validate and load each feed
3. WHEN configuration includes prompt template reference THEN the system SHALL load the specified agent prompt for LLM evaluation
4. WHEN configuration includes price thresholds THEN the system SHALL apply these filters to deals
5. IF configuration file is invalid THEN the system SHALL provide clear error messages and fail gracefully
6. WHEN configuration is updated THEN the system SHALL reload settings without requiring restart

### Requirement 3

**User Story:** As a bargain hunter, I want deals evaluated against my personal criteria using AI so that I only receive alerts for genuinely relevant offers.

#### Acceptance Criteria

1. WHEN a new deal is detected THEN the system SHALL evaluate it against user-defined interest criteria using LLM
2. WHEN LLM evaluation occurs THEN it SHALL use the configured prompt template with deal title, description, price, and category as inputs
3. WHEN deal meets user criteria THEN the system SHALL proceed with additional filtering checks
4. IF LLM service is unavailable THEN the system SHALL fall back to keyword-based filtering
5. WHEN LLM evaluation fails THEN the system SHALL log the error and skip that deal
6. WHEN evaluating deals THEN the system SHALL complete processing within 30 seconds per deal

### Requirement 4

**User Story:** As a price-conscious shopper, I want deals filtered by price thresholds and discount percentages so that I only see offers meeting my budget criteria.

#### Acceptance Criteria

1. WHEN a deal passes LLM evaluation THEN the system SHALL check against configured price thresholds
2. WHEN deal has discount percentage THEN the system SHALL compare against minimum discount criteria
3. WHEN deal meets price criteria THEN the system SHALL proceed to authenticity assessment
4. IF price information is missing THEN the system SHALL use LLM evaluation result only
5. WHEN multiple price thresholds exist THEN the system SHALL apply the most restrictive matching criteria

### Requirement 5

**User Story:** As a cautious shopper, I want basic authenticity assessment of deals so that I can avoid potentially questionable offers.

#### Acceptance Criteria

1. WHEN a deal passes price filtering THEN the system SHALL assess authenticity using OzBargain community data
2. WHEN deal has votes/comments THEN the system SHALL calculate a basic authenticity score
3. WHEN authenticity score is below threshold THEN the system SHALL flag the deal as questionable
4. WHEN deal lacks community data THEN the system SHALL proceed without authenticity assessment
5. WHEN authenticity assessment completes THEN the system SHALL include the result in alert data

### Requirement 6

**User Story:** As a mobile user, I want to receive formatted alerts via free messaging platforms so that I can act on deals immediately without checking multiple sources.

#### Acceptance Criteria

1. WHEN a deal passes all filters THEN the system SHALL format and send an alert within 5 minutes of RSS detection
2. WHEN formatting alerts THEN the system SHALL include deal title, price, discount percentage, urgency indicator, and authenticity assessment
3. WHEN deal is time-sensitive THEN the system SHALL deliver alert within 2 minutes of RSS detection
4. WHEN sending alerts THEN the system SHALL use configured messaging platform (WhatsApp, Telegram, etc.)
5. IF messaging platform is unavailable THEN the system SHALL retry delivery and log failures
6. WHEN alert is sent THEN the system SHALL include sufficient information for decision-making without mandatory click-through

### Requirement 7

**User Story:** As a system administrator, I want the system to run reliably in Docker on Windows 11 so that I can deploy and maintain it easily.

#### Acceptance Criteria

1. WHEN deploying THEN the system SHALL run in Docker containers on Windows 11
2. WHEN system starts THEN it SHALL initialize all components and begin monitoring within 60 seconds
3. WHEN errors occur THEN the system SHALL log detailed information for troubleshooting
4. WHEN system runs THEN it SHALL handle graceful shutdown and restart scenarios
5. IF external services fail THEN the system SHALL continue operating with degraded functionality
6. WHEN system operates THEN it SHALL maintain stable performance for continuous monitoring

### Requirement 8

**User Story:** As a user, I want LLM integration options so that I can choose between local Docker hosting or API services based on my preferences for cost and performance.

#### Acceptance Criteria

1. WHEN configuring LLM THEN the system SHALL support both local Docker-hosted models and external API services
2. WHEN using local LLM THEN the system SHALL manage Docker container lifecycle automatically
3. WHEN using API services THEN the system SHALL manage authentication and rate limiting
4. IF LLM service fails THEN the system SHALL implement fallback mechanisms to maintain functionality
5. WHEN switching LLM providers THEN the system SHALL require only configuration changes
6. WHEN using paid APIs THEN the system SHALL track and limit usage to prevent unexpected costs

### Requirement 9

**User Story:** As a developer, I want the codebase to follow Python PEP 8 standards so that the code is maintainable, readable, and follows industry best practices.

#### Acceptance Criteria

1. WHEN writing Python code THEN it SHALL conform to PEP 8 style guidelines
2. WHEN code is committed THEN it SHALL pass automated linting checks
3. WHEN functions are defined THEN they SHALL include proper docstrings following PEP 257
4. WHEN modules are created THEN they SHALL include appropriate type hints following PEP 484
5. WHEN code is reviewed THEN it SHALL maintain consistent formatting and naming conventions
6. WHEN dependencies are managed THEN they SHALL follow PEP 518 standards for project configuration

### Requirement 10

**User Story:** As a developer, I want automatic git commits after task completion so that progress is tracked with meaningful commit messages.

#### Acceptance Criteria

1. WHEN a development task is completed THEN the system SHALL automatically commit changes to git
2. WHEN committing changes THEN it SHALL generate meaningful commit messages describing the work completed
3. WHEN multiple files are changed THEN the commit SHALL include all related changes in a single commit
4. WHEN commits are made THEN they SHALL reference the specific task or requirement being implemented
5. IF git operations fail THEN the system SHALL log errors and continue without blocking development
6. WHEN commits are created THEN they SHALL follow conventional commit message format

### Requirement 11

**User Story:** As a user, I want technical discovery of messaging platforms so that I can choose the most suitable option for receiving alerts on my mobile device.

#### Acceptance Criteria

1. WHEN design phase begins THEN the system SHALL research available free messaging platform APIs
2. WHEN evaluating platforms THEN it SHALL test API endpoints and authentication methods
3. WHEN platforms are assessed THEN it SHALL document setup complexity, reliability, and feature availability
4. WHEN discovery is complete THEN it SHALL present platform options with pros/cons to the user for approval
5. WHEN user selects platform THEN the system SHALL validate the choice through test message delivery
6. IF selected platform fails testing THEN the system SHALL provide alternative recommendations
