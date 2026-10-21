import json
import os
import re
import time
from typing import Any, Callable, Dict, Optional, Type, TypeVar
import anthropic
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "claude-3-5-sonnet-latest"


class LLMConfig(BaseModel):
    api_key: Optional[str] = None
    model: str = DEFAULT_MODEL
    temperature: float = 0.0

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            model=os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL),
            temperature=0.0,
        )


class LLMResult(BaseModel):
    raw_content: str
    data: Optional[Any] = None
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    retries: int = 0


def extract_json_block(text: str) -> str:
    """Extract JSON from raw text or markdown code blocks."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Check if string starts with { or [
    start_brace = text.find("{")
    end_brace = text.rfind("}")
    if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
        return text[start_brace : end_brace + 1].strip()
    return text


class LLMClient:
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig.from_env()
        self._mock_handler: Optional[Callable[[str, str], str]] = None

    def set_mock_handler(self, handler: Optional[Callable[[str, str], str]]) -> None:
        """Used in test suites to mock LLM responses deterministically."""
        self._mock_handler = handler

    def call_structured(
        self,
        prompt: str,
        system_prompt: str,
        response_model: Type[T],
        max_retries: int = 1,
    ) -> LLMResult:
        start_time = time.time()
        retries = 0
        input_tokens = 0
        output_tokens = 0

        # Construct schema instruction to guarantee structured response
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        enriched_system = (
            f"{system_prompt}\n\n"
            "You MUST respond ONLY with valid JSON conforming to this JSON Schema:\n"
            f"{schema_json}\n"
            "Do not output markdown explanations or preamble outside the JSON."
        )

        current_prompt = prompt

        while retries <= max_retries:
            raw_text = ""
            if self._mock_handler:
                raw_text = self._mock_handler(current_prompt, enriched_system)
                input_tokens += len(current_prompt) // 4
                output_tokens += len(raw_text) // 4
            else:
                if not self.config.api_key:
                    raise ValueError(
                        "ANTHROPIC_API_KEY environment variable is not set. "
                        "Please set ANTHROPIC_API_KEY in your environment or .env file."
                    )
                client = anthropic.Anthropic(api_key=self.config.api_key)
                response = client.messages.create(
                    model=self.config.model,
                    max_tokens=2048,
                    temperature=self.config.temperature,
                    system=enriched_system,
                    messages=[{"role": "user", "content": current_prompt}],
                )
                raw_text = response.content[0].text
                input_tokens += response.usage.input_tokens
                output_tokens += response.usage.output_tokens

            # Attempt parsing JSON and validating against Pydantic model
            try:
                json_str = extract_json_block(raw_text)
                parsed_json = json.loads(json_str)
                validated_data = response_model.model_validate(parsed_json)
                latency_ms = int((time.time() - start_time) * 1000)

                return LLMResult(
                    raw_content=raw_text,
                    data=validated_data,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    retries=retries,
                )
            except (json.JSONDecodeError, ValidationError) as err:
                retries += 1
                if retries > max_retries:
                    latency_ms = int((time.time() - start_time) * 1000)
                    raise ValueError(
                        f"Failed to produce valid schema after {max_retries} retry. Error: {err}. Raw response: {raw_text}"
                    ) from err
                # Feed error back in follow-up attempt
                current_prompt = (
                    f"Your previous output was invalid.\n"
                    f"Error: {str(err)}\n"
                    f"Previous output was:\n{raw_text}\n\n"
                    "Please correct it and return ONLY valid JSON matching the schema."
                )

        raise RuntimeError("Unexpected loop exit in LLM structured call")
