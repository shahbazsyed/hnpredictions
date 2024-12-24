import json
import re
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import time
import random
import os
from dotenv import load_dotenv

load_dotenv()


def fetch_hacker_news_comments(item_id):
    """
    Fetches all comments and their reply levels for a Hacker News post.

    Args:
      item_id: The ID of the Hacker News post.

    Returns:
      A list of dictionaries, where each dictionary represents a comment
      and contains keys: 'text', 'level', 'author', 'time'.
      Returns an empty list if the item_id is invalid or an error occurs.
    """
    url = f"https://news.ycombinator.com/item?id={item_id}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise an HTTPError exception for bad status code

        soup = BeautifulSoup(response.content, "html.parser")
        comment_sections = soup.find_all("tr", class_="athing comtr")

        comments_data = []
        for comment_section in comment_sections:
            level = 0
            # Find the comment indentation, the image for the comment level is an "img" tag with a "width" attribute
            indent_img = comment_section.find("img", attrs={"width": True})
            if indent_img:
                # If it exists, the level is calculated from width and a hardcoded scale
                level = int(indent_img["width"]) // 40

            # Extract the author
            author_link = comment_section.find("a", class_="hnuser")
            author = author_link.text if author_link else "Anonymous"

            # Extract the comment's time
            time_span = comment_section.find("span", class_="age")
            time = time_span.text if time_span else "Unknown Time"

            # Extract the comment text
            comment_text_element = comment_section.find("div", class_="comment")
            text = ""
            if comment_text_element:
                # Extract the comment text, removing extra tags
                for text_element in comment_text_element.find_all(text=True):
                    text += text_element
                    text = re.sub(r"\s+", " ", text)
            text = text.strip()
            # Append to the list
            comments_data.append(
                {"text": text, "level": level, "author": author, "time": time}
            )

        return comments_data

    except requests.exceptions.RequestException as e:
        print(f"An error occurred fetching the URL: {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return []


FILTER_NOISY_COMMENTS_PROMPT = """
You are an expert at identifying relevant comments in an online discussion. You will be given a list of comments, and your task is to determine if each comment is noisy or not, as determined by these criteria:

- Sarcastic comments
- Meta comments from moderators
- Comments that contain only URLs.
- Comments that do not contain any actual predictions for the future.
- Exchanges between participants of the discussion that are not directly related to a prediction.

For each comment in the list, return "True" if the comment is noisy according to the rules above. Otherwise, return "False". The response should be a JSON object with the format:

{{
    "results": [true, false, true, false,...]
}}

Here are the comments: {comments}
"""

EVALUATE_PREDICTIONS_PROMPT = """
You are an expert in evaluating predictions. Your task is to analyze a list of comments from an online discussion and determine the likelihood of each prediction coming true.

Analyze the comments and extract each unique prediction. Discard any sarcastic, noisy, URL-only comments or any exchange between users that are not related to a specific prediction. For each prediction you find, provide a **complete** JSON response in the following format:

[
    {{
        "prediction": "verbatim prediction from the comment",
        "probability": "score between 0 (impossible) and 1 (certain), with 0.5 representing a 50/50 chance",
        "justification": "explanation for the prediction probability, providing statistics, facts, or scientific theories when possible"
    }},
    ...
]

Only provide JSON, do not include any text outside the JSON output.

Here are the comments: {comments}
"""

IDENTIFY_THEMES_PROMPT = """
You are an expert in analyzing text to identify recurring themes. You will be given a list of predictions. Your task is to identify and summarize the main themes present in these predictions. For each theme, return the theme and also a short summary that represents all the predictions that it contains.

Your response should be in the following JSON format:

[
    {{
        "theme": "theme 1 summary",
        "theme_summary": "a summary of the predictions grouped by the theme",
        "predictions": [
            {{
                "prediction": "verbatim prediction from the comment"
            }},
            ...
        ]
    }},
    ...
]

Here are the predictions: {predictions}
"""


def call_gemini(
    prompt,
    gemini_model,
    max_tokens=4000,
    retry_count=3,
    retry_delay=1,
    retry_backoff_factor=2,
):
    """
    Calls the Gemini API with the given prompt, with retry and exponential backoff.
    """

    for attempt in range(retry_count):
        try:
            response = gemini_model.generate_content(
                prompt, generation_config={"max_output_tokens": max_tokens}
            )
            return response.text
        except Exception as e:
            print(f"An error occurred: {e}, retrying in {retry_delay} seconds...")
            if attempt == retry_count - 1:
                print("Max retries reached. Giving up")
                return None
            time.sleep(retry_delay + random.uniform(-0.1, 0.1))
            retry_delay *= retry_backoff_factor
    return None


def is_comment_noisy(
    comments,
    gemini_model,
    max_tokens=1000,
    retry_count=3,
    retry_delay=1,
    retry_backoff_factor=2,
):
    """
    Checks if a list of comments are noisy using Gemini.

    Returns:
      A list of booleans, where True indicates a noisy comment, or an empty list if an error occurred.
    """
    prompt = FILTER_NOISY_COMMENTS_PROMPT.format(comments=comments)

    for attempt in range(retry_count):
        try:
            response = gemini_model.generate_content(
                prompt, generation_config={"max_output_tokens": max_tokens}
            )
            text_response = response.text
            parsed_response = parse_json_with_fallback_is_comment_noisy(
                text_response, len(comments)
            )
            if parsed_response:
                return parsed_response
            else:
                print(f"Received unparsable response: {text_response}")
                return []
        except Exception as e:
            print(f"An error occurred: {e}, retrying in {retry_delay} seconds...")
            if attempt == retry_count - 1:
                print("Max retries reached. Giving up")
                return []
            time.sleep(retry_delay + random.uniform(-0.1, 0.1))
            retry_delay *= retry_backoff_factor
    return []  # Should never arrive here since we already gave up at the max number of retries


def parse_json_with_fallback_is_comment_noisy(text, batch_size):
    """
    Parses JSON from a string, handling Markdown code block wrappers, for is_comment_noisy
    """
    if not text:
        print("Received empty string as response")
        return None
    try:
        # Attempt to parse the text directly as JSON first
        # Relax parsing, if there is text outside the actual JSON, it may fail
        text = re.sub(r"//.*", "", text)
        json_match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(0).strip())
            if (
                isinstance(parsed, dict)
                and "results" in parsed
                and isinstance(parsed["results"], list)
                and len(parsed["results"]) == batch_size
            ):
                return parsed["results"]
            else:
                if not isinstance(parsed, dict):
                    print(f"Parsed object does not have results key: {parsed}")
                else:
                    print(
                        f"Parsed list has incorrect size: {len(parsed['results'])}, expected: {batch_size}"
                    )
                return None
        else:
            parsed = json.loads(text)
            if (
                isinstance(parsed, dict)
                and "results" in parsed
                and isinstance(parsed["results"], list)
                and len(parsed["results"]) == batch_size
            ):
                return parsed["results"]
            else:
                if not isinstance(parsed, dict):
                    print(f"Parsed object does not have results key: {parsed}")
                else:
                    print(
                        f"Parsed list has incorrect size: {len(parsed['results'])}, expected: {batch_size}"
                    )
                return None

    except json.JSONDecodeError:
        # Try extracting JSON from a Markdown code block (```json ... ```)
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            try:
                text = re.sub(r"//.*", "", match.group(1))
                parsed = json.loads(text.strip())
                if (
                    isinstance(parsed, dict)
                    and "results" in parsed
                    and isinstance(parsed["results"], list)
                    and len(parsed["results"]) == batch_size
                ):
                    return parsed["results"]
                else:
                    if not isinstance(parsed, dict):
                        print(f"Parsed object does not have results key: {parsed}")
                    else:
                        print(
                            f"Parsed list has incorrect size: {len(parsed['results'])}, expected: {batch_size}"
                        )
                    return None
            except json.JSONDecodeError:
                print("Could not decode text from code block: ", text)
                return None
        else:
            print("Could not decode text at all: ", text)
            return None


