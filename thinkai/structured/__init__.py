"""Structured Output模块 - 约束LLM输出为Pydantic模型"""
import json
import re
from typing import Type, List, Optional

from pydantic import BaseModel, ValidationError

from thinkai.core.models import ChatMessage
from thinkai.exceptions import ThinkAiError


class StructuredOutputError(ThinkAiError):
    """Structured output error"""

    def __init__(self, message: str):
        super().__init__(message=message, code="STRUCTURED_OUTPUT_ERROR")


def generate_schema_prompt(model_class: Type[BaseModel]) -> str:
    """Generate a prompt that describes the expected JSON schema"""
    schema = model_class.model_json_schema()

    descriptions = []
    for field_name, field_info in model_class.model_fields.items():
        if field_info.description:
            descriptions.append(f"  - {field_name}: {field_info.description}")

    descriptions_text = (
        "\n".join(descriptions)
        if descriptions
        else "  No specific field descriptions provided."
    )

    return (
        "You must extract information and output it as a JSON object matching the following schema.\n"
        "\n"
        "JSON Schema:\n"
        f"{json.dumps(schema, indent=2, ensure_ascii=False)}\n"
        "\n"
        "Field descriptions:\n"
        f"{descriptions_text}\n"
        "\n"
        "IMPORTANT: Output ONLY valid JSON matching the schema above. "
        "Do not include any other text, explanation, or markdown formatting."
    )


def parse_json_response(response: str) -> dict:
    """Extract JSON from LLM response (handles ```json...``` blocks)"""
    json_block_match = re.search(
        r"```json\s*\n?(.*?)\n?\s*```", response, re.DOTALL
    )
    if json_block_match:
        return json.loads(json_block_match.group(1))

    code_block_match = re.search(r"```\s*\n?(.*?)\n?\s*```", response, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError:
            pass

    brace_count = 0
    start = -1
    for i, char in enumerate(response):
        if char == "{":
            if brace_count == 0:
                start = i
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0 and start != -1:
                try:
                    return json.loads(response[start : i + 1])
                except json.JSONDecodeError:
                    start = -1
                    continue

    return json.loads(response)


def validate_and_create(model_class: Type[BaseModel], data: dict) -> BaseModel:
    """Validate and create Pydantic instance"""
    return model_class.model_validate(data)


class StructuredOutput:
    """Wraps ThinkAI client to extract structured data constrained by a Pydantic model."""

    def __init__(self, ai_client):
        self.ai_client = ai_client

    async def extract(
        self, text: str, model_class: Type[BaseModel], **kwargs
    ) -> BaseModel:
        """Extract structured data from text using LLM"""
        schema_prompt = generate_schema_prompt(model_class)

        current_messages = [
            ChatMessage.system(schema_prompt),
            ChatMessage.user(text),
        ]

        max_retries = 2

        for attempt in range(max_retries + 1):
            response = await self.ai_client.chat(messages=current_messages, **kwargs)
            content = response.content or ""

            try:
                parsed = parse_json_response(content)
                return validate_and_create(model_class, parsed)
            except (json.JSONDecodeError, ValidationError) as e:
                if attempt < max_retries:
                    error_feedback = (
                        f"Your previous response was invalid. Error: {e}. "
                        "Please output ONLY valid JSON matching the schema."
                    )
                    current_messages.append(ChatMessage.assistant(content))
                    current_messages.append(ChatMessage.user(error_feedback))
                else:
                    raise StructuredOutputError(
                        f"Failed to extract structured output after "
                        f"{max_retries + 1} attempts: {e}"
                    ) from e

        raise StructuredOutputError("Failed to extract structured output")

    async def extract_batch(
        self, texts: List[str], model_class: Type[BaseModel], **kwargs
    ) -> List[BaseModel]:
        """Extract structured data from multiple texts"""
        results = []
        for text in texts:
            result = await self.extract(text, model_class, **kwargs)
            results.append(result)
        return results


__all__ = [
    "StructuredOutput",
    "StructuredOutputError",
    "generate_schema_prompt",
    "parse_json_response",
    "validate_and_create",
]
