# KQL Queries for Monitoring

This folder contains ready-to-use KQL queries for monitoring your Azure Function in Application Insights.

## 📁 Files

### `comprehensive_query.kql`
**Use this for:** Complete analysis of your traces

Returns everything in one view:
- User messages and responses
- Full execution flow (which spans ran)
- Token usage (input/output/total)
- Costs (estimated in USD)
- Performance metrics (duration by span)
- Evaluation scores (relevance, coherence, groundedness)
- Location and weather data

**When to use:**
- Investigating specific requests
- Understanding the full trace flow
- Analyzing token usage patterns
- Getting all data at once

---

### `specialized_queries.kql`
**Use this for:** Specific monitoring tasks

Contains 10 focused queries:

#### 1. Error Analysis
Find failed requests and error messages quickly.

**Use when:** Something is broken or users report issues.

#### 2. Cost Analysis
Track token usage and spending over time (hourly breakdown).

**Use when:** Monitoring your budget or optimizing costs.

#### 3. Performance Monitoring
Get P50, P95, P99 latencies by hour with success rates.

**Use when:** Checking if the app is fast enough or investigating slowness.

#### 4. Detailed Span Breakdown
See average duration for each span type (weather_chat_function, openai_initial_request, etc.).

**Use when:** Finding which part of your code is slow.

#### 5. Tool Calls Analysis
Track how often OpenAI decides to call the weather function vs. responding directly.

**Use when:** Understanding AI behavior and function calling patterns.

#### 6. Location Usage Analysis
See which locations users ask about most.

**Use when:** Understanding usage patterns or planning features.

#### 7. Real-Time Monitoring
View the last hour of activity.

**Use when:** Actively testing or debugging right now.

#### 8. Evaluation Scores Analysis
Aggregate quality metrics (relevance, coherence, groundedness) by evaluator.

**Use when:** Checking AI response quality or running A/B tests.

#### 9. Daily Summary Statistics
High-level daily stats: request count, success rate, avg latency, total cost.

**Use when:** Creating reports or reviewing trends.

#### 10. Slow Requests
Find all requests slower than 3 seconds.

**Use when:** Investigating performance issues or SLA violations.

---

## 🚀 How to Use

### Step 1: Open Application Insights
1. Go to Azure Portal
2. Navigate to your Application Insights resource
3. Click "Logs" in the left sidebar

### Step 2: Copy & Run
1. Open one of the `.kql` files in this folder
2. Copy the query you want
3. Paste it into the Application Insights query editor
4. Click "Run"

### Step 3: Adjust Time Range
All queries default to last 7 days. Change this by editing:
```kql
| where timestamp > ago(7d)  // Change to 1h, 24h, 30d, etc.
```

---

## 💡 Tips

**Quick health check:**
```kql
dependencies
| where timestamp > ago(1h)
| where name == "weather_chat_function"
| summarize count(), success_rate = 100.0 * countif(success) / count();
```

**Find a specific request:**
```kql
dependencies
| where timestamp > ago(7d)
| where customDimensions has "What is the weather in Dubai"
| project timestamp, operation_Id, name, customDimensions
| order by timestamp desc;
```

**See all span types in your data:**
```kql
dependencies
| where timestamp > ago(7d)
| summarize count() by name
| order by count_ desc;
```

---

## 📊 Understanding Results

### Common Fields
- `timestamp` - When the span occurred
- `operation_Id` - Trace ID (groups all spans in one request)
- `name` - Span name (e.g., "weather_chat_function", "openai_initial_request")
- `duration` - Time in ticks (divide by 10000 for milliseconds)
- `success` - true/false
- `customDimensions` - Your custom attributes

### Duration Conversion
```kql
| extend duration_ms = duration / 10000.0  // Convert to milliseconds
| extend duration_sec = duration / 10000000.0  // Convert to seconds
```

### Cost Calculation
Based on GPT-4 pricing (adjust for your model):
```kql
| extend cost_usd =
    round((input_tokens / 1000.0 * 0.03) + (output_tokens / 1000.0 * 0.06), 4)
```

---

## 🆘 Troubleshooting

**No results?**
1. Check your time range: `| where timestamp > ago(7d)`
2. Verify you have data: `dependencies | take 10`
3. Check span names match your code

**Query too slow?**
1. Reduce time range: Use `ago(1h)` instead of `ago(30d)`
2. Add filters early in the query
3. Use `| take 100` to limit results while testing

**Need help?**
See the main [README.md](../README.md) for quick query examples and setup instructions.
