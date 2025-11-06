# Azure Function App with Weather Tool & Application Insights Tracing

A simple Azure Function app that demonstrates:
- Azure OpenAI integration with tool/function calling
- Mock weather API tool
- Application Insights distributed tracing (without Azure AI Foundry)
- OpenTelemetry instrumentation

## Features

- **HTTP Trigger**: POST/GET endpoint at `/api/weather`
- **Weather Tool**: Mock weather data retrieval with custom spans
- **Azure OpenAI**: Uses tool calling to fetch weather information
- **Token Counting**: Tracks input/output tokens for cost analysis
- **AI Evaluations**: Automatic evaluation metrics (relevance, coherence, groundedness)
- **Response Correlation**: Unique response_id for tracking across spans
- **Full Tracing**: Distributed tracing with Application Insights using OpenTelemetry

## Setup

### 1. Prerequisites

- Python 3.9+
- Azure Functions Core Tools
- Azure OpenAI resource
- Application Insights resource

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Edit `local.settings.json` and set:

- `APPLICATIONINSIGHTS_CONNECTION_STRING`: Your Application Insights connection string
- `AZURE_OPENAI_ENDPOINT`: Your Azure OpenAI endpoint
- `AZURE_OPENAI_API_KEY`: Your Azure OpenAI API key
- `AZURE_OPENAI_DEPLOYMENT_NAME`: Your deployment name (e.g., "gpt-4")

### 4. Run Locally

```bash
func start
```

## Usage

### Example Request (POST)

```bash
curl -X POST http://localhost:7071/api/weather \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the weather like in Dubai?"}'
```

### Example Request (GET)

```bash
curl "http://localhost:7071/api/weather?message=What%20is%20the%20weather%20in%20London?"
```

### Example Response

```json
{
  "response": "The current weather in Dubai is sunny with a temperature of 22°C. The humidity is at 65% and there's a light wind at 10 km/h.",
  "user_message": "What is the weather like in Dubai?",
  "response_id": "resp_a3f2b9c8d1e4"
}
```

## Tracing & Telemetry

The app automatically sends rich telemetry to Application Insights:

### Captured Data
- **Function execution spans** with duration and success status
- **OpenAI API calls** with model, finish reason, and latency
- **Token usage** (input/output tokens per request)
- **Weather tool invocations** with location and weather data
- **AI Evaluation metrics** (relevance, coherence, groundedness scores)
- **Custom attributes**: user messages, response IDs, temperatures, etc.
- **Response correlation** via unique response_id across all spans

### View Traces in Azure Portal

1. Go to your Application Insights resource
2. Navigate to "Logs" (KQL query editor)
3. Use the queries from [kql_queries.md](kql_queries.md) for comprehensive analysis

### Sample KQL Queries

**View all executions with token counts:**
```kql
dependencies
| where timestamp > ago(1h)
| where name in ("weather_chat_function", "openai_initial_request", "openai_final_request")
| extend
    ResponseId = tostring(customDimensions.["gen_ai.response.id"]),
    InputTokens = toint(customDimensions.["gen_ai.usage.input_tokens"]),
    OutputTokens = toint(customDimensions.["gen_ai.usage.output_tokens"]),
    TotalTokens = toint(customDimensions.["gen_ai.usage.total_tokens"])
| project timestamp, name, ResponseId, InputTokens, OutputTokens, TotalTokens
| order by timestamp desc
```

**View evaluation scores:**
```kql
dependencies
| where timestamp > ago(1h)
| where name startswith "gen_ai.evaluation"
| extend
    EvaluatorName = tostring(customDimensions.["gen_ai.evaluator.name"]),
    Score = todouble(customDimensions.["gen_ai.evaluation.score"]),
    ResponseId = tostring(customDimensions.["gen_ai.response.id"])
| project timestamp, EvaluatorName, Score, ResponseId
| order by timestamp desc
```

See [kql_queries.md](kql_queries.md) for 10+ advanced queries including cost estimation, performance analytics, and evaluation tracking.

## Deployment

Deploy to Azure:

```bash
func azure functionapp publish <your-function-app-name>
```

Make sure to set the environment variables in Azure Portal under Configuration > Application Settings.

## Architecture

```
User Request
    ↓
Azure Function (weather_chat)
    ↓
Azure OpenAI (with tool definition)
    ↓
get_weather() mock tool
    ↓
Azure OpenAI (natural language response)
    ↓
Response to User
```

All steps are traced with OpenTelemetry and sent to Application Insights.

## References

- See [tracing_integration_guide.md](tracing_integration_guide.md) for detailed tracing setup
- [Azure Functions Python Developer Guide](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [Azure OpenAI Function Calling](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/function-calling)
