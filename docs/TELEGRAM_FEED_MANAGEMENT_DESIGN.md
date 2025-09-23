# Telegram Feed Management System - Design Document

## Overview

This document details the design for implementing Telegram-based RSS feed management functionality for the OzBargain Deal Filter system. The feature will allow authorized users to add, remove, and manage RSS feeds through Telegram bot commands while maintaining system security and reliability.

## Current System Architecture

### Existing Components
- **TelegramDispatcher** (`components/message_dispatcher.py:139`): One-way messaging to Telegram
- **RSSMonitor** (`components/rss_monitor.py:354`): Manages RSS feed polling with `add_feed()` and `remove_feed()` methods
- **ConfigurationManager** (`services/config_manager.py:20`): Handles static YAML configuration loading
- **ApplicationOrchestrator** (`orchestrator.py:53`): Main application coordinator

### Current Limitations
- Static configuration only (YAML file)
- No incoming message handling
- No command processing infrastructure
- No dynamic feed management persistence

## System Requirements

### Functional Requirements
1. **FR1**: Accept feed management commands via Telegram
2. **FR2**: Validate RSS feed URLs before adding
3. **FR3**: Persist feed configuration changes
4. **FR4**: Authorize users before processing commands
5. **FR5**: Provide feedback on command execution
6. **FR6**: Support feed listing and status queries
7. **FR7**: Maintain backward compatibility with existing configuration

### Non-Functional Requirements
1. **NFR1**: Response time < 5 seconds for all commands
2. **NFR2**: Support concurrent command processing
3. **NFR3**: Graceful error handling and user feedback
4. **NFR4**: Secure authorization mechanism
5. **NFR5**: Audit trail for feed modifications
6. **NFR6**: Rate limiting to prevent spam

## Architecture Design

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Bot Handler                     │
├─────────────────────────────────────────────────────────────┤
│ • Message polling/webhook processing                        │
│ • Command parsing and validation                           │
│ • User authorization                                       │
│ • Response formatting                                      │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                  Feed Command Processor                     │
├─────────────────────────────────────────────────────────────┤
│ • Command execution logic                                  │
│ • Feed URL validation                                      │
│ • Integration with RSS Monitor                            │
│ • Error handling and logging                              │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                 Dynamic Feed Manager                        │
├─────────────────────────────────────────────────────────────┤
│ • Persistent feed configuration                            │
│ • Configuration validation                                 │
│ • Backup and recovery                                      │
│ • Integration with existing ConfigManager                 │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                    RSS Monitor (Enhanced)                   │
├─────────────────────────────────────────────────────────────┤
│ • Dynamic feed addition/removal                            │
│ • Feed health monitoring                                   │
│ • Real-time configuration updates                          │
│ • Existing functionality preserved                         │
└─────────────────────────────────────────────────────────────┘
```

### New Components

#### 1. TelegramBotHandler

**Purpose**: Handle incoming Telegram messages and bot commands

**Location**: `ozb_deal_filter/components/telegram_bot_handler.py`

**Responsibilities**:
- Poll Telegram API for new messages
- Parse and validate incoming commands
- Authorize users against whitelist
- Route commands to appropriate processors
- Send responses back to users
- Rate limiting and abuse prevention

**Key Methods**:
```python
class TelegramBotHandler:
    async def start_polling(self) -> None
    async def handle_message(self, message: TelegramMessage) -> None
    async def send_response(self, chat_id: str, text: str) -> None
    def authorize_user(self, user_id: str) -> bool
    def parse_command(self, text: str) -> Optional[BotCommand]
```

#### 2. FeedCommandProcessor

**Purpose**: Process feed management commands and coordinate with system components

**Location**: `ozb_deal_filter/components/feed_command_processor.py`

**Responsibilities**:
- Execute feed management operations
- Validate RSS feed URLs
- Coordinate with RSS Monitor
- Generate user-friendly responses
- Log command execution for audit

**Key Methods**:
```python
class FeedCommandProcessor:
    async def add_feed(self, url: str, name: str = None, user_id: str = None) -> CommandResult
    async def remove_feed(self, identifier: str, user_id: str = None) -> CommandResult
    async def list_feeds(self, user_id: str = None) -> CommandResult
    async def get_feed_status(self, user_id: str = None) -> CommandResult
    def validate_feed_url(self, url: str) -> ValidationResult
```

#### 3. DynamicFeedManager

**Purpose**: Manage persistent feed configuration with dynamic updates

**Location**: `ozb_deal_filter/services/dynamic_feed_manager.py`

**Responsibilities**:
- Store feed configurations in persistent storage
- Validate feed configurations
- Backup and restore configurations
- Integration with existing ConfigurationManager
- Thread-safe configuration updates

**Key Methods**:
```python
class DynamicFeedManager:
    def add_feed_config(self, feed: FeedConfig) -> bool
    def remove_feed_config(self, identifier: str) -> bool
    def list_feed_configs(self) -> List[FeedConfig]
    def save_configuration(self) -> None
    def load_configuration(self) -> None
    def backup_configuration(self) -> str
