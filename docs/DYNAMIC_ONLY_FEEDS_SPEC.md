# Dynamic-Only Feed Management Specification

## Overview

This specification outlines the changes required to remove the mandatory RSS feeds requirement from `config.yaml` and transition to a fully dynamic feed management system through Telegram bot commands. This allows users to start the system with zero configured feeds and manage all feeds dynamically through the Telegram interface.

## Current State

- `rss_feeds` field in `config.yaml` requires at least one feed
- Validation fails if `rss_feeds` is empty
- Dynamic feeds are stored separately and managed via Telegram
- System cannot start without at least one static RSS feed

## Target State

- `rss_feeds` field in `config.yaml` becomes optional and can be empty
- System can start with zero feeds configured
- All feed management happens through Telegram bot commands
- Dynamic feeds become the primary feed management mechanism
- Static feeds in config remain as an optional feature for advanced users

## Architecture Changes

### 1. Configuration Model Updates

**File**: `ozb_deal_filter/models/config.py`

- Remove validation requirement for non-empty `rss_feeds`
- Update `Configuration.validate()` method to allow empty RSS feeds list
- Ensure dynamic feeds can function independently

### 2. Feed Aggregation Logic

**Files**:
- `ozb_deal_filter/orchestrator.py`
- `ozb_deal_filter/services/dynamic_feed_manager.py`

- Update feed collection logic to handle empty static feeds
- Ensure orchestrator can operate with only dynamic feeds
- Handle the case where both static and dynamic feeds are empty (graceful degradation)

### 3. System Initialization

**Files**:
- `ozb_deal_filter/orchestrator.py`
- Main application entry point

- System should start successfully with empty feeds
- Log appropriate warnings when no feeds are configured
- Provide clear guidance on how to add feeds via Telegram

### 4. Documentation Updates

**Files**:
- `config/config.yaml` (example)
- README or user documentation

- Update example configuration to show empty RSS feeds
- Document the new dynamic-first approach
- Provide clear instructions for Telegram feed management

## Behavioral Changes

### Startup Behavior

1. **With Empty Feeds**: System starts successfully but logs a warning
2. **Feed Addition**: Users can immediately add feeds via Telegram commands
3. **Feed Removal**: Users can remove all feeds without system failure

### Runtime Behavior

1. **No Feeds State**: System continues running, polling interval maintained
2. **Feed Addition/Removal**: Hot reloading of feed configuration
3. **Error Handling**: Graceful handling when no feeds are available

### Telegram Integration

1. **Feed Commands**: All existing feed management commands continue working
2. **Status Commands**: Update to show when no feeds are configured
3. **Help Commands**: Guide users to add their first feed

## Migration Strategy

### Backward Compatibility

- Existing configurations with static RSS feeds continue working unchanged
- No breaking changes to existing setups
- Optional migration path for users who want to move to dynamic-only

### Default Configuration

- Ship with empty `rss_feeds: []` in example config
- Clear documentation on how to add first feed via Telegram
- Optional quick-start guide for common OzBargain feeds

## Risk Assessment

### Low Risk Changes

- Configuration validation updates (well-isolated)
- Documentation updates
- Example configuration changes

### Medium Risk Changes

- Orchestrator feed collection logic (requires testing)
- System initialization behavior (affects startup)

### Mitigation Strategies

- Comprehensive unit tests for empty feed scenarios
- Integration tests covering zero-feed startup
- Rollback plan maintaining current validation as fallback

## Success Criteria

1. **System Startup**: Application starts successfully with empty `rss_feeds: []`
2. **Feed Management**: All Telegram feed commands work with zero initial feeds
3. **Runtime Stability**: System handles transitions between zero and non-zero feeds
4. **User Experience**: Clear guidance provided for users starting with no feeds
5. **Backward Compatibility**: Existing configurations continue working unchanged

## Implementation Priority

1. **High Priority**: Configuration validation changes (core functionality)
2. **High Priority**: Orchestrator feed collection updates (system stability)
3. **Medium Priority**: Documentation and example updates (user experience)
4. **Low Priority**: Advanced error handling and logging improvements

## Testing Requirements

### Unit Tests

- Configuration validation with empty feeds
- Feed aggregation with various combinations
- Dynamic feed manager edge cases

### Integration Tests

- System startup with empty configuration
- End-to-end feed addition/removal via Telegram
- Feed persistence across system restarts

### User Acceptance Tests

- New user onboarding with zero feeds
- Migration from static to dynamic feeds
- Error scenarios and recovery

## Dependencies

- No external dependencies required
- Leverages existing Telegram bot infrastructure
- Uses current dynamic feed management system
