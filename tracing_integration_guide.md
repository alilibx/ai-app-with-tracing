# Comprehensive Tracing Integration Guide (Azure AI Foundry + Application Insights + OpenTelemetry)

This guide explains how to enable and analyze distributed tracing using **Azure AI Foundry** or directly via **Azure Application Insights**, including **KQL (Kusto Query Language)** examples for custom telemetry analysis. It also aligns with the provided TelemetryManager and Evaluations utilities.

---

## 🔹 1. Overview
Tracing provides deep visibility into your GenAI workloads — including latency, token usage, evaluator scores, and multi-agent interactions — by correlating spans emitted by OpenTelemetry with Azure Monitor or Application Insights.

There are **two main setups**:
1. **Using Azure AI Foundry Tracing (simplified setup)** – automatic correlation with model calls, evaluations, and agents.
2. **Direct Application Insights Integration (manual setup)** – without linking to AI Foundry.

---

## 🔸 2. Setup A — Azure AI Foundry + Application Insights (Recommended)

### **Step 1 — Connect App Insights to Project**
1. Go to **Azure AI Foundry → Your Project → Tracing**.
2. Associate an **Application Insights** resource.
3. Copy the **Project Endpoint URI**.

### **Step 2 — Use the TelemetryManager class**
The `TelemetryManager` automatically retrieves your Application Insights connection string from the project and initializes tracing.

```python
telemetry_manager.initialize(
    project_endpoint="https://<your-resource>.services.ai.azure.com/api/projects/<project>",
    enable_console_export=True
)
```

### **Step 3 — Use decorators and spans**
```python
@trace_function(attributes={"operation": "generate_summary"}, capture_args=True)
def generate_summary(doc: str):
    # Your model call here
    return summarize_text(doc)
```

You can also wrap code blocks:
```python
with telemetry_manager.create_span("agent_decision", {"agent": "retrieval"}):
    result = run_retrieval()
```

### **Step 4 — Log Evaluations**
```python
from evaluations import log_relevance_score, log_coherence_score

log_relevance_score(0.88, response_id="resp_123", comments="Highly relevant")
log_coherence_score(0.75, response_id="resp_123", comments="Some repetition")
```

### **Step 5 — View in Azure AI Foundry**
Navigate to **Project → Tracing**. You’ll see spans with metadata such as:
- Function name
- Token usage
- Evaluation metrics
- Custom span attributes

Click **View in Application Insights** for advanced analytics.

---

## 🔸 3. Setup B — Direct Application Insights (Without AI Foundry)

### **Option 1 — Using Environment Variable**
```bash
export APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=<your-key>;IngestionEndpoint=https://<region>.in.applicationinsights.azure.com/"
```

Then initialize telemetry directly:
```python
telemetry_manager.initialize(connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"))
```

### **Option 2 — Without TelemetryManager**
You can configure OpenTelemetry manually:
```python
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

configure_azure_monitor(connection_string="InstrumentationKey=<key>")

tracer_provider = TracerProvider()
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("local_span_test"):
    print("This trace goes to Application Insights.")
```

---

## 🔹 4. KQL Queries for Application Insights
Once spans are flowing to Application Insights, use these queries for debugging and evaluation tracking.