```

### New Data Models

#### TelegramMessage
```python
@dataclass
class TelegramMessage:
    message_id: int
    from_user: TelegramUser
    chat: TelegramChat
    text: Optional[str]
    date: datetime

    def validate(self) -> bool
```

#### BotCommand
```python
@dataclass
class BotCommand:
    command: str  # add_feed, remove_feed, list_feeds, etc.
    args: List[str]
    user_id: str
    chat_id: str

    def validate(self) -> bool
```

#### FeedConfig
```python
@dataclass
class FeedConfig:
    url: str
    name: Optional[str]
    added_by: str
    added_at: datetime
    enabled: bool = True

    def validate(self) -> bool
```

#### CommandResult
```python
@dataclass
class CommandResult:
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
```

## Command Specification

### Supported Commands

#### `/add_feed <url> [name]`
- **Purpose**: Add a new RSS feed to monitoring
- **Parameters**:
  - `url` (required): Valid RSS feed URL
  - `name` (optional): Human-readable name for the feed
- **Validation**: URL format, RSS feed accessibility, duplicate check
- **Response**: Success confirmation with feed details or error message

#### `/remove_feed <url|name>`
- **Purpose**: Remove an RSS feed from monitoring
- **Parameters**:
  - `identifier` (required): Feed URL or name
- **Validation**: Feed exists, user permissions
- **Response**: Success confirmation or error message

#### `/list_feeds`
- **Purpose**: List all currently monitored feeds
- **Parameters**: None
- **Response**: Formatted list of feeds with status information

#### `/feed_status [url|name]`
- **Purpose**: Show detailed status of feeds
- **Parameters**:
  - `identifier` (optional): Specific feed URL or name
- **Response**: Health status, last poll time, error information

#### `/help`
- **Purpose**: Show available commands and usage
- **Parameters**: None
- **Response**: Formatted help text

### Command Flow

```
User sends message → TelegramBotHandler
                   ↓
            Parse command → Validate syntax
                   ↓
            Authorize user → Check permissions
                   ↓
            Route to FeedCommandProcessor
                   ↓
            Execute command → Update RSS Monitor
                   ↓
            Generate response → Send to user
```

## Security Design

### User Authorization

**Authorization Model**: Whitelist-based user verification

**Implementation**:
```python
class TelegramAuthorizer:
    def __init__(self, authorized_users: List[str]):
        self.authorized_users = set(authorized_users)

    def is_authorized(self, user_id: str) -> bool:
        return user_id in self.authorized_users

    def add_authorized_user(self, user_id: str) -> None:
        self.authorized_users.add(user_id)
```

**Configuration**:
```yaml
telegram_bot:
  bot_token: "${TELEGRAM_BOT_TOKEN}"
  authorized_users:
    - "123456789"  # User IDs from Telegram
    - "987654321"
  rate_limit:
    commands_per_minute: 10
    burst_limit: 3
```

### Rate Limiting

**Implementation**: Token bucket algorithm per user

**Limits**:
- 10 commands per minute per user
- Burst limit of 3 commands
- Global limit of 100 commands per minute

### Input Validation

**URL Validation**:
- Valid HTTP/HTTPS URLs only
- Reachable endpoint verification
- RSS/XML content type validation
- Malicious URL detection (basic)

**Command Validation**:
- Command syntax verification
- Parameter count validation
- Input sanitization
- Maximum length limits

## Data Storage Design

### Configuration Storage

**Primary Storage**: Enhanced YAML configuration with dynamic sections

```yaml
# Static configuration (existing)
user_criteria:
  prompt_template: "prompts/deal_evaluator.txt"
  max_price: 500.0

# Dynamic configuration (new)
dynamic_feeds:
  version: 1
  last_updated: "2024-01-01T00:00:00Z"
  feeds:
    - url: "https://example.com/feed.xml"
      name: "Example Feed"
      added_by: "123456789"
      added_at: "2024-01-01T00:00:00Z"
      enabled: true
```

**Backup Strategy**:
- Automatic backups before configuration changes
- Retention of last 10 configuration versions
- Backup location: `config/backups/`

### Audit Trail

**Location**: `logs/feed_management.log`

**Format**:
```json
{
  "timestamp": "2024-01-01T00:00:00Z",
  "user_id": "123456789",
  "command": "add_feed",
  "parameters": {"url": "https://example.com/feed.xml", "name": "Example"},
  "result": "success",
  "feed_count_before": 5,
  "feed_count_after": 6
}
```

## Integration Points

### RSS Monitor Integration

**Enhanced RSSMonitor Interface**:
```python
class EnhancedRSSMonitor(RSSMonitor):
    def add_feed_dynamic(self, feed_config: FeedConfig) -> bool:
        """Add feed with enhanced metadata"""

    def remove_feed_dynamic(self, identifier: str) -> bool:
        """Remove feed by URL or name"""

    def get_feed_status(self, identifier: str = None) -> Dict[str, Any]:
        """Get detailed feed status information"""

    def reload_feeds(self) -> None:
        """Reload feeds from updated configuration"""
