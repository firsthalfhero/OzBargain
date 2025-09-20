# Duplicate Deal Prevention & Expired Deal Filtering - Fix Summary

## Issues Identified

Your Docker container was experiencing two main problems:

1. **Sending all deals on every RSS poll** - No mechanism to track which deals had already been processed
2. **Not filtering expired deals** - Despite having expiration detection logic, it wasn't being used properly

## Root Causes

### 1. No Persistent Duplicate Detection
- The `DealDetector` was using an in-memory `Set` to track seen deals
- When the Docker container restarted, this memory was lost
- Every RSS poll would treat all deals as "new" and send alerts for them

### 2. Simplified Filtering Logic
- The `orchestrator.py` was using a simplified filtering method instead of the proper `FilterEngine`
- The `FilterEngine` had comprehensive expiration detection patterns, but they weren't being used
- Expired deals were passing through the filters

### 3. No Time-Based Filtering
- RSS feeds can contain deals from many days/weeks ago
- Without time-based filtering, old deals could be processed as "new"

## Solutions Implemented

### 1. Persistent State Management
```python
# DealDetector now saves seen deals to disk
class DealDetector:
    def __init__(self, state_file: str = "logs/seen_deals.json", max_age_hours: int = 24):
        self.state_file = Path(state_file)
        self.seen_deal_ids: Set[str] = set()
        self._load_state()  # Load previously seen deals
    
    def _save_state(self):
        # Save seen deals to JSON file after each processing
```

**Benefits:**
- Survives container restarts
- Prevents duplicate alerts
- Configurable storage location

### 2. Time-Based Filtering
```python
# Only process deals newer than max_age_hours
cutoff_time = datetime.now() - timedelta(hours=self.max_age_hours)
if pub_date < cutoff_time:
    logger.debug(f"Skipping old deal: {entry.get('title', 'Unknown')} ({pub_date})")
    continue
```

**Benefits:**
- Prevents processing of very old deals
- Configurable age threshold (default: 24 hours)
- Reduces noise from historical deals

### 3. Proper FilterEngine Integration
```python
# orchestrator.py now uses the full FilterEngine
async def _apply_filters(self, deal: Deal, evaluation: EvaluationResult) -> FilterResult:
    if self._filter_engine:
        return self._filter_engine.apply_filters(deal, evaluation)
```

**Benefits:**
- Uses comprehensive expiration detection patterns
- Filters out deals with "EXPIRED", "ended", "closed", etc. in title/description
- Proper authenticity scoring
- Consistent filtering logic

### 4. Enhanced Configuration
```yaml
# config.yaml
system:
  polling_interval: 320  # seconds
  max_concurrent_feeds: 10
  max_deal_age_hours: 24  # Only process deals newer than 24 hours
```

## How It Works Now

### RSS Polling Cycle
1. **Fetch RSS Feed** - Every 320 seconds (5.3 minutes)
2. **Time Filter** - Skip deals older than 24 hours
3. **Duplicate Check** - Skip deals already seen (persistent across restarts)
4. **Parse Deal** - Extract price, discount, category info
5. **LLM Evaluation** - Check if deal matches user criteria
6. **Apply Filters** - Check price, discount, authenticity, and **expiration status**
7. **Send Alert** - Only for new, relevant, non-expired deals
8. **Save State** - Update persistent storage with newly seen deals

### Expiration Detection
The FilterEngine now properly detects expired deals using patterns like:
- `EXPIRED`, `ended`, `closed`, `inactive`
- `[expired]`, `(expired)`
- `deal has ended`, `offer expired`
- `promotion ended`, `sold out`

### State Persistence
- Seen deals stored in `logs/seen_deals.json`
- Survives Docker container restarts
- Automatic cleanup to prevent memory bloat
- Configurable storage location

## Testing Results

✅ **Time-based filtering** - Only processes recent deals  
✅ **Persistent state** - Remembers seen deals across restarts  
✅ **Expired deal filtering** - Properly filters out expired deals  
✅ **Real RSS feed testing** - Works with actual OzBargain feeds  

## Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_deal_age_hours` | 24 | Only process deals newer than this many hours |
| `polling_interval` | 320 | Seconds between RSS feed checks |
| `state_file` | `logs/seen_deals.json` | Where to store seen deal IDs |

## Expected Behavior

After deploying these fixes:

1. **First run** - May send alerts for recent deals (last 24 hours)
2. **Subsequent runs** - Only sends alerts for genuinely new deals
3. **Container restart** - Remembers previously seen deals, no duplicates
4. **Expired deals** - Automatically filtered out, no alerts sent

The system now behaves like a proper deal monitoring service that only notifies you about new, active deals that match your criteria.