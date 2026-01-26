# Demo Queries

This document contains example queries to demonstrate the Agentic Policy Data Analytics Platform capabilities.

## Quick Start Queries

### 1. Tech Sector Employment Trends (Primary Demo)
```
What has been the trend in Singapore's tech sector employment from 2019 to 2023?
```
**Demonstrates:** Time-series trend analysis, multi-source data integration, chart generation

### 2. Digital Transformation Metrics
```
Analyze digital transformation metrics across Singapore industries
```
**Demonstrates:** Cross-sector analysis, breakdown by industry

### 3. Digital Adoption Comparison
```
What trends do you see in Singapore's digital adoption rates over the past 5 years? Compare across different demographics.
```
**Demonstrates:** Demographic comparison, multi-year trend analysis

---

## Category: Employment & Workforce Analytics

### Year-over-Year Analysis
```
Show YoY change in tech sector employment by industry from 2020 to 2024
```

### Workforce Composition
```
What is the breakdown of local vs foreign employees in Singapore's digital sector?
```

### Salary Trends
```
How have average salaries in the tech sector changed over the past 3 years?
```

### Role Distribution
```
Compare the ratio of professional vs technical roles in the digital industry
```

---

## Category: AI & Workforce Development

### Training Programme Effectiveness
```
What is the completion rate of AI workforce training programmes in Singapore?
```

### Employment Outcomes
```
Analyze employment rates 6 months after completing AI training programmes
```

### Programme Investment
```
How much funding has been allocated to AI workforce development programmes?
```

---

## Category: Online Safety & Digital Trust

### Incident Trends
```
What are the trends in online safety incidents reported in Singapore?
```

### Resolution Metrics
```
What is the average resolution time for verified online safety incidents?
```

### Severity Analysis
```
Break down online safety incidents by severity level over the past year
```

---

## Category: Emerging Technology Adoption

### Technology Readiness
```
What is Singapore's emerging technology adoption score across different tech domains?
```

### Adoption Factors
```
Compare workforce readiness vs regulatory clarity for emerging technologies
```

### Investment Analysis
```
Analyze investment levels in emerging technologies by sector
```

---

## Category: Comparative & Correlation Analysis

### Multi-Metric Comparison
```
Compare employment growth vs digital adoption rates in Singapore's tech sector
```

### Correlation Query
```
Is there a correlation between AI training programme completion and employment rates?
```

### Cross-Sector Comparison
```
Compare digital transformation progress across manufacturing, finance, and healthcare sectors
```

---

## Advanced Queries with Constraints

### Time-Bounded Query
```json
{
  "query": "Analyze employment trends in the technology sector",
  "constraints": {
    "time_range": {
      "start": "2020-01-01",
      "end": "2024-12-31"
    }
  }
}
```

### Source-Specific Query
```json
{
  "query": "Show digital sector employment statistics",
  "constraints": {
    "sources_allowlist": ["singstat", "data_gov_sg"]
  }
}
```

### Cost-Limited Query
```json
{
  "query": "Comprehensive analysis of Singapore's digital economy",
  "constraints": {
    "max_cost_sgd": 2.0
  }
}
```

---

## Available Data Sources

| Source | Description | Data Types |
|--------|-------------|------------|
| `data_gov_sg` | Singapore Government Open Data | Employment, demographics, sectoral indicators |
| `singstat` | Department of Statistics Singapore | Labour force, industry data, economic indicators |
| `mock_internal` | IMDA Internal Database | Digital sector metrics, programme data |

---

## Available Metrics

### Digital Sector Employment
- `total_employees` - Total headcount
- `local_employees` - Singapore citizens/PRs
- `foreign_employees` - Foreign workers
- `professional_roles` - Professional positions
- `technical_roles` - Technical positions
- `average_salary_sgd` - Average salary in SGD

### AI Workforce Programmes
- `target_participants` - Programme targets
- `actual_participants` - Actual enrolment
- `completion_rate` - Programme completion %
- `employment_rate_6months` - Post-programme employment
- `funding_sgd` - Programme funding

### Online Safety
- `total_reports` - Reports received
- `verified_incidents` - Confirmed incidents
- `resolution_rate` - Resolution success %
- `avg_resolution_days` - Average resolution time

### Emerging Tech Adoption
- `adoption_score` - Overall adoption index
- `workforce_readiness` - Skills readiness score
- `regulatory_clarity` - Policy clarity index
- `investment_level` - Investment indicator

---

## Query Tips

1. **Be specific about time ranges** - Include years for better results
2. **Mention metrics explicitly** - Name what you want to analyze
3. **Specify comparison dimensions** - By sector, demographics, time period
4. **Use natural language** - The system understands conversational queries

## Example Workflow

1. Enter your query in the chat interface
2. Review the proposed analysis plan
3. Approve or modify the plan
4. View results: tables, charts, and insights
5. Export report as Markdown or PDF
