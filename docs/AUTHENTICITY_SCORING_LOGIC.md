# Authenticity Scoring Logic

## Overview

The OzBargain Deal Filter system uses an authenticity scoring mechanism to assess the reliability and trustworthiness of deals based on community engagement data. The scoring system analyzes votes and comments from the OzBargain community to generate a score between 0.0 and 1.0, where:

- **1.0**: Highly authentic (strong positive community engagement)
- **0.5**: Neutral/unknown (insufficient data or mixed signals)
- **0.0**: Potentially questionable (negative community signals)

## Example: 50% Authenticity Score

Let's examine the specific example from the screenshot showing an ASUS monitor deal with **50.0%** authenticity:

**Deal Details:**
- Product: ASUS ROG Strix OLED XG27UCDMG 26.5" 240Hz 4K UHD QD-OLED Gaming Monitor
- Price: $1119 Delivered
- Category: Computing
- **Authenticity: 50.0%**

This 50% score indicates a **neutral assessment** - the system doesn't have sufficient positive or negative community signals to make a strong determination about the deal's authenticity.

## Core Components

### 1. AuthenticityAssessor Class

Located in `ozb_deal_filter/components/authenticity_assessor.py:16`, this class handles all authenticity calculations.

**Key Configuration:**
- `min_votes_threshold`: 5 votes (default)
- `min_comments_threshold`: 2 comments (default)

### 2. Main Assessment Method

The `assess_authenticity()` method (`ozb_deal_filter/components/authenticity_assessor.py:35`) follows this logic:

```python
def assess_authenticity(self, deal: Deal) -> float:
    # If no community data available, return neutral score
    if deal.votes is None and deal.comments is None:
        return 0.5  # This explains our 50% example

    # Calculate authenticity score based on available data
    score = self._calculate_authenticity_score(deal)
    return score
```

## Scoring Algorithm Breakdown

### Base Score Calculation (`ozb_deal_filter/components/authenticity_assessor.py:63`)

The system uses a weighted combination approach:

1. **Initialize base score**: 0.5 (neutral)
2. **Calculate vote score**: Based on vote count and sentiment
3. **Calculate comment score**: Based on comment engagement level
4. **Combine with weights**:
   - Vote weight: 70% (more trusted indicator)
   - Comment weight: 30%

### Vote-Based Scoring (`ozb_deal_filter/components/authenticity_assessor.py:105`)

The vote scoring logic works as follows:

#### Negative Votes (Suspicious)
```python
if votes < 0:
    # Each negative vote reduces score by 0.1 from base 0.5
    return max(0.0, 0.5 + (votes * 0.1))
    # Example: -3 votes = max(0.0, 0.5 + (-3 * 0.1)) = 0.2
```

#### Zero Votes (Neutral)
```python
if votes == 0:
    return 0.5  # Pure neutral score
```

#### Positive Votes Below Threshold (1-4 votes)
```python
if 0 < votes < min_votes_threshold:
    return 0.6 + (votes * 0.05)
    # Example: 3 votes = 0.6 + (3 * 0.05) = 0.75
```

#### Positive Votes Above Threshold (5+ votes)
```python
if votes >= min_votes_threshold:
    # Uses logarithmic scaling to prevent extreme scores
    import math
    normalized_votes = min(votes, 50)  # Cap at 50
    return min(1.0, 0.6 + (math.log(normalized_votes + 1) * 0.1))
    # Example: 10 votes = min(1.0, 0.6 + (log(11) * 0.1)) = ~0.84
```

### Comment-Based Scoring (`ozb_deal_filter/components/authenticity_assessor.py:140`)

Comments indicate community engagement and scrutiny:

#### No Comments (Slightly Suspicious)
```python
if comments == 0:
    return 0.48  # Slightly below neutral - might lack scrutiny
```

#### Comments Below Threshold (1 comment)
```python
if 0 < comments < min_comments_threshold:
    return 0.52 + (comments * 0.02)
    # Example: 1 comment = 0.52 + (1 * 0.02) = 0.54
```

#### Comments Above Threshold (2+ comments)
```python
if comments >= min_comments_threshold:
    import math
    normalized_comments = min(comments, 20)  # Cap at 20
    return min(1.0, 0.55 + (math.log(normalized_comments + 1) * 0.08))
    # Example: 5 comments = min(1.0, 0.55 + (log(6) * 0.08)) = ~0.69
```

## Why the Example Shows 50% Authenticity

Looking at the screenshot example, the 50.0% authenticity score most likely results from one of these scenarios:

### Scenario 1: No Community Data
```python
# If both votes and comments are None or missing
deal.votes = None
deal.comments = None
# Result: assess_authenticity() returns 0.5 (50%)
```

### Scenario 2: Zero Votes, Zero Comments
```python
# If the deal has zero engagement
deal.votes = 0
deal.comments = 0
# Vote score: 0.5, Comment score: 0.48
# Combined: (0.5 * 0.7) + (0.48 * 0.3) = 0.494 ≈ 50%
```

### Scenario 3: Mixed Signals Averaging to Neutral
```python
# Theoretical example with mixed data resulting in neutral score
# The weighted combination of vote and comment scores equals ~0.5
```

## Score Interpretation

The system provides human-readable descriptions (`ozb_deal_filter/components/authenticity_assessor.py:182`):

| Score Range | Description | Meaning |
|-------------|-------------|---------|
| 0.8 - 1.0   | "Highly trusted" | Strong positive community validation |
| 0.6 - 0.79  | "Well-regarded" | Good community reception |
| 0.4 - 0.59  | "Mixed signals" | **Our 50% example falls here** |
| 0.2 - 0.39  | "Questionable" | Community concerns evident |
| 0.0 - 0.19  | "Potentially problematic" | Strong negative signals |

## Questionable Deal Detection

The system flags deals as questionable using `is_questionable()` (`ozb_deal_filter/components/authenticity_assessor.py:167`):

```python
def is_questionable(self, authenticity_score: float, threshold: float = 0.4) -> bool:
    return authenticity_score < threshold
```

**For our 50% example**: Since 0.5 > 0.4 (default threshold), this deal would **NOT** be flagged as questionable, despite the neutral score.

## Key Design Principles

1. **Conservative Approach**: When in doubt, return neutral (0.5) rather than extreme scores
2. **Vote Priority**: Votes are weighted more heavily (70%) as they represent direct community sentiment
3. **Logarithmic Scaling**: Prevents extremely high engagement from skewing scores unreasonably
4. **Bounded Output**: All scores are clamped between 0.0 and 1.0
5. **Threshold-Based Logic**: Different scoring rules apply based on minimum engagement thresholds

## Real-World Application

The authenticity score is used throughout the system to:
- Filter out potentially problematic deals
- Prioritize well-regarded deals in notifications
- Provide transparency to users about deal reliability
- Support automated moderation decisions

The 50% score in our example represents the system's neutral stance when community data is insufficient to make a confident assessment of the deal's authenticity.
