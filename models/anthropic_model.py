from litellm import completion
from .base_model import BaseAIModel
import os
from pydantic import BaseModel
from typing import Optional, Type


class AnthropicModel(BaseAIModel):
    def __init__(
        self, model_name: str = "claude-3-5-sonnet-20241022", max_tokens: int = 4000
    ):
        super().__init__(model_name, max_tokens)
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    def generate_text(
        self, prompt: str, response_format: Optional[Type[BaseModel]] = None
    ) -> Optional[BaseModel]:
        try:
            response = completion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                api_key=self.api_key,
                num_retries=3,
                **(
                    {"response_format": {"type": "json_object"}}
                    if response_format
                    else {}
                ),
            )
            if response and response.choices and response.choices[0].message.content:
                cleaned_json = self.clean_json_text(response.choices[0].message.content)
                if cleaned_json:
                    return response_format.model_validate_json(cleaned_json)
                else:
                    return None
            else:
                return None
        except Exception as e:
            print(f"Error generating text with Anthropic: {e}")
            return None
