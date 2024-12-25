import json
import os
import hashlib
from pathlib import Path
from typing import List, Dict, Union


class CacheManager:
    def __init__(self, cache_dir="cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def compute_data_hash(self, data: Union[List[Dict], List[str]]) -> str:
        """Compute a hash of the input data for cache key."""
        if isinstance(data, list):
            if all(isinstance(item, dict) for item in data):
                # For lists of dicts (comments), hash their text content
                data_str = "".join(str(item.get("text", "")) for item in data)
            else:
                data_str = "".join(str(item) for item in data)
        else:
            data_str = str(data)
        return hashlib.md5(data_str.encode()).hexdigest()[:8]

    def get_cache_path(self, model_name: str, step: str, data_hash: str) -> Path:
        """Get the cache file path for a specific model, step, and data hash."""
        safe_model_name = model_name.replace("/", "_").replace("-", "_")
        return self.cache_dir / f"{safe_model_name}_{step}_{data_hash}.json"

    def load_cache(
        self, model_name: str, step: str, input_data: Union[List[Dict], List[str]]
    ) -> dict:
        """Load cached data for a specific model, step, and input data."""
        data_hash = self.compute_data_hash(input_data)
        cache_path = self.get_cache_path(model_name, step, data_hash)
        if cache_path.exists():
            try:
                with open(cache_path, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Cache file {cache_path} is corrupted")
        return None

    def save_cache(
        self,
        model_name: str,
        step: str,
        input_data: Union[List[Dict], List[str]],
        result_data: dict,
    ):
        """Save data to cache for a specific model, step, and input data."""
        data_hash = self.compute_data_hash(input_data)
        cache_path = self.get_cache_path(model_name, step, data_hash)
        with open(cache_path, "w") as f:
            json.dump(result_data, f, indent=2)

    def clear_cache(self, model_name: str = None):
        """Clear cache for a specific model or all models."""
        if model_name:
            safe_model_name = model_name.replace("/", "_").replace("-", "_")
            for cache_file in self.cache_dir.glob(f"{safe_model_name}_*.json"):
                cache_file.unlink()
        else:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
