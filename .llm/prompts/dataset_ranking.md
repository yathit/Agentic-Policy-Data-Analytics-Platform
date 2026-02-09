# Dataset Ranking Prompt

Rank these dataset candidates by relevance to the user query.

## User Query
"{question}"

## Entities of Interest
{entities}

## Metrics of Interest
{metrics}

## Candidates
{candidates}

## Instructions

For each candidate, provide:
- **id**: The dataset ID (must match exactly from the list above)
- **relevance_score**: 0.0 to 1.0 (higher = more relevant to the query)
- **reason**: Brief explanation of why this is or isn't relevant (1 sentence)
- **confidence**: "high", "medium", or "low"

## Response Format

Respond with JSON:
```json
{"rankings": [{"id": "...", "relevance_score": 0.85, "reason": "...", "confidence": "high"}]}
```
