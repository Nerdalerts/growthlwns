import json
import pytest
from pydantic import BaseModel
from copilot.llm import LLMClient, LLMConfig, extract_json_block


class SampleResponse(BaseModel):
    sql: str
    metric: str
    confidence: float


def test_extract_json_block():
    markdown_wrapped = "Here is the response:\n```json\n{\"sql\": \"SELECT 1\", \"metric\": \"gmv\", \"confidence\": 0.95}\n```\nDone."
    raw = extract_json_block(markdown_wrapped)
    data = json.loads(raw)
    assert data["sql"] == "SELECT 1"

    plain_json = '{"sql": "SELECT 2", "metric": "aov", "confidence": 0.8}'
    assert json.loads(extract_json_block(plain_json))["metric"] == "aov"


def test_llm_client_mock_successful_call():
    client = LLMClient(config=LLMConfig(api_key="mock-key"))
    client.set_mock_handler(
        lambda prompt, sys: '{"sql": "SELECT COUNT(*) FROM orders", "metric": "order_count", "confidence": 1.0}'
    )

    result = client.call_structured(
        prompt="How many orders?",
        system_prompt="You are a SQL generator.",
        response_model=SampleResponse,
    )

    assert result.data is not None
    assert isinstance(result.data, SampleResponse)
    assert result.data.metric == "order_count"
    assert result.retries == 0
    assert result.input_tokens > 0
    assert result.output_tokens > 0


def test_llm_client_retry_on_invalid_json():
    client = LLMClient(config=LLMConfig(api_key="mock-key"))
    attempts = 0

    def mock_flaky(prompt, sys):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return "This is not valid JSON at all!"
        return '{"sql": "SELECT SUM(price) FROM order_items", "metric": "gmv", "confidence": 0.99}'

    client.set_mock_handler(mock_flaky)

    result = client.call_structured(
        prompt="What is GMV?",
        system_prompt="You are a SQL generator.",
        response_model=SampleResponse,
        max_retries=1,
    )

    assert result.data.metric == "gmv"
    assert result.retries == 1
    assert attempts == 2


def test_llm_client_raises_after_max_retries_exceeded():
    client = LLMClient(config=LLMConfig(api_key="mock-key"))
    client.set_mock_handler(lambda prompt, sys: "Still not JSON")

    with pytest.raises(ValueError, match="Failed to produce valid schema after 1 retry"):
        client.call_structured(
            prompt="What is GMV?",
            system_prompt="You are a SQL generator.",
            response_model=SampleResponse,
            max_retries=1,
        )


def test_gemini_provider_auto_detection(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTestKey12345")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = LLMConfig.from_env()
    assert config.provider == "gemini"
    assert config.api_key == "AIzaSyTestKey12345"
    assert "gemini" in config.model

    # Also test auto-detecting a Gemini key placed under ANTHROPIC_API_KEY
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "AIzaSyTestKeyPastedUnderAnthropic")
    config2 = LLMConfig.from_env()
    assert config2.provider == "gemini"
    assert config2.api_key == "AIzaSyTestKeyPastedUnderAnthropic"

