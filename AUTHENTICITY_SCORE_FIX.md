# Authenticity Score Fix

## Problem
The authenticity score was always showing as 70% (0.7) regardless of the actual deal's community engagement (votes and comments).

## Root Cause
The system was failing to initialize properly due to missing environment variables, causing it to fall back to basic filtering logic in the orchestrator that used a hardcoded authenticity score of 0.7.

### Specific Issues:
1. **Environment Variable Expansion**: The config manager was trying to expand ALL environment variables in the configuration file, including `${OPENAI_API_KEY}` even when using local LLM
2. **Failed Initialization**: When environment variables were missing, the entire system initialization failed
3. **Fallback Logic**: The orchestrator had fallback filtering logic with hardcoded authenticity scoring instead of using the proper `FilterEngine`
4. **Unused AuthenticityAssessor**: The sophisticated `AuthenticityAssessor` component was never being used

## Solution

### 1. Environment Variable Handling
**File**: `ozb_deal_filter/services/config_manager.py`
- Modified `_expand_env_vars()` to handle missing environment variables gracefully
- Instead of throwing an error, missing variables are replaced with placeholder values
- The validation logic then determines if the missing variable is actually needed

### 2. Conditional API Key Validation
**File**: `ozb_deal_filter/models/config.py`
- Added validation in `LLMProviderConfig.validate()` to only require API keys when using API-based providers
- When using local LLM, missing API keys are ignored
- Clear error messages guide users to set the correct environment variables when needed

### 3. Proper FilterEngine Usage
The system now properly initializes the `FilterEngine` which uses the `AuthenticityAssessor` to calculate dynamic authenticity scores based on:
- **Vote count**: Positive votes increase authenticity, negative votes decrease it
- **Comment count**: More comments indicate community scrutiny and engagement
- **Logarithmic scaling**: Prevents extremely high scores while rewarding engagement
- **Weighted combination**: Votes weighted 70%, comments 30%

## Results

### Before Fix:
- Authenticity score: Always 0.7 (70%)
- Used basic calculation: `min(1.0, (votes + comments) / 20.0)` with 0.7 default

### After Fix:
- Authenticity score: Dynamic calculation based on community engagement
- Example: Deal with 10 votes + 5 comments = ~0.796 (79.6%)
- Uses sophisticated `AuthenticityAssessor` with proper weighting and scaling

## Testing
- All existing tests pass
- Manual testing confirms dynamic authenticity scoring
- System properly initializes with local LLM configuration
- No breaking changes to existing functionality

## Impact
- More accurate authenticity assessment for deals
- Better filtering based on community engagement
- Proper use of the designed architecture
- System robustness improved with better error handling
