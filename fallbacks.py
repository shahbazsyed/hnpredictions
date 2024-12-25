"""Module containing fallback parsing logic for model responses."""

import json
import re
from schemas import CommentClassification, PredictionEvaluation, ThemesList

def clean_json_text(text: str) -> str:
    """Clean and fix common JSON formatting issues."""
    # Remove markdown code block markers
    text = re.sub(r'```(?:json)?\n?(.*?)```', r'\1', text, flags=re.DOTALL)
    
    # Remove any non-JSON text before or after the JSON content
    text = re.sub(r'^[^{\[]*', '', text)
    text = re.sub(r'[^}\]]*$', '', text)
    
    # Fix common formatting issues
    text = text.replace("'", '"')  # Replace single quotes with double quotes
    text = re.sub(r'//.*?\n', '\n', text)  # Remove single-line comments
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)  # Remove multi-line comments
    
    return text.strip()

def parse_noisy_comments(text: str, batch_size: int) -> CommentClassification:
    """Parse model response for noisy comments classification."""
    text = clean_json_text(text)
    
    try:
        # Try parsing as direct JSON array
        data = json.loads(text)
        if isinstance(data, list) and all(isinstance(x, bool) for x in data):
            return CommentClassification(is_noisy=data)
            
        # Try parsing as object with results field
        if isinstance(data, dict) and "results" in data:
            results = data["results"]
            if isinstance(results, list) and all(isinstance(x, bool) for x in results):
                return CommentClassification(is_noisy=results)
                
    except json.JSONDecodeError:
        pass
        
    # Fallback: Try to extract boolean array from text
    pattern = r'\[(.*?)\]'
    match = re.search(pattern, text)
    if match:
        try:
            values = [x.strip().lower() == "true" for x in match.group(1).split(",")]
            if len(values) == batch_size:
                return CommentClassification(is_noisy=values)
        except Exception:
            pass
            
    # If all parsing attempts fail, return all False
    return CommentClassification(is_noisy=[False] * batch_size)

def parse_predictions(text: str) -> PredictionEvaluation:
    """Parse model response for prediction evaluation."""
    text = clean_json_text(text)
    
    try:
        # Try parsing as direct JSON
        data = json.loads(text)
        
        # Handle case where predictions are directly in root
        if isinstance(data, list):
            return PredictionEvaluation(predictions=data)
            
        # Handle case where predictions are in a 'predictions' field
        if isinstance(data, dict) and "predictions" in data:
            return PredictionEvaluation(predictions=data["predictions"])
            
    except json.JSONDecodeError:
        pass
        
    # If all parsing attempts fail, return empty predictions list
    return PredictionEvaluation(predictions=[])

def parse_themes(text: str) -> ThemesList:
    """Parse model response for theme identification."""
    text = clean_json_text(text)
    
    try:
        # Try parsing as direct JSON
        data = json.loads(text)
        
        # Handle case where themes are in a 'themes' field
        if isinstance(data, dict) and "themes" in data:
            return ThemesList(**data)
            
        # Handle case where themes are directly in root
        if isinstance(data, list):
            return ThemesList(themes=data)
            
    except json.JSONDecodeError:
        pass
        
    # If all parsing attempts fail, return empty themes list
    return ThemesList(themes=[])