### Main Query for LLM Traces
```kql
// Helper function to determine Gen AI role based on event name
let get_role = (event_name: string) { 
    iff(event_name == "gen_ai.choice", "assistant", split(event_name, ".")[1])
};
let get_event_name = (customDimensions: dynamic, message: string) {  iff(customDimensions["event.name"] == "", message, customDimensions["event.name"]) };
let get_response_id = (customDimensions: dynamic) { 
    iff(
        customDimensions["gen_ai.response.id"] == "", 
        iff(customDimensions["gen_ai.thread.run.id"] == "", "", strcat(tostring(customDimensions["gen_ai.thread.id"]), "/", tostring(customDimensions["gen_ai.thread.run.id"]))),
        tostring(customDimensions["gen_ai.response.id"]))
}; 
let is_completion_message = (customDimensions: dynamic, event_name: string) { event_name == "gen_ai.choice" or (event_name == "gen_ai.assistant.message" and customDimensions["gen_ai.thread.run.id"] != "") };
let get_evaluator_name = (customDimensions: dynamic, event_name: string) { iff(customDimensions["gen_ai.evaluator.name"] == "", split(event_name, ".")[2], tostring(customDimensions["gen_ai.evaluator.name"])) };
// Retrieve all GenAI operations
let gen_ai_operations = requests | union dependencies
| where timestamp between (datetime(2025-10-30T05:34:42.826Z) .. datetime(2025-11-06T05:34:42.826Z))
| where isnotnull(customDimensions["gen_ai.system"]) or isnotnull(customDimensions["gen_ai.provider.name"])
| summarize count() by operation_Id;
// Retrieve Gen AI content within the specified date range
let gen_ai_prompts_and_completions = traces
    | where timestamp between (datetime(2025-10-30T05:34:42.826Z) .. datetime(2025-11-06T05:34:42.826Z))
    | extend event_name = get_event_name(customDimensions, message)
    | where (event_name startswith "gen_ai") and (event_name !startswith "gen_ai.evaluation")
    | extend event_content = iff(message startswith ("gen_ai"), tostring(customDimensions["gen_ai.event.content"]), message)
    | extend json = parse_json(event_content)
    | extend role = get_role(event_name)
    | extend content = bag_merge(bag_pack("timestamp", timestamp, "role", role), iff(json["message"] != "", json.message, json))
    | extend is_completion = is_completion_message(customDimensions, event_name)    
    | project 
        operation_Id,
        id = operation_ParentId, 
        response_id = get_response_id(customDimensions),       
        prompt = iff(is_completion, dynamic(null), content),
        completion = iff(is_completion, content, dynamic(null)),
        content,
        role,
        timestamp;
// Retrieve root span for each operation
let root_spans = gen_ai_operations | join kind=inner (union requests, dependencies) on operation_Id
  | where operation_ParentId == "" or operation_Id == operation_ParentId
  | project root_name = name, root_start_time = timestamp, root_span_type = type, root_duration = duration, root_success = success, root_span_id = id, operation_Id;
// Retrieve GenAI evaluation events
let eval_data = traces
  | where timestamp between (datetime(2025-10-30T05:34:42.826Z) .. datetime(2025-11-06T05:34:42.826Z))
  | extend event_name = get_event_name(customDimensions, message)
  | where event_name startswith "gen_ai.evaluation"
  | extend  response_id = get_response_id(customDimensions)
  | where isnotempty(response_id)
  | extend evaluator_name = get_evaluator_name(customDimensions, event_name), evaluation_score = todouble(customDimensions["gen_ai.evaluation.score"]), evaluation_id = iff(customDimensions["gen_ai.evaluation.id"] != "", customDimensions["gen_ai.evaluation.id"], tostring(timestamp))
  | summarize 
     evals = make_list(bag_pack("evaluatorName", evaluator_name, "evaluationScore", evaluation_score, "evaluationId", evaluation_id, "comments", message, "responseId", response_id)) by response_id;
// Perform final join and summarization to merge GenAI spans, non-GenAI spans, and additional attributes for displaying the root span of the trace
let operations = gen_ai_operations 
| join kind=inner (union requests, dependencies) on operation_Id
| extend response_id = get_response_id(customDimensions)
| join kind=leftouter eval_data on response_id
| join kind=leftouter (gen_ai_prompts_and_completions) on id, operation_Id
| extend spanType = "GenAI"
| join kind=inner (root_spans) on operation_Id
| summarize  
  name = any(root_name),
  startTime = tostring(any(root_start_time)),
  spanType = any(root_span_type),
  raw_prompts = make_list(prompt), 
  raw_completions = make_list(completion),
  raw_evals = make_set(evals),
  id = any(root_span_id),
  duration = any(root_duration),
  success = any(root_success),
  inputToken = sum(toint(customDimensions["gen_ai.usage.input_tokens"])),
  outputToken = sum(toint(customDimensions["gen_ai.usage.output_tokens"])),
  childCount = dcount(id) - 1  // each span has a unique id, -1 to exclude the root
  by 
  operation_Id;
operations  
| join kind=leftouter (gen_ai_prompts_and_completions | where role == "user" | summarize input=arg_min(todatetime(timestamp), prompt)[1]["content"] by operation_Id) on operation_Id
| join kind=leftouter (gen_ai_prompts_and_completions | where role == "system" | summarize system=arg_min(todatetime(timestamp), prompt)[1]["content"] by operation_Id) on operation_Id
| join kind=leftouter (gen_ai_prompts_and_completions | where role == "assistant" | summarize output=arg_max(todatetime(timestamp), completion)[1]["content"] by operation_Id) on operation_Id
| join kind=leftouter (operations | mv-expand raw_evals 
        | summarize evaluationScore = avg(todouble(raw_evals.evaluationScore)), evaluationCount = count() by evaluatorName = tostring(raw_evals.evaluatorName), operation_Id
        | summarize events = make_list(pack("eventName", evaluatorName, "evaluationScore", evaluationScore, "count", evaluationCount)) by operation_Id
) on operation_Id
| project name, system, input = coalesce(input["text"]["value"], tostring(input)), output = coalesce(output["text"]["value"], tostring(output)), events, startTime, duration, inputToken, outputToken, success, operationId = operation_Id, raw_prompts, raw_completions, raw_evals, childCount, operationParentId = operation_Id, id
| order by tolower(name) asc
```

