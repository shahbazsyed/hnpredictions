"""Module containing all prompts used in the prediction analysis pipeline."""

FILTER_NOISY_COMMENTS_PROMPT = """
You are an expert at identifying relevant comments in an online discussion. Your task is to determine if each comment is "noisy" or "not noisy" based on these criteria:

**Noisy Comments:**
*   Sarcastic or joking comments.
*   Meta-comments about the discussion itself or other comments.
*   Comments that only contain URLs.
*   Comments that are generic statements or observations unrelated to specific future events.
*   Short replies or exchanges not directly making a prediction.
*   Comments expressing opinions or beliefs without predicting a concrete future outcome.

**Not Noisy Comments:**
*   Comments that make a *specific and testable* prediction about a future event or outcome.
*   Comments that predict a concrete future state related to real-world things or trends.

Respond with a JSON object in the following format:
{{
  "is_noisy": [<boolean>, <boolean>, ...]
}}

where the booleans correspond to the input comments in order and `true` means noisy, `false` is not noisy.

Do not include any explanation or code.

Comments to Evaluate:
{comments}
"""

EVALUATE_PREDICTIONS_PROMPT = """
You are an expert in extracting and evaluating predictions made by the participants abou the future. Given a list of comments, your task is to extract unique predictions from each comment and analyze the likelihood of each prediction coming true. For each prediction you find, provide a **complete** JSON response in the following format:

{{
    "predictions": [
        {{
            "prediction": "verbatim prediction from the comment",
            "probability": 0.75,  # Estimated probability between 0 and 1
            "justification": "Brief explanation of the probability assessment"
        }}
    ]
}}

Comments to Evaluate:
{comments}
"""

IDENTIFY_THEMES_PROMPT = """
You are an expert at identifying themes and patterns in texts. Given a list of statements, identify the major themes or categories they fall into.

For each theme, provide:
1. A short descriptive name
2. A brief summary of the statements denoting what the theme encompasses
3. A list of statements that fall under this theme

If the statements cannot be easily summarized into one specific theme, group them under a theme called "Other", and provide a description that explains why they don't fit into a cohesive theme.

Respond with a JSON object in the following format:
{{
    "themes": [
        {{
            "theme": "Theme name",
            "summary": "Brief theme description",
            "predictions": ["prediction 1", "prediction 2"]
        }}
    ]
}}

Predictions and evaluations:
{predictions_and_evaluations}
"""