def parse_json_with_fallback_evaluate_predictions(text):
    """
    Parses JSON from a string, handling Markdown code block wrappers for evaluate_predictions.
    Expects a list of prediction objects, each with 'prediction', 'probability', and 'justification' fields.
    """
    if not text:
        print("Received empty string as response")
        return None
    try:
        # Attempt to parse the text directly as JSON first
        text = re.sub(r"//.*", "", text)
        json_match = re.search(r"(\[.*\])", text, re.DOTALL)  # Only match lists
        if json_match:
            parsed = json.loads(json_match.group(0).strip())
            if isinstance(parsed, list) and all(
                isinstance(p, dict) 
                and "prediction" in p 
                and "probability" in p 
                and "justification" in p 
                for p in parsed
            ):
                return parsed
            else:
                print(f"Parsed object is not a valid list of predictions: {parsed}")
                return None
        else:
            parsed = json.loads(text)
            if isinstance(parsed, list) and all(
                isinstance(p, dict) 
                and "prediction" in p 
                and "probability" in p 
                and "justification" in p 
                for p in parsed
            ):
                return parsed
            else:
                print(f"Parsed object is not a valid list of predictions: {parsed}")
                return None

    except json.JSONDecodeError:
        # Try extracting JSON from a Markdown code block
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            try:
                text = re.sub(r"//.*", "", match.group(1))
                parsed = json.loads(text.strip())
                if isinstance(parsed, list) and all(
                    isinstance(p, dict) 
                    and "prediction" in p 
                    and "probability" in p 
                    and "justification" in p 
                    for p in parsed
                ):
                    return parsed
                else:
                    print(f"Parsed object is not a valid list of predictions: {parsed}")
                    return None
            except json.JSONDecodeError:
                print("Could not decode text from code block: ", text)
                return None
        else:
            print("Could not decode text at all: ", text)
            return None


