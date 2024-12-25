import json
import re
import requests
from bs4 import BeautifulSoup
import time
from typing import List, Dict, Union
import os
from collections import OrderedDict
import numpy as np
import hdbscan
from sentence_transformers import SentenceTransformer
from prompts import (
    FILTER_NOISY_COMMENTS_PROMPT,
    EVALUATE_PREDICTIONS_PROMPT,
    IDENTIFY_THEMES_PROMPT,
)
from schemas import (
    CommentClassification,
    PredictionEvaluation,
    ThemesList,
)
from cache_manager import CacheManager  # Import CacheManager
from models import BaseAIModel


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


def is_comment_noisy(
    comments: List[Dict],
    model: BaseAIModel,
    cache_manager: CacheManager,
    batch_size: int = 10,
    retry_count: int = 3,
    retry_delay: int = 1,
    retry_backoff_factor: int = 2,
) -> List[bool]:
    """
    Checks if comments are noisy using the provided model.
    Processes comments in batches to avoid token limits.

    Args:
        comments: A list of comments
        model: The model to use for evaluation
        cache_manager: CacheManager instance for caching results
        batch_size: Number of comments to process in each batch
        retry_count: Number of retries on failure
        retry_delay: Initial delay between retries
        retry_backoff_factor: Factor to increase delay between retries

    Returns:
        A list of booleans indicating if each comment is noisy
    """

    results = []

    # Function to process a single batch
    def process_batch(batch_comments: List[Dict]):
        batch_texts = [comment["text"] for comment in batch_comments]
        cached_results = cache_manager.load_cache(
            model.model_name, "noisy_comments", batch_comments
        )
        if cached_results:
            return cached_results
        else:
            prompt = FILTER_NOISY_COMMENTS_PROMPT.format(
                comments="\n".join(batch_texts)
            )
            for attempt in range(retry_count):
                try:
                    response = model.call_with_retry(
                        prompt, response_format=CommentClassification
                    )
                    if response:
                        cache_manager.save_cache(
                            model.model_name,
                            "noisy_comments",
                            batch_comments,
                            response.is_noisy,
                        )
                        return response.is_noisy
                    else:
                        if attempt == retry_count - 1:
                            print(
                                f"Failed to process batch after {retry_count} attempts, no json returned"
                            )
                            return [False] * len(batch_texts)
                        else:
                            delay = retry_delay * (retry_backoff_factor**attempt)
                            time.sleep(delay)
                except Exception as e:
                    if attempt == retry_count - 1:
                        print(
                            f"Failed to process batch after {retry_count} attempts: {e}"
                        )
                        return [False] * len(batch_texts)
                    else:
                        delay = retry_delay * (retry_backoff_factor**attempt)
                        time.sleep(delay)

    # Process batches
    for i in range(0, len(comments), batch_size):
        batch = comments[i : i + batch_size]
        results.extend(process_batch(batch))

    return results


def extract_predictions_with_retry(
    batch: List[Dict],
    model: BaseAIModel,
    cache_manager: CacheManager,
    max_retries: int = 3,
    retry_delay: int = 1,
) -> List[Dict]:
    """
    Attempts to extract predictions from a batch of comments with retry logic.
    """

    # Check cache first
    cached_predictions = cache_manager.load_cache(
        model.model_name, "predictions", batch
    )
    if cached_predictions:
        return cached_predictions

    batch_texts = [item["text"] for item in batch]

    for attempt in range(max_retries):
        try:
            prompt = EVALUATE_PREDICTIONS_PROMPT.format(comments="\n".join(batch_texts))
            response = model.call_with_retry(
                prompt, response_format=PredictionEvaluation
            )
            if response:
                # Cache the results
                cache_manager.save_cache(
                    model.model_name,
                    "predictions",
                    batch,
                    [prediction.model_dump() for prediction in response.predictions],
                )
                return [
                    prediction.model_dump() for prediction in response.predictions
                ]  # Ensure return is a dict for easier use
            else:
                if attempt == max_retries - 1:  # Last attempt
                    print(
                        f"Failed to extract predictions after {max_retries} attempts, no json returned"
                    )
                    return []
                time.sleep(retry_delay * (2**attempt))
        except Exception as e:
            if attempt == max_retries - 1:  # Last attempt
                print(
                    f"Failed to extract predictions after {max_retries} attempts: {e}"
                )
                return []
            time.sleep(retry_delay * (2**attempt))

    return []


