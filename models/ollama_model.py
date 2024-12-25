from litellm import completion
from .base_model import BaseAIModel

class OllamaModel(BaseAIModel):
    def __init__(self, model_name: str = "llama2:13b", max_tokens: int = 4000):
        super().__init__(model_name, max_tokens)

    def generate_text(self, prompt: str) -> str:
        response = completion(
            model=f"ollama/{self.model_name}",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_tokens,
            num_retries=3
        )
        return response.choices[0].message.content
