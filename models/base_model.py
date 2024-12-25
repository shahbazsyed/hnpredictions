from abc import ABC, abstractmethod
import time
from typing import List, Dict, Any, Optional, Type
from litellm import completion, RateLimitError
from pydantic import BaseModel
import re
import json


class BaseAIModel(ABC):
    def __init__(self, model_name: str, max_tokens: int = 4000):
        self.model_name = model_name
        self.max_tokens = max_tokens

    @abstractmethod
    def generate_text(
        self, prompt: str, response_format: Optional[Type[BaseModel]] = None
    ) -> Optional[BaseModel]:
        """Generate text from the model with the given prompt."""
        pass

    def clean_json_text(self, text: str | None) -> str | None:
        """Clean and fix common JSON formatting issues."""
        if not text:
            return None

        try:
            data = json.loads(text)
            # if the first key is the expected one, return the text directly
            if isinstance(data, dict) and (
                "predictions" in data or "is_noisy" in data or "themes" in data
            ):
                return json.dumps(data)

            # if we don't have the key at the top level, then look for it as a value
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, dict) and (
                        "predictions" in value
                        or "is_noisy" in value
                        or "themes" in value
                    ):
                        return json.dumps(value)
                    if isinstance(value, dict):
                        for k, v in value.items():
                            if isinstance(v, dict) and (
                                "predictions" in v or "is_noisy" in v or "themes" in v
                            ):
                                return json.dumps(v)

        except json.JSONDecodeError:
            # Remove markdown code block markers
            text = re.sub(r"```(?:json)?\n?(.*?)```", r"\1", text, flags=re.DOTALL)

            # Remove any non-JSON text before or after the JSON content
            text = re.sub(r"^[^{\[]*", "", text)
            text = re.sub(r"[^}\]]*$", "", text)

            # Fix common formatting issues
            text = text.replace("'", '"')  # Replace single quotes with double quotes
            text = re.sub(r"//.*?\n", "\n", text)  # Remove single-line comments
            text = re.sub(
                r"/\*.*?\*/", "", text, flags=re.DOTALL
            )  # Remove multi-line comments

            # Remove any invalid escape characters
            text = re.sub(
                r'\\([^\/"bfnrtu])', r"\1", text
            )  # Remove invalid escape sequences

            # Attempt to fix escaped characters
            text = text.replace('\\"', '"')  # fix escaped double quotes

            # Fix extra commas or other basic syntax issues.
            text = re.sub(r",\s*([}\]])", r"\1", text)  # remove trailing commas

            try:
                json.loads(text)
                return text.strip()
            except json.JSONDecodeError:
                return None

        return None

    def call_with_retry(
        self,
        prompt: str,
        retry_count: int = 3,
        retry_delay: int = 1,
        retry_backoff_factor: int = 2,
        response_format: Optional[Type[BaseModel]] = None,
    ) -> Optional[BaseModel]:
        """Call the model with retry logic."""
        current_delay = retry_delay
        e = None  # init e to None

        for attempt in range(retry_count):
            try:
                response = self.generate_text(prompt, response_format)
                if response:
                    return response
                else:
                    if attempt == retry_count - 1:  # Last attempt
                        print(
                            f"Failed to generate text after {retry_count} attempts. Error: {str(e)}"
                        )
                        return None
                    else:
                        delay = retry_delay * (retry_backoff_factor**attempt)
                        time.sleep(delay)
            except RateLimitError as exception:
                e = exception
                wait_time = (
                    e.retry_after if hasattr(e, "retry_after") else current_delay
                )
                if attempt == retry_count - 1:  # Last attempt
                    print(
                        f"Rate limit exceeded after {retry_count} attempts. Error: {str(e)}"
                    )
                    return None
                print(f"Rate limit hit. Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
                current_delay *= retry_backoff_factor
            except Exception as exception:
                e = exception
                if attempt == retry_count - 1:  # Last attempt
                    print(f"Failed after {retry_count} attempts. Error: {str(e)}")
                    return None
                print(
                    f"Attempt {attempt + 1} failed. Retrying in {current_delay} seconds..."
                )
                time.sleep(current_delay)
                current_delay *= retry_backoff_factor

        return None