def cluster_predictions(
    predictions: List[Dict],
    min_cluster_size: int = 2,
    max_iterations=3,
    level=0,
    unique_id_prefix="",
) -> Dict[str, List[Dict]]:
    """Clusters predictions using HDBSCAN with sentence transformers, recursively clustering subclusters."""

    model = SentenceTransformer("all-MiniLM-L6-v2")
    prediction_texts = [p["prediction"] for p in predictions]
    embeddings = model.encode(prediction_texts)

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size, gen_min_span_tree=True
    )
    cluster_labels = clusterer.fit_predict(embeddings)

    clustered_predictions = {}
    for i, label in enumerate(cluster_labels):
        unique_cluster_id = f"{unique_id_prefix}{label}"  # Use a unique identifier for each cluster (including subclusters)
        if unique_cluster_id not in clustered_predictions:
            clustered_predictions[unique_cluster_id] = []
        clustered_predictions[unique_cluster_id].append(predictions[i])

    # check sizes of cluster if over min_cluster_size then run it again
    if level < max_iterations:
        new_clustered_predictions = {}
        for key, value in clustered_predictions.items():
            if len(value) > 100:
                print(f"Recursing cluster id: {key} with {len(value)} predictions")
                subclusters = cluster_predictions(
                    value,
                    min_cluster_size,
                    max_iterations,
                    level + 1,
                    unique_id_prefix=f"{key}-",
                )
                new_clustered_predictions.update(subclusters)
            else:
                new_clustered_predictions[key] = value
        return new_clustered_predictions

    return clustered_predictions


def identify_themes(
    predictions: List[Dict],
    evaluated_predictions: List[Dict],
    model: BaseAIModel,
    cache_manager: CacheManager,
    batch_size: int = 10,
) -> ThemesList:
    """
    Identifies themes in a list of predictions using the provided model.
    Processes predictions in batches to avoid token limits.
    """
    # First cluster the predictions
    clustered_predictions = cluster_predictions(predictions)

    all_themes = []

    for cluster_id, predictions_in_cluster in clustered_predictions.items():
        # Prepare the input data
        prompt_data = []
        for prediction in predictions_in_cluster:
            # we will add the predictions here, instead of creating a combined string
            prompt_data.append(prediction["prediction"])

        print(
            f"Processing cluster id: {cluster_id} with {len(prompt_data)} predictions"
        )
        prompt = IDENTIFY_THEMES_PROMPT.format(
            predictions_and_evaluations="\n".join(prompt_data)
        )
        response = model.call_with_retry(prompt, response_format=ThemesList)
        if response:
            # create a map of the returned themes to the original data from step 2.
            # We cannot directly send evaluated_predictions since hdbscan returns a different number of clusters.
            for theme in response.themes:
                theme_predictions = []
                for theme_prediction in theme.predictions:
                    for prediction, eval_prediction in zip(
                        predictions, evaluated_predictions
                    ):
                        if theme_prediction == prediction["prediction"]:
                            theme_predictions.append(
                                {
                                    "prediction": prediction["prediction"],
                                    "probability": prediction["probability"],
                                    "justification": prediction["justification"],
                                }
                            )
                theme.predictions = theme_predictions
            all_themes.extend(response.themes)

    result = ThemesList(themes=all_themes)
    # Cache the results
    cache_key = [str(p) for p in predictions] + [
        str(ep) for ep in evaluated_predictions
    ]
    cache_manager.save_cache(model.model_name, "themes", cache_key, result.model_dump())
    return result


def serialize_data(themes: ThemesList, filename, model):
    """Serializes the data to a JSON file."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    themes_data = []
    for theme in themes.themes:
        theme_data = {
            "theme": theme.theme,
            "summary": theme.summary,
            "predictions": theme.predictions,
        }
        themes_data.append(theme_data)

    data = {"themes": themes_data, "model": model.model_name}
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
