import azure.functions as func
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Optional
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


def log_evaluation(response_id: str, evaluator_name: str, score: float, comments: str = "", reasoning: str = ""):
    """
    Log an evaluation metric for a response following AI Foundry conventions
    """
    with tracer.start_as_current_span(f"gen_ai.evaluation.{evaluator_name}") as span:
        span.set_attribute("gen_ai.evaluation.id", str(uuid.uuid4()))
        span.set_attribute("gen_ai.evaluation.score", score)
        span.set_attribute("gen_ai.evaluator.name", evaluator_name)
        span.set_attribute("gen_ai.response.id", response_id)

        # Store reasoning in the evaluation span
        if reasoning:
            span.set_attribute("evaluation.reasoning", reasoning)

        if comments:
            logging.info(f"Evaluation {evaluator_name}: {score} - {comments}")
        else:
            logging.info(f"Evaluation {evaluator_name}: {score}")


def evaluate_with_llm(client, deployment_name: str, response_id: str,
                       response_text: str, user_query: str, criterion: str,
                       context: str = "") -> tuple[float, str]:
    """
    Use an LLM as a judge to evaluate the response on a specific criterion
    Returns: (score, reasoning)
    """
    evaluation_prompts = {
        "relevance": f"""You are an expert evaluator. Assess how relevant the AI response is to the user's query.

User Query: {user_query}
AI Response: {response_text}

Rate the relevance on a scale of 0.0 to 1.0 where:
- 1.0 = Perfectly addresses the query
- 0.7 = Mostly relevant with minor issues
- 0.5 = Partially relevant
- 0.3 = Barely relevant
- 0.0 = Completely irrelevant

Respond in JSON format:
{{"score": <float between 0.0 and 1.0>, "reasoning": "<brief explanation>"}}""",

        "coherence": f"""You are an expert evaluator. Assess how coherent and well-structured the AI response is.

AI Response: {response_text}

Rate the coherence on a scale of 0.0 to 1.0 where:
- 1.0 = Perfectly coherent, logical, and well-structured
- 0.7 = Mostly coherent with minor issues
- 0.5 = Somewhat coherent
- 0.3 = Poorly structured or confusing
- 0.0 = Incoherent

Respond in JSON format:
{{"score": <float between 0.0 and 1.0>, "reasoning": "<brief explanation>"}}""",

        "groundedness": f"""You are an expert evaluator. Assess if the AI response is grounded in the provided context/data.

Context/Retrieved Data: {context}
AI Response: {response_text}

Rate the groundedness on a scale of 0.0 to 1.0 where:
- 1.0 = Completely grounded, no hallucinations
- 0.7 = Mostly grounded with minor extrapolations
- 0.5 = Partially grounded
- 0.3 = Significant hallucinations
- 0.0 = Completely ungrounded

Respond in JSON format:
{{"score": <float between 0.0 and 1.0>, "reasoning": "<brief explanation>"}}""",

        "helpfulness": f"""You are an expert evaluator. Assess how helpful the AI response is to the user.

User Query: {user_query}
AI Response: {response_text}

Rate the helpfulness on a scale of 0.0 to 1.0 where:
- 1.0 = Extremely helpful, actionable information
- 0.7 = Helpful with good information
- 0.5 = Somewhat helpful
- 0.3 = Minimally helpful
- 0.0 = Not helpful at all

Respond in JSON format:
{{"score": <float between 0.0 and 1.0>, "reasoning": "<brief explanation>"}}"""
    }

    prompt = evaluation_prompts.get(criterion, evaluation_prompts["relevance"])

    with tracer.start_as_current_span(f"llm_judge.{criterion}") as span:
        span.set_attribute("gen_ai.evaluation.criterion", criterion)
        span.set_attribute("gen_ai.response.id", response_id)

        try:
            judge_response = client.chat.completions.create(
                model=deployment_name,
                messages=[
                    {"role": "system", "content": "You are a precise evaluator that returns scores in valid JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,  # Deterministic evaluation
                max_tokens=300
            )

            result_text = judge_response.choices[0].message.content.strip()

            # Track token usage for evaluation
            if hasattr(judge_response, 'usage') and judge_response.usage:
                span.set_attribute("gen_ai.usage.input_tokens", judge_response.usage.prompt_tokens)
                span.set_attribute("gen_ai.usage.output_tokens", judge_response.usage.completion_tokens)

            # Parse JSON response
            result = json.loads(result_text)
            score = float(result.get("score", 0.0))
            reasoning = result.get("reasoning", "No reasoning provided")

            # Clamp score between 0 and 1
            score = max(0.0, min(1.0, score))

            span.set_attribute("evaluation.score", score)
            span.set_attribute("evaluation.reasoning", reasoning)

            return score, reasoning

        except Exception as e:
            logging.error(f"Error in LLM evaluation for {criterion}: {str(e)}")
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            # Fallback to neutral score
            return 0.5, f"Evaluation failed: {str(e)}"


def evaluate_response(response_id: str, response_text: str, user_query: str,
                       context: str = "", client=None, deployment_name: Optional[str] = None):
    """
    Run multiple LLM-as-a-judge evaluations on the AI response
    """
    if client is None or deployment_name is None:
        logging.warning("No OpenAI client provided, skipping evaluations")
        return

    # Relevance evaluation using LLM judge
    relevance_score, relevance_reasoning = evaluate_with_llm(
        client, deployment_name, response_id, response_text, user_query, "relevance"
    )
    log_evaluation(response_id, "relevance", relevance_score, reasoning=relevance_reasoning)

    # Coherence evaluation using LLM judge
    coherence_score, coherence_reasoning = evaluate_with_llm(
        client, deployment_name, response_id, response_text, user_query, "coherence"
    )
    log_evaluation(response_id, "coherence", coherence_score, reasoning=coherence_reasoning)

    # Groundedness evaluation using LLM judge (with context)
    groundedness_score, groundedness_reasoning = evaluate_with_llm(
        client, deployment_name, response_id, response_text, user_query, "groundedness", context
    )
    log_evaluation(response_id, "groundedness", groundedness_score, reasoning=groundedness_reasoning)

    # Helpfulness evaluation using LLM judge
    helpfulness_score, helpfulness_reasoning = evaluate_with_llm(
        client, deployment_name, response_id, response_text, user_query, "helpfulness"
    )
    log_evaluation(response_id, "helpfulness", helpfulness_score, reasoning=helpfulness_reasoning)


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
            weather_context = ""  # Track context for groundedness evaluation

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
                        weather_context = json.dumps(function_response)  # Capture for evaluation

                        # Add tool response to messages
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": weather_context
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
                final_message = response_message.content or ""

            span.set_attribute("response.success", True)
            span.set_attribute("response.length", len(final_message))

            # Run evaluations on the response with LLM-as-a-judge
            if final_message:
                evaluate_response(
                    response_id=response_id,
                    response_text=final_message,
                    user_query=user_message,
                    context=weather_context,
                    client=client,
                    deployment_name=deployment_name
                )

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