### Additional Queries

### **Query 2 — All traces grouped by span name**
```kql
traces
| summarize Count = count(), AvgDuration = avg(duration) by name
| order by Count desc
```

### **Query 3 — Function performance overview**
```kql
traces
| where message contains "function.duration_ms"
| extend Duration = toreal(todynamic(customDimensions).['function.duration_ms'])
| summarize AvgDurationMs = avg(Duration), Calls = count() by name
| order by AvgDurationMs desc
```

### **Query 4 — AI Evaluation Scores**
```kql
traces
| where name startswith "gen_ai.evaluation"
| extend Evaluator = tostring(customDimensions.['gen_ai.evaluator.name']),
         Score = toreal(customDimensions.['gen_ai.evaluation.score'])
| summarize AvgScore = avg(Score), Count = count() by Evaluator
| order by AvgScore desc
```

### **Query 5 — End-to-End Request Correlation**
```kql
requests
| join kind=inner (traces) on operation_Id
| project operation_Id, name, timestamp, message, customDimensions
```

### **Query 6 — Recent Errors in Traces**
```kql
traces
| where severityLevel >= 3
| project timestamp, name, message, customDimensions
| order by timestamp desc
```

---

## 🔹 5. Advanced AI Foundry Features
When using Azure AI Foundry:
- Evaluations (`log_evaluation`, `EvaluationContext`) appear automatically under trace events.
- You can visualize **agent hops**, **model completions**, and **evaluation metrics** in sequence.
- The Foundry UI correlates spans from multiple services (e.g., LangChain → RAG → Evaluator).

**Tip:** Click *“View in Application Insights”* to access raw traces and run KQL queries directly.

---

## 🔹 6. Troubleshooting & Best Practices
- Ensure `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` is set **before** SDK instrumentation.
- Avoid logging sensitive data.
- Use `EvaluationContext` for grouped metric logging.
- Use console export during development.

---

### ✅ Example — Combined Evaluation and Tracing
```python
with telemetry_manager.create_span("chat_response", {"user_id": "42"}):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Tell me about Dubai."}],
    )

    with EvaluationContext(response_id="resp_42") as eval_ctx:
        eval_ctx.add_metric("relevance", 0.9, "Accurate and to the point")
        eval_ctx.add_metric("coherence", 0.8, "Well-structured")
```

This will emit structured telemetry visible both in Azure AI Foundry and in Application Insights with all span, evaluation, and custom attributes captured.

---

**References:**
- [Azure Monitor OpenTelemetry documentation](https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry-enable)

