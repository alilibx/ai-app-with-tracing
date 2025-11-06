# Azure Function App with Weather Tool & Tracing

A simple Azure Function that demonstrates OpenAI function calling with full Application Insights tracing.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Settings
Edit `local.settings.json`:
```json
{
  "Values": {
    "APPLICATIONINSIGHTS_CONNECTION_STRING": "your-app-insights-connection-string",
    "AZURE_OPENAI_ENDPOINT": "your-openai-endpoint",
    "AZURE_OPENAI_API_KEY": "your-api-key",
    "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4"
  }
}
```

### 3. Run Locally
```bash
func start
```

### 4. Test It
```bash
curl -X POST http://localhost:7071/api/weather \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the weather in Dubai?"}'
```

## 📊 Monitoring & Analytics

All requests are automatically traced to Application Insights with:
- ✅ Token usage (input/output counts)
- ✅ Request duration and latency
- ✅ OpenAI model and finish reasons
- ✅ Weather data retrieved
- ✅ Evaluation scores (relevance, coherence, groundedness)
- ✅ Full execution flow

### View Your Data

1. Go to Azure Portal → Your Application Insights resource
2. Click "Logs" to open the KQL query editor
3. Copy queries from the [`queries/`](queries/) folder

### Ready-to-Use Queries

**📁 [`queries/comprehensive_query.kql`](queries/comprehensive_query.kql)**
- Complete view with all trace data, tokens, costs, and evaluations
- Best for: Deep analysis of specific requests

**📁 [`queries/specialized_queries.kql`](queries/specialized_queries.kql)**
- 10 focused queries for common tasks:
  1. **Error Analysis** - Find and debug failures
  2. **Cost Analysis** - Track spending over time
  3. **Performance Monitoring** - P50/P95/P99 latencies
  4. **Span Breakdown** - Identify bottlenecks
  5. **Tool Calls Analysis** - Function calling patterns
  6. **Location Analytics** - Most requested locations
  7. **Real-Time Monitoring** - Last hour activity
  8. **Evaluation Scores** - AI quality metrics
  9. **Daily Summary** - High-level statistics
  10. **Slow Requests** - Latency threshold detection

### Quick Queries

**View recent activity:**
```kql
dependencies
| where timestamp > ago(1h)
| where name == "weather_chat_function"
| extend
    user_message = tostring(customDimensions["user.message"]),
    duration_ms = duration / 10000.0
| project timestamp, user_message, duration_ms, success
| order by timestamp desc;
```

**Check for errors:**
```kql
dependencies
| where timestamp > ago(7d)
| where name == "weather_chat_function"
| where success == false
| project timestamp, operation_Id, customDimensions
| order by timestamp desc;
```

**Calculate costs:**
```kql
dependencies
| where timestamp > ago(7d)
| where name in ("openai_initial_request", "openai_final_request")
| extend
    input_tokens = toint(customDimensions["gen_ai.usage.input_tokens"]),
    output_tokens = toint(customDimensions["gen_ai.usage.output_tokens"])
| summarize
    total_input = sum(input_tokens),
    total_output = sum(output_tokens)
| extend cost_usd = round((total_input / 1000.0 * 0.03) + (total_output / 1000.0 * 0.06), 4);
```

## 📂 Project Structure

```
ai-app-with-tracing/
├── function_app.py              # Azure Function with weather endpoint
├── requirements.txt             # Python dependencies
├── local.settings.json         # Local configuration
├── queries/                    # KQL queries for monitoring
│   ├── comprehensive_query.kql # All-in-one complete trace view
│   └── specialized_queries.kql # 10 focused queries for specific needs
└── README.md                   # This file
```

## 🔍 How It Works

```
1. User asks: "What's the weather in Dubai?"
   ↓
2. Azure OpenAI (first call) → decides to use get_weather tool
   ↓
3. get_weather() function → returns mock weather data
   ↓
4. Azure OpenAI (second call) → generates natural language response
   ↓
5. User receives: "The weather in Dubai is sunny with 22°C..."
```

Every step is traced with:
- Execution time
- Token counts
- Success/failure status
- Custom attributes (location, temperature, etc.)

## 📖 Additional Resources

- **[tracing_integration_guide.md](tracing_integration_guide.md)** - Detailed tracing implementation guide
- **[queries/](queries/)** - All KQL queries for monitoring
- [Azure Functions Python Guide](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [Azure OpenAI Function Calling](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/function-calling)

## 🚢 Deployment

```bash
func azure functionapp publish <your-function-app-name>
```

Remember to set environment variables in Azure Portal under **Configuration → Application Settings**.

---

**Need help?** Check the [queries/](queries/) folder for pre-built monitoring queries.
