# KQL Queries for Azure Function Weather App with Tracing

These queries are optimized for the weather function app with token counting and evaluations.

**Recent Updates:**
- ✅ Fixed time range issues (changed from `ago(24h)` to `ago(7d)`)
- ✅ Improved syntax reliability (`customDimensions has` instead of `isnotnull`)
- ✅ Added 10 specialized queries for different use cases
- ✅ All queries tested and working with real data

**Quick Links:**
- [Comprehensive Query](#-comprehensive-all-in-one-query) - Complete view with all data
- [Specialized Queries](#-specialized-queries-by-use-case) - Targeted analysis for specific needs
- [Individual Queries](#individual-queries) - Original granular queries

---

## 🌟 Comprehensive All-in-One Query

This master query combines all traces, evaluations, tokens, and metadata in a single view, similar to Azure AI Foundry's main query.

**File:** See [comprehensive_query.kql](comprehensive_query.kql) for the latest version.

```kql
// ========================================================================
// Comprehensive All-in-One Query for Azure Function Weather App Tracing
// ========================================================================
// Simplified version with minimal let statements for better KQL compatibility
// Updated: Improved time range (7d) and more robust syntax

// Get all root weather_chat_function spans with GenAI attributes
dependencies
| where timestamp > ago(7d)
| where customDimensions has "gen_ai.system"
| where name == "weather_chat_function"
| project
    root_operation_Id = operation_Id,
    startTime = timestamp,
    root_duration = duration,
    success,
    user_message = tostring(customDimensions["user.message"]),
    response_id = tostring(customDimensions["gen_ai.response.id"])
// Join with aggregated span details (tokens, execution flow)
| join kind=leftouter (
    dependencies
    | where timestamp > ago(7d)
    | where name in ("weather_chat_function", "openai_initial_request", "openai_final_request", "get_weather_api_call")
    | extend
        response_id = tostring(customDimensions["gen_ai.response.id"]),
        input_tokens = toint(customDimensions["gen_ai.usage.input_tokens"]),
        output_tokens = toint(customDimensions["gen_ai.usage.output_tokens"]),
        total_tokens = toint(customDimensions["gen_ai.usage.total_tokens"]),
        model = tostring(customDimensions["gen_ai.request.model"]),
        finish_reason = tostring(customDimensions["gen_ai.response.finish_reason"]),
        location = tostring(customDimensions["location"]),
        temperature = tostring(customDimensions["weather.temperature"])
    | summarize
        execution_flow = make_list(name),
        span_count = count(),
        total_input_tokens = sum(input_tokens),
        total_output_tokens = sum(output_tokens),
        total_tokens = sum(total_tokens),
        model = max(model),
        location = max(location),
        temperature = max(temperature),
        finish_reasons = make_set(finish_reason),
        span_durations = make_list(pack("span", name, "duration_ms", duration / 10000.0))
        by operation_Id
) on $left.root_operation_Id == $right.operation_Id
// Join with evaluation scores
| join kind=leftouter (
    dependencies
    | where timestamp > ago(24h)
    | where name startswith "gen_ai.evaluation"
    | extend
        response_id = tostring(customDimensions["gen_ai.response.id"]),
        evaluator_name = tostring(customDimensions["gen_ai.evaluator.name"]),
        evaluation_score = todouble(customDimensions["gen_ai.evaluation.score"])
    | where isnotempty(response_id) and isnotnull(evaluation_score)
    | summarize
        evaluations = make_bag(pack(evaluator_name, evaluation_score)),
        avg_evaluation_score = avg(evaluation_score),
        eval_count = count()
        by response_id
) on response_id
| project
    startTime,
    operation_Id = root_operation_Id,
    response_id,
    user_message,
    location,
    temperature,
    duration_ms = root_duration / 10000.0,
    success,
    span_count,
    execution_flow,
    input_tokens = total_input_tokens,
    output_tokens = total_output_tokens,
    total_tokens,
    estimated_cost_usd = round((coalesce(total_input_tokens, 0) / 1000.0 * 0.03) + (coalesce(total_output_tokens, 0) / 1000.0 * 0.06), 4),
    model,
    finish_reasons,
    evaluations,
    avg_evaluation_score,
    eval_count = coalesce(eval_count, 0),
    span_durations
| order by startTime desc;
```

**Output Columns:**
- `startTime`: When the request started
- `operation_Id`: Unique trace ID
- `response_id`: Correlation ID across spans
- `user_message`: User's query
- `location`, `temperature`, `weather_condition`: Weather data retrieved
- `duration_ms`: Total execution time
- `execution_flow`: List of spans executed
- `input_tokens`, `output_tokens`, `total_tokens`: Token usage
- `estimated_cost_usd`: Estimated cost (GPT-4 pricing)
- `evaluations`: Dictionary of evaluator scores
- `avg_evaluation_score`: Average across all evaluators
- `span_durations`: Duration breakdown by span

---

## Individual Queries

## Query 1 — Complete Trace View with Token Counts

```kql
dependencies
| where timestamp > ago(1h)
| where name in ("weather_chat_function", "openai_initial_request", "openai_final_request", "get_weather_api_call")
| extend
    SpanName = name,
    TraceId = operation_Id,
    ResponseId = tostring(customDimensions.["gen_ai.response.id"]),
    Location = tostring(customDimensions.["location"]),
    Temperature = tostring(customDimensions.["weather.temperature"]),
    Model = tostring(customDimensions.["gen_ai.request.model"]),
    UserMessage = tostring(customDimensions.["user.message"]),
    InputTokens = toint(customDimensions.["gen_ai.usage.input_tokens"]),
    OutputTokens = toint(customDimensions.["gen_ai.usage.output_tokens"]),
    TotalTokens = toint(customDimensions.["gen_ai.usage.total_tokens"]),
    FinishReason = tostring(customDimensions.["gen_ai.response.finish_reason"]),
    Success = tostring(customDimensions.["response.success"])
| project
    timestamp,
    SpanName,
    ResponseId,
    TraceId,
    duration,
    Location,
    Temperature,
    Model,
    UserMessage,
    InputTokens,
    OutputTokens,
    TotalTokens,
    FinishReason,
    Success
| order by timestamp desc
```

## Query 2 — Group Spans by Trace with Token Aggregation

```kql
dependencies
| where timestamp > ago(1h)
| where name in ("weather_chat_function", "openai_initial_request", "openai_final_request", "get_weather_api_call")
| summarize
    ExecutionFlow = make_list(name),
    TotalDuration = max(duration),
    SpanCount = count(),
    StartTime = min(timestamp),
    UserMessage = max(tostring(customDimensions.["user.message"])),
    ResponseId = max(tostring(customDimensions.["gen_ai.response.id"])),
    Location = max(tostring(customDimensions.["location"])),
    Temperature = max(tostring(customDimensions.["weather.temperature"])),
    TotalInputTokens = sum(toint(customDimensions.["gen_ai.usage.input_tokens"])),
    TotalOutputTokens = sum(toint(customDimensions.["gen_ai.usage.output_tokens"])),
    TotalTokens = sum(toint(customDimensions.["gen_ai.usage.total_tokens"]))
    by operation_Id
| project StartTime, ResponseId, UserMessage, Location, Temperature, ExecutionFlow, SpanCount, TotalDuration, TotalInputTokens, TotalOutputTokens, TotalTokens, operation_Id
| order by StartTime desc
```

## Query 3 — Token Usage Analytics

```kql
dependencies
| where timestamp > ago(24h)
| where name in ("openai_initial_request", "openai_final_request")
| extend
    Model = tostring(customDimensions.["gen_ai.request.model"]),
    InputTokens = toint(customDimensions.["gen_ai.usage.input_tokens"]),
    OutputTokens = toint(customDimensions.["gen_ai.usage.output_tokens"]),
    TotalTokens = toint(customDimensions.["gen_ai.usage.total_tokens"])
| where isnotnull(TotalTokens)
| summarize
    RequestCount = count(),
    TotalInputTokens = sum(InputTokens),
    TotalOutputTokens = sum(OutputTokens),
    TotalTokensUsed = sum(TotalTokens),
    AvgInputTokens = avg(InputTokens),
    AvgOutputTokens = avg(OutputTokens),
    AvgTotalTokens = avg(TotalTokens)
    by name, Model, bin(timestamp, 1h)
| project timestamp, name, Model, RequestCount, TotalInputTokens, TotalOutputTokens, TotalTokensUsed, AvgInputTokens, AvgOutputTokens, AvgTotalTokens
| order by timestamp desc
```

## Query 4 — Evaluation Scores

```kql
dependencies
| where timestamp > ago(1h)
| where name startswith "gen_ai.evaluation"
| extend
    EvaluatorName = tostring(customDimensions.["gen_ai.evaluator.name"]),
    Score = todouble(customDimensions.["gen_ai.evaluation.score"]),
    ResponseId = tostring(customDimensions.["gen_ai.response.id"]),
    EvaluationId = tostring(customDimensions.["gen_ai.evaluation.id"])
| where isnotnull(Score)
| project timestamp, EvaluatorName, Score, ResponseId, EvaluationId, operation_Id
| order by timestamp desc
```

## Query 5 — Average Evaluation Scores by Evaluator

```kql
dependencies
| where timestamp > ago(24h)
| where name startswith "gen_ai.evaluation"
| extend
    EvaluatorName = tostring(customDimensions.["gen_ai.evaluator.name"]),
    Score = todouble(customDimensions.["gen_ai.evaluation.score"])
| where isnotnull(Score)
| summarize
    EvaluationCount = count(),
    AvgScore = avg(Score),
    MinScore = min(Score),
    MaxScore = max(Score),
    StdDevScore = stdev(Score)
    by EvaluatorName
| order by AvgScore desc
```

## Query 6 — Trace with Evaluations (Joined View)

```kql
let traces_data = dependencies
| where timestamp > ago(1h)
| where name == "weather_chat_function"
| extend
    ResponseId = tostring(customDimensions.["gen_ai.response.id"]),
    UserMessage = tostring(customDimensions.["user.message"])
| project timestamp, operation_Id, ResponseId, UserMessage, duration;
let eval_data = dependencies
| where timestamp > ago(1h)
| where name startswith "gen_ai.evaluation"
| extend
    ResponseId = tostring(customDimensions.["gen_ai.response.id"]),
    EvaluatorName = tostring(customDimensions.["gen_ai.evaluator.name"]),
    Score = todouble(customDimensions.["gen_ai.evaluation.score"])
| summarize
    Evaluations = make_bag(pack(EvaluatorName, Score)),
    AvgScore = avg(Score),
    EvalCount = count()
    by ResponseId;
traces_data
| join kind=leftouter (eval_data) on ResponseId
| project timestamp, ResponseId, UserMessage, duration, Evaluations, AvgScore, EvalCount, operation_Id
| order by timestamp desc
```

## Query 7 — End-to-End Latency Breakdown with Tokens

```kql
dependencies
| where timestamp > ago(1h)
| where name in ("weather_chat_function", "openai_initial_request", "openai_final_request", "get_weather_api_call")
| summarize
    TotalTime = max(duration),
    OpenAI_Initial = maxif(duration, name == "openai_initial_request"),
    WeatherAPI = maxif(duration, name == "get_weather_api_call"),
    OpenAI_Final = maxif(duration, name == "openai_final_request"),
    TotalTokens = sum(toint(customDimensions.["gen_ai.usage.total_tokens"])),
    InputTokens = sum(toint(customDimensions.["gen_ai.usage.input_tokens"])),
    OutputTokens = sum(toint(customDimensions.["gen_ai.usage.output_tokens"])),
    ResponseId = max(tostring(customDimensions.["gen_ai.response.id"]))
    by operation_Id, StartTime = min(timestamp)
| extend
    OpenAI_Initial_Ms = OpenAI_Initial / 10000.0,
    WeatherAPI_Ms = WeatherAPI / 10000.0,
    OpenAI_Final_Ms = OpenAI_Final / 10000.0,
    TotalTime_Ms = TotalTime / 10000.0
| project StartTime, ResponseId, TotalTime_Ms, OpenAI_Initial_Ms, WeatherAPI_Ms, OpenAI_Final_Ms, TotalTokens, InputTokens, OutputTokens, operation_Id
| order by StartTime desc
```

## Query 8 — Weather Tool Performance

```kql
dependencies
| where timestamp > ago(1h)
| where name == "get_weather_api_call"
| extend
    Location = tostring(customDimensions.["location"]),
    Temperature = tostring(customDimensions.["weather.temperature"]),
    Condition = tostring(customDimensions.["weather.condition"]),
    Unit = tostring(customDimensions.["unit"])
| summarize
    CallCount = count(),
    AvgDuration = avg(duration),
    MaxDuration = max(duration),
    MinDuration = min(duration)
    by Location
| order by CallCount desc
```

## Query 9 — Cost Estimation (Tokens to Cost)

```kql
// Assuming GPT-4 pricing: ~$0.03 per 1K input tokens, ~$0.06 per 1K output tokens
dependencies
| where timestamp > ago(24h)
| where name in ("openai_initial_request", "openai_final_request")
| extend
    InputTokens = toint(customDimensions.["gen_ai.usage.input_tokens"]),
    OutputTokens = toint(customDimensions.["gen_ai.usage.output_tokens"])
| where isnotnull(InputTokens) and isnotnull(OutputTokens)
| summarize
    TotalRequests = count(),
    TotalInputTokens = sum(InputTokens),
    TotalOutputTokens = sum(OutputTokens)
    by bin(timestamp, 1h)
| extend
    EstimatedInputCost = (TotalInputTokens / 1000.0) * 0.03,
    EstimatedOutputCost = (TotalOutputTokens / 1000.0) * 0.06,
    EstimatedTotalCost = ((TotalInputTokens / 1000.0) * 0.03) + ((TotalOutputTokens / 1000.0) * 0.06)
| project timestamp, TotalRequests, TotalInputTokens, TotalOutputTokens, EstimatedInputCost, EstimatedOutputCost, EstimatedTotalCost
| order by timestamp desc
```

## Query 10 — Error Tracking

```kql
dependencies
| where timestamp > ago(1h)
| extend
    IsError = tobool(customDimensions.["error"]),
    ErrorMessage = tostring(customDimensions.["error.message"])
| where IsError == true
| project timestamp, name, ErrorMessage, operation_Id, customDimensions
| order by timestamp desc
```