def parse_json_with_fallback_identify_themes(text):
    """
    Parses JSON from a string, handling Markdown code block wrappers for identify_themes.
    Expects an array of theme objects, each containing theme info and predictions.
    """
    if not text:
        print("Received empty string as response")
        return None

    def is_valid_theme_response(parsed):
        return (
            isinstance(parsed, list)
            and all(
                isinstance(theme, dict)
                and "theme" in theme
                and "predictions" in theme
                and isinstance(theme["predictions"], list)
                and all(
                    isinstance(p, dict)
                    and isinstance(p.get("prediction"), str)
                    for p in theme["predictions"]
                )
                for theme in parsed
            )
        )

    try:
        # Attempt to parse the text directly as JSON first
        text = re.sub(r"//.*", "", text)
        json_match = re.search(r"(\[.*\])", text, re.DOTALL)  # Only match arrays
        if json_match:
            parsed = json.loads(json_match.group(0).strip())
            if is_valid_theme_response(parsed):
                return parsed
            print(f"Parsed object is not a valid themes response: {parsed}")
            return None

        # Try parsing the whole text if no match found
        parsed = json.loads(text)
        if is_valid_theme_response(parsed):
            return parsed
        print(f"Parsed object is not a valid themes response: {parsed}")
        return None

    except json.JSONDecodeError:
        # Try extracting JSON from a Markdown code block
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            try:
                text = re.sub(r"//.*", "", match.group(1))
                parsed = json.loads(text.strip())
                if is_valid_theme_response(parsed):
                    return parsed
                print(f"Parsed object is not a valid themes response: {parsed}")
                return None
            except json.JSONDecodeError:
                print("Could not decode text from code block: ", text)
                return None
        print("Could not decode text at all: ", text)
        return None


def identify_themes(predictions, evaluated_predictions, model_name="gemini-pro"):
    """
    Identifies themes in a list of predictions using Gemini and enriches them with evaluation data.
    
    Args:
        predictions: List of prediction texts to group into themes
        evaluated_predictions: List of fully evaluated predictions with probability and justification
        model_name: Name of the Gemini model to use
    """
    # Create a lookup dictionary for quick access to evaluated predictions
    prediction_lookup = {p["prediction"]: p for p in evaluated_predictions}
    
    # Extract just the prediction texts for theme identification
    prediction_texts = [{"prediction": p["prediction"]} for p in evaluated_predictions]
    
    prompt = IDENTIFY_THEMES_PROMPT.format(predictions=prediction_texts)
    response = call_gemini(prompt, model_name)
    
    if response:
        theme_clusters = parse_json_with_fallback_identify_themes(response)
        if theme_clusters:
            # Enrich the predictions in each cluster with their evaluation data
            for cluster in theme_clusters:
                if cluster.get("predictions"):
                    enriched_predictions = []
                    for pred in cluster["predictions"]:
                        pred_text = pred["prediction"]
                        if pred_text in prediction_lookup:
                            # Add the evaluation data to the prediction
                            enriched_predictions.append(prediction_lookup[pred_text])
                    
                    # Replace the predictions array with enriched predictions
                    cluster["predictions"] = sorted(
                        enriched_predictions,
                        key=lambda x: float(x.get("probability", 0)),
                        reverse=True,
                    )
            return theme_clusters
    return None


def categorize_prediction(prediction):
    """Categorizes a prediction based on its probability."""

    probability = float(prediction.get("probability", "0"))  # defaults to 0

    if probability >= 0.7:
        return "Likely"
    elif probability >= 0.3:
        return "Maybe"
    else:
        return "Unlikely"


def serialize_data(categorized_predictions, filename, model):
    """Serializes the data to a JSON file."""
    data = {"categorized_predictions": categorized_predictions, "model": model}
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)


