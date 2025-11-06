import azure.functions as func
import json
import logging
import os
import uuid
from datetime import datetime
from openai import AzureOpenAI
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

# Initialize Application Insights tracing
connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if connection_string:
    configure_azure_monitor(connection_string=connection_string)

# Add console exporter for local debugging
tracer_provider = trace.get_tracer_provider()
if isinstance(tracer_provider, TracerProvider):
    tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

tracer = trace.get_tracer(__name__)

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def log_evaluation(response_id: str, evaluator_name: str, score: float, comments: str = ""):
    """
    Log an evaluation metric for a response following AI Foundry conventions
    """
    with tracer.start_as_current_span(f"gen_ai.evaluation.{evaluator_name}") as span:
        span.set_attribute("gen_ai.evaluation.id", str(uuid.uuid4()))
        span.set_attribute("gen_ai.evaluation.score", score)
        span.set_attribute("gen_ai.evaluator.name", evaluator_name)
        span.set_attribute("gen_ai.response.id", response_id)

        if comments:
            logging.info(f"Evaluation {evaluator_name}: {score} - {comments}")
        else:
            logging.info(f"Evaluation {evaluator_name}: {score}")


def evaluate_response(response_id: str, response_text: str, user_query: str):
    """
    Run multiple evaluations on the AI response
    """
    # Relevance evaluation (mock scoring)
    relevance_score = 0.9 if "weather" in user_query.lower() else 0.7
    log_evaluation(response_id, "relevance", relevance_score, "Response addresses the user's query")

    # Coherence evaluation (mock scoring based on response length)
    coherence_score = 0.85 if len(response_text) > 50 else 0.6
    log_evaluation(response_id, "coherence", coherence_score, "Response is well-structured")

    # Groundedness evaluation (mock scoring - assumes weather data is grounded)
    groundedness_score = 0.95
    log_evaluation(response_id, "groundedness", groundedness_score, "Response is based on retrieved data")


def get_weather(location: str, unit: str = "celsius") -> dict:
    """
    Mock weather API call - simulates fetching weather data
    """
    with tracer.start_as_current_span("get_weather_api_call") as span:
        span.set_attribute("location", location)
        span.set_attribute("unit", unit)

        # Mock weather data
        mock_weather = {
            "location": location,
            "temperature": 22 if unit == "celsius" else 72,
            "unit": unit,
            "condition": "Sunny",
            "humidity": 65,
            "wind_speed": 10
        }

        logging.info(f"Fetched weather for {location}: {mock_weather}")
        span.set_attribute("weather.temperature", mock_weather["temperature"])
        span.set_attribute("weather.condition", mock_weather["condition"])

        return mock_weather


# Define the weather tool schema for OpenAI
weather_tool = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a specific location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g., San Francisco, CA"
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "The temperature unit to use"
                }
            },
            "required": ["location"]
        }
    }
}


@app.route(route="weather", methods=["POST", "GET"])
def weather_chat(req: func.HttpRequest) -> func.HttpResponse:
    """
    Azure Function that handles weather queries using Azure OpenAI with tool calling
    """
    with tracer.start_as_current_span("weather_chat_function") as span:
        try:
            # Generate unique response ID for correlation
            response_id = f"resp_{uuid.uuid4().hex[:12]}"

            # Get user message from request
            if req.method == "POST":
                req_body = req.get_json()
                user_message = req_body.get('message', 'What is the weather in Dubai?')
            else:
                user_message = req.params.get('message', 'What is the weather in Dubai?')

            span.set_attribute("user.message", user_message)
            span.set_attribute("gen_ai.response.id", response_id)
            span.set_attribute("gen_ai.system", "azure_openai")
            logging.info(f"Received message: {user_message} (response_id: {response_id})")

            # Initialize Azure OpenAI client
            client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
            )

            deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")

            # First API call with tool definition
            with tracer.start_as_current_span("openai_initial_request") as api_span:
                api_span.set_attribute("gen_ai.system", "azure_openai")
                api_span.set_attribute("gen_ai.request.model", deployment_name)
                api_span.set_attribute("gen_ai.response.id", response_id)
                api_span.set_attribute("model", deployment_name)

                messages = [
                    {"role": "system", "content": "You are a helpful weather assistant. Use the get_weather function to fetch weather information."},
                    {"role": "user", "content": user_message}
                ]

                response = client.chat.completions.create(
                    model=deployment_name,
                    messages=messages,
                    tools=[weather_tool],
                    tool_choice="auto"
                )

                response_message = response.choices[0].message

                # Token counting
                if hasattr(response, 'usage') and response.usage:
                    api_span.set_attribute("gen_ai.usage.input_tokens", response.usage.prompt_tokens)
                    api_span.set_attribute("gen_ai.usage.output_tokens", response.usage.completion_tokens)
                    api_span.set_attribute("gen_ai.usage.total_tokens", response.usage.total_tokens)
                    logging.info(f"Initial request tokens - Input: {response.usage.prompt_tokens}, Output: {response.usage.completion_tokens}")

                api_span.set_attribute("response.finish_reason", response.choices[0].finish_reason)
                api_span.set_attribute("gen_ai.response.finish_reason", response.choices[0].finish_reason)

            # Check if the model wants to call a tool
            tool_calls = response_message.tool_calls

            if tool_calls:
                # Execute tool calls
                messages.append(response_message)

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    logging.info(f"Calling tool: {function_name} with args: {function_args}")

                    # Call the weather function
                    if function_name == "get_weather":
                        function_response = get_weather(**function_args)

                        # Add tool response to messages
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": json.dumps(function_response)
                        })

                # Second API call with tool results
                with tracer.start_as_current_span("openai_final_request") as final_span:
                    final_span.set_attribute("gen_ai.system", "azure_openai")
                    final_span.set_attribute("gen_ai.request.model", deployment_name)
                    final_span.set_attribute("gen_ai.response.id", response_id)

                    final_response = client.chat.completions.create(
                        model=deployment_name,
                        messages=messages
                    )

                    final_message = final_response.choices[0].message.content

                    # Token counting for final response
                    if hasattr(final_response, 'usage') and final_response.usage:
                        final_span.set_attribute("gen_ai.usage.input_tokens", final_response.usage.prompt_tokens)
                        final_span.set_attribute("gen_ai.usage.output_tokens", final_response.usage.completion_tokens)
                        final_span.set_attribute("gen_ai.usage.total_tokens", final_response.usage.total_tokens)
                        logging.info(f"Final request tokens - Input: {final_response.usage.prompt_tokens}, Output: {final_response.usage.completion_tokens}")

                    final_span.set_attribute("response.content_length", len(final_message))
                    final_span.set_attribute("gen_ai.response.finish_reason", final_response.choices[0].finish_reason)

                    logging.info(f"Final response: {final_message}")
            else:
                # No tool call needed
                final_message = response_message.content

            span.set_attribute("response.success", True)
            span.set_attribute("response.length", len(final_message))

            # Run evaluations on the response
            evaluate_response(response_id, final_message, user_message)

            return func.HttpResponse(
                json.dumps({
                    "response": final_message,
                    "user_message": user_message,
                    "response_id": response_id
                }),
                mimetype="application/json",
                status_code=200
            )

        except Exception as e:
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            logging.error(f"Error processing request: {str(e)}")

            return func.HttpResponse(
                json.dumps({"error": str(e)}),
                mimetype="application/json",
                status_code=500
            )
