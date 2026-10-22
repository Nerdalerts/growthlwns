import json
import os
import re
import time
from typing import Any, Callable, Dict, Optional, Type, TypeVar
import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError
import requests

load_dotenv()

T = TypeVar("T", bound=BaseModel)

DEFAULT_ANTHROPIC_MODEL = "claude-3-5-sonnet-latest"
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"


class LLMConfig(BaseModel):
    api_key: Optional[str] = None
    model: str = DEFAULT_ANTHROPIC_MODEL
    provider: str = "anthropic"  # "anthropic" or "gemini"
    temperature: float = 0.0

    @classmethod
    def from_env(cls) -> "LLMConfig":
        load_dotenv()

        # Check Gemini keys first or Anthropic key
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        gemini_model = os.getenv("GEMINI_MODEL")
        anthropic_model = os.getenv("ANTHROPIC_MODEL")

        # Auto-detect if user passed a Gemini API key under ANTHROPIC_API_KEY
        if anthropic_key and (
            anthropic_key.startswith("AIza")
            or anthropic_key.startswith("AQ.")
            or not anthropic_key.startswith("sk-")
            or (anthropic_model and "gemini" in anthropic_model.lower())
            or os.getenv("LLM_PROVIDER", "").lower() == "gemini"
        ):
            gemini_key = anthropic_key
            anthropic_key = None


        if gemini_key:
            model = gemini_model or anthropic_model or DEFAULT_GEMINI_MODEL
            if "claude" in model.lower():
                model = DEFAULT_GEMINI_MODEL
            return cls(
                api_key=gemini_key,
                model=model,
                provider="gemini",
                temperature=0.0,
            )

        model = anthropic_model or DEFAULT_ANTHROPIC_MODEL
        return cls(
            api_key=anthropic_key,
            model=model,
            provider="anthropic",
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
        # If config was passed directly, auto-detect provider if needed
        if self.config.api_key and (
            self.config.api_key.startswith("AIza")
            or self.config.api_key.startswith("AQ.")
            or not self.config.api_key.startswith("sk-")
        ):
            self.config.provider = "gemini"
            if "claude" in self.config.model.lower():
                self.config.model = DEFAULT_GEMINI_MODEL
        elif "gemini" in self.config.model.lower():
            self.config.provider = "gemini"


        self._mock_handler: Optional[Callable[[str, str], str]] = None

    def set_mock_handler(self, handler: Optional[Callable[[str, str], str]]) -> None:
        """Used in test suites to mock LLM responses deterministically."""
        self._mock_handler = handler

    def _call_gemini_api(self, prompt: str, system_prompt: str) -> tuple[str, int, int]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model}:generateContent?key={self.config.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "systemInstruction": {
                "parts": [{"text": system_prompt}],
            },
            "generationConfig": {
                "temperature": self.config.temperature,
                "responseMimeType": "application/json",
            },
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code != 200:
            raise ValueError(f"Gemini API returned error ({resp.status_code}): {resp.text}")

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError(f"Gemini API returned no candidates: {data}")

        parts = candidates[0].get("content", {}).get("parts", [])
        raw_text = parts[0].get("text", "") if parts else ""

        usage = data.get("usageMetadata", {})
        input_tokens = usage.get("promptTokenCount", 0)
        output_tokens = usage.get("candidatesTokenCount", 0)

        return raw_text, input_tokens, output_tokens

    def _call_anthropic_api(self, prompt: str, system_prompt: str) -> tuple[str, int, int]:
        client = anthropic.Anthropic(api_key=self.config.api_key)
        response = client.messages.create(
            model=self.config.model,
            max_tokens=2048,
            temperature=self.config.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        return raw_text, input_tokens, output_tokens

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
                if not self.config.api_key or self.config.api_key == "your-api-key-here":
                    raise ValueError(
                        "No API key provided. Please set GEMINI_API_KEY (or ANTHROPIC_API_KEY) "
                        "in your .env file."
                    )

                if self.config.provider == "gemini":
                    call_text, in_tok, out_tok = self._call_gemini_api(current_prompt, enriched_system)
                else:
                    call_text, in_tok, out_tok = self._call_anthropic_api(current_prompt, enriched_system)

                raw_text = call_text
                input_tokens += in_tok
                output_tokens += out_tok

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