def extract_predictions_with_retry(batch, gemini_model, max_retries=3, retry_delay=1):
    """
    Attempts to extract predictions from a batch of comments with retry logic.
    
    Args:
        batch: List of comments to process
        gemini_model: The Gemini model to use
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
    
    Returns:
        List of predictions or None if all attempts fail
    """
    for attempt in range(max_retries):
        try:
            prompt = EVALUATE_PREDICTIONS_PROMPT.format(comments=batch)
            gemini_response = call_gemini(prompt, gemini_model)
            if not gemini_response:
                print(f"Attempt {attempt + 1}: Empty response from Gemini")
                continue
                
            parsed_response = parse_json_with_fallback_evaluate_predictions(gemini_response)
            if parsed_response:
                return parsed_response
            
            print(f"Attempt {attempt + 1}: Failed to parse JSON response")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                
        except Exception as e:
            print(f"Attempt {attempt + 1}: Error processing batch: {str(e)}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2
    
    return None


if __name__ == "__main__":
    # get comments from item_id = 42490343 (https://news.ycombinator.com/item?id=42490343)
    comments = fetch_hacker_news_comments("42490343")
    print(f"Successfully fetched {len(comments)} comments from the discussion.")
    batch_size = 10  
    prediction_batch_size = 10 
    models = [
        "gemini-1.5-pro",
    ]  
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    comments = comments[:100]
    genai.configure(api_key=GEMINI_API_KEY)
    for model in models:
        print(f"Running with model {model}...")
        gemini_model = genai.GenerativeModel(model)
        # Take a sample of comments
        filtered_comments = []
        print("Step 1: Filtering Noisy Comments...")
        for i in range(0, len(comments), batch_size):
            batch = comments[i : i + batch_size]
            print(f"Processing comments {i} to {i + batch_size}")
            response = is_comment_noisy(batch, gemini_model)
            if response:
                if len(response) == len(batch):  # Check lengths
                    for index, is_noisy in enumerate(response):
                        if not is_noisy:
                            filtered_comments.append(batch[index])
                else:
                    print(
                        f"Error: Skipping batch with invalid response size, received:{len(response)}, expected: {len(batch)}"
                    )
            else:
                print("Error: Received an empty response from Gemini.")

        # Test on a sample of comments
        all_predictions = []
        print("\n")
        print("Step 2: Extracting Predictions...")
        for i in range(0, len(filtered_comments), prediction_batch_size):
            batch = filtered_comments[i : i + prediction_batch_size]
            print(
                f"Extracting predictions for batch {i} to {i + prediction_batch_size}"
            )
            parsed_response = extract_predictions_with_retry(batch, gemini_model)
            if parsed_response:
                all_predictions.extend(parsed_response)
            else:
                print("Failed to parse JSON for batch after all retries")

        if all_predictions:
            print(
                f"Extracted {len(all_predictions)} predictions from {len(filtered_comments)} comments."
            )
        else:
            print("Failed to parse any JSON for the predictions.")
            continue
        print("\n")
        print("Step 3: Categorizing Predictions and Identifying Themes...")
        # Categorize Predictions and Identify Themes
        categorized_predictions = {
            "Likely": [],
            "Maybe": [],
            "Unlikely": [],
        }
        for prediction in all_predictions:
            category = categorize_prediction(prediction)
            categorized_predictions[category].append(prediction)

        clustered_predictions = {}
        for category, predictions in categorized_predictions.items():
            print(f"Step 3.1: Identifying Themes for {category} Predictions...")
            if predictions:
                themes_response = identify_themes(predictions, predictions, gemini_model)
                if themes_response:
                    clustered_predictions[category] = themes_response
                else:
                    print(f"Failed to identify themes for {category}.")
                    clustered_predictions[category] = []
            else:
                clustered_predictions[category] = []

        serialize_data(clustered_predictions, f"predictions_data_{model}.json", model)
        print(f"Data exported to predictions_data_{model}.json")

        print("\n--- Prediction Category Counts ---")
        for category, predictions in categorized_predictions.items():
            count = len(predictions)
            print(f"{category}: {count} predictions")

        for category, clusters in clustered_predictions.items():
            print(f"\n--- Predictions categorized as '{category}' ---")
            if clusters:
                for cluster in clusters:
                    print(f"Theme: {cluster['theme']}")
                    for prediction in cluster['predictions']:
                        print(f"  - {prediction['prediction']}")
            else:
                print(f"No predictions in this category {category}.")