```

### Configuration Manager Integration

**Extension Pattern**:
- Extend existing ConfigurationManager
- Add dynamic configuration loading
- Maintain backward compatibility
- Implement configuration merging

### Message Dispatcher Integration

**Reuse Existing TelegramDispatcher**:
- Use for sending responses
- Leverage existing error handling
- Maintain consistent message formatting

## Error Handling

### Error Categories

1. **User Errors** (4xx-style):
   - Invalid commands
   - Unauthorized access
   - Malformed URLs
   - Duplicate feeds

2. **System Errors** (5xx-style):
   - Network connectivity issues
   - Configuration file errors
   - RSS Monitor failures
   - Storage errors

### Error Response Format

```python
@dataclass
class ErrorResponse:
    error_code: str
    message: str
    suggestion: Optional[str] = None

    def to_telegram_message(self) -> str:
        """Format for Telegram display"""
```

### Error Handling Strategy

1. **Graceful Degradation**: Continue monitoring existing feeds if new operations fail
2. **User Feedback**: Provide clear, actionable error messages
3. **Logging**: Comprehensive error logging for debugging
4. **Recovery**: Automatic retry for transient errors

## Performance Considerations

### Telegram API Limits

- **Message Rate**: 30 messages per second
- **Bot API Limits**: 20 requests per minute for getUpdates
- **Message Length**: 4096 characters maximum

### Optimization Strategies

1. **Polling Optimization**: Intelligent polling interval adjustment
2. **Message Batching**: Combine multiple responses when possible
3. **Caching**: Cache feed status for quick responses
4. **Async Processing**: Non-blocking command execution

### Resource Usage

- **Memory**: Minimal increase (~10-20MB for bot handler)
- **CPU**: Negligible impact during normal operation
- **Storage**: ~1-5MB for configuration and logs
- **Network**: Additional Telegram API calls (estimated 1-10 requests/minute)

## Deployment Considerations

### Environment Variables

```bash
# Required
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Optional
TELEGRAM_AUTHORIZED_USERS=123456789,987654321
TELEGRAM_RATE_LIMIT_PER_MINUTE=10
TELEGRAM_WEBHOOK_URL=https://yourapp.com/webhook  # Alternative to polling
```

### Configuration Migration

**Migration Strategy**:
1. Detect existing static feed configuration
2. Convert to dynamic format automatically
3. Backup original configuration
4. Validate migration success

**Migration Script**:
```python
def migrate_static_to_dynamic_config(config_path: str) -> bool:
    """Migrate existing static RSS feeds to dynamic format"""
```

### Monitoring

**Health Checks**:
- Telegram Bot API connectivity
- Command processing latency
- Feed management operation success rate
- Error rate monitoring

**Metrics**:
- Commands processed per minute
- Average response time
- Active feed count
- User activity patterns

## Testing Strategy

### Unit Tests

**Components to Test**:
- TelegramBotHandler message parsing
- FeedCommandProcessor command execution
- DynamicFeedManager persistence operations
- URL validation logic
- Authorization mechanisms

### Integration Tests

**Test Scenarios**:
- End-to-end command processing
- RSS Monitor integration
- Configuration persistence
- Error handling workflows
- Rate limiting behavior

### Manual Testing

**Test Cases**:
- Add/remove feeds via Telegram
- Authorization verification
- Error message clarity
- Performance under load
- Recovery from failures

## Migration and Rollback Plan

### Migration Steps

1. **Phase 1**: Deploy new components without activation
2. **Phase 2**: Enable Telegram bot handler with limited users
3. **Phase 3**: Gradually expand to all authorized users
4. **Phase 4**: Full deployment with monitoring

### Rollback Strategy

1. **Configuration Rollback**: Restore previous configuration from backup
2. **Component Disabling**: Disable bot handler while preserving existing functionality
3. **Data Preservation**: Ensure no loss of existing feed configurations

### Validation Criteria

- All existing feeds continue to work
- No performance degradation
- Error rates remain within acceptable limits
- User feedback is positive

## Future Enhancements

### Short-term (Next Release)

1. **Feed Categories**: Group feeds by categories
2. **Scheduled Operations**: Add/remove feeds at scheduled times
3. **Feed Statistics**: Show feed performance metrics
4. **Bulk Operations**: Add/remove multiple feeds at once

### Medium-term (6 months)

1. **Web Interface**: Complement Telegram with web UI
2. **Feed Discovery**: Suggest feeds based on user preferences
3. **Advanced Filtering**: Per-feed filtering rules
4. **Notification Preferences**: Customize notifications per feed

### Long-term (1 year)

1. **Multi-platform Management**: Extend to Discord, Slack, etc.
2. **Machine Learning**: Intelligent feed recommendations
3. **Collaborative Features**: Share feeds between users
4. **Analytics Dashboard**: Comprehensive feed and deal analytics

## Conclusion

This design provides a robust, secure, and scalable foundation for Telegram-based RSS feed management. The modular architecture ensures easy maintenance and future enhancements while preserving the existing system's reliability and performance.

The implementation prioritizes user security through authorization mechanisms, provides clear error handling and feedback, and maintains backward compatibility with existing configurations. The phased deployment approach minimizes risk while enabling progressive feature rollout.
