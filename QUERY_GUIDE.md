# Comprehensive Query Guide

## Quick Start

The **comprehensive all-in-one query** is located in:
- [comprehensive_query.kql](comprehensive_query.kql) - Standalone file
- [kql_queries.md](kql_queries.md) - Integrated with other queries

## What It Does

This query provides a complete view of your Azure Function executions by combining:

1. **Execution Flow**: See all spans that executed (function → OpenAI → weather tool → OpenAI)
2. **Token Usage**: Input/output/total tokens per request
3. **Cost Estimation**: Automatic cost calculation based on GPT-4 pricing
4. **Evaluation Scores**: All three evaluators (relevance, coherence, groundedness)
5. **Weather Data**: Location, temperature, and conditions retrieved
6. **Performance Metrics**: Duration breakdown by span
7. **Correlation**: Uses `response_id` to link all related spans

## Output Example

When you run the comprehensive query, you'll get results like:

| startTime | response_id | user_message | location | temperature | duration_ms | input_tokens | output_tokens | total_tokens | estimated_cost_usd | evaluations | avg_evaluation_score |
|-----------|-------------|--------------|----------|-------------|-------------|--------------|---------------|--------------|-------------------|-------------|---------------------|
| 2025-11-06... | resp_a3f2b9... | What is the weather in Dubai? | Dubai | 22 | 2150.5 | 285 | 95 | 380 | 0.0142 | {"relevance":0.9, "coherence":0.85, "groundedness":0.95} | 0.90 |

## Key Features

### 1. Hierarchical Structure
The query follows the same pattern as Azure AI Foundry's main query:
- Step 1: Identify all GenAI operations
- Step 2: Find root spans
- Step 3: Collect evaluations
- Step 4: Gather span details with tokens
- Step 5: Aggregate by operation
- Step 6: Join everything together
- Step 7: Calculate evaluation summaries
- Step 8: Format final output

### 2. Semantic Conventions
Uses standard GenAI semantic conventions:
- `gen_ai.system`: "azure_openai"
- `gen_ai.response.id`: Unique correlation ID
- `gen_ai.usage.input_tokens`: Prompt tokens
- `gen_ai.usage.output_tokens`: Completion tokens
- `gen_ai.evaluation.score`: Evaluator scores (0-1)
- `gen_ai.evaluator.name`: Evaluator identifier

### 3. Cost Calculation
Automatically estimates costs using GPT-4 pricing:
- Input tokens: $0.03 per 1K tokens
- Output tokens: $0.06 per 1K tokens
- Formula: `(input_tokens/1000 * 0.03) + (output_tokens/1000 * 0.06)`

## Usage

### In Azure Portal
1. Go to your Application Insights resource
2. Click "Logs" in the left menu
3. Copy the query from [comprehensive_query.kql](comprehensive_query.kql)
4. Paste and run

### Adjust Time Range
Change this line to adjust the lookback period:
```kql
| where timestamp > ago(24h)  // Change to ago(1h), ago(7d), etc.
```

### Filter by Specific Response
Add this after Step 1:
```kql
let target_response_id = "resp_a3f2b9c8d1e4";
let gen_ai_operations = dependencies
| where timestamp > ago(24h)
| where tostring(customDimensions["gen_ai.response.id"]) == target_response_id
| summarize count() by operation_Id;
```

### Export Results
Click "Export" button in Azure Portal to:
- Download as CSV
- Export to Excel
- Send to Power BI
- Create Azure Monitor Alert

## Other Queries

For specific analysis needs, see [kql_queries.md](kql_queries.md) which includes:
- Token usage analytics (hourly breakdown)
- Average evaluation scores by evaluator
- End-to-end latency analysis
- Weather tool performance
- Error tracking
- Cost estimation over time

## Troubleshooting

**No results returned?**
- Wait 2-5 minutes after making requests (ingestion delay)
- Check if `gen_ai.system` attribute is set in your spans
- Verify time range with `ago(1h)` instead of `ago(24h)`

**Missing evaluations?**
- Ensure `evaluate_response()` is called in your function
- Check evaluation spans have `gen_ai.response.id` attribute
- Verify evaluator names match: "relevance", "coherence", "groundedness"

**Token counts are empty?**
- Confirm OpenAI responses include `usage` object
- Check `gen_ai.usage.*` attributes are set in spans
- Some models may not return token counts for all requests

## Integration with AI Foundry

This query is compatible with Azure AI Foundry's semantic conventions. If you later decide to integrate with AI Foundry, the same attributes and structure will work seamlessly.

To migrate to AI Foundry:
1. Create an AI Foundry project
2. Link your Application Insights resource
3. Keep using the same attributes in your code
4. View traces in both AI Foundry UI and Application Insights

The comprehensive query will work in both environments!
