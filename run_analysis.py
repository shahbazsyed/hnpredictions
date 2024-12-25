import os
import argparse
from dotenv import load_dotenv
from models import GeminiModel, OpenAIModel, AnthropicModel, OllamaModel, GroqModel
from analyse_predictions import (
    fetch_hacker_news_comments,
    is_comment_noisy,
    extract_predictions_with_retry,
    identify_themes,
    serialize_data,
)
from schemas import CommentClassification, PredictionEvaluation, ThemesList
from cache_manager import CacheManager


def get_model_by_name(model_name: str):
    """Get model instance by name."""
    models = {
        "gemini": lambda: GeminiModel(),
        "openai": lambda: OpenAIModel(),
        "anthropic": lambda: AnthropicModel(),
        #'ollama': lambda: OllamaModel("llama2:13b"),
        "groq": lambda: GroqModel("llama3-70b-8192"),
    }
    if model_name not in models:
        raise ValueError(
            f"Unknown model: {model_name}. Available models: {', '.join(models.keys())}"
        )
    return models[model_name]()


def run_analysis_for_model(
    model, comments, cache_manager: CacheManager, batch_size=5, force_rerun=False
):
    """Run the analysis pipeline for a specific model."""

    if force_rerun:
        cache_manager.clear_cache(model.model_name)

    # Step 1: Filter out noisy comments
    print("\nStep 1: Filtering comments...")
    filtered_comments = []
    current_batch = []

    # Prepare batches of comment dicts
    for comment in comments:
        # Ensure comments are a dict with a "text" key
        if isinstance(comment, str):
            comment = {"text": comment}

        # Create standardized comment object for all steps
        comment_obj = {"text": comment.get("text", "")}

        if isinstance(comment, dict) and "text" in comment:
            current_batch.append(comment_obj)

            if len(current_batch) >= batch_size:
                # Process the batch
                noisy_flags = is_comment_noisy(
                    current_batch, model, cache_manager, batch_size=batch_size
                )

                # Add non-noisy comments to filtered list
                for orig_comment, is_noisy in zip(current_batch, noisy_flags):
                    if not is_noisy:
                        filtered_comments.append(orig_comment)

                current_batch = []

    # Process any remaining comments
    if current_batch:
        noisy_flags = is_comment_noisy(
            current_batch, model, cache_manager, batch_size=batch_size
        )

        for orig_comment, is_noisy in zip(current_batch, noisy_flags):
            if not is_noisy:
                filtered_comments.append(orig_comment)

    print(f"Filtered {len(comments) - len(filtered_comments)} noisy comments")
    print(f"Remaining comments: {len(filtered_comments)}")

    # Step 2: Extract predictions
    print("\nStep 2: Extracting predictions...")
    all_predictions = []

    # Process filtered comments in batches
    for i in range(0, len(filtered_comments), batch_size):
        batch = filtered_comments[i : i + batch_size]
        print(
            f"Processing batch {i//batch_size + 1}/{(len(filtered_comments) + batch_size - 1)//batch_size}"
        )
        predictions = extract_predictions_with_retry(batch, model, cache_manager)
        if predictions:
            all_predictions.extend(predictions)

    print(f"Extracted {len(all_predictions)} predictions")

    # Step 3: Identify themes
    print("\nStep 3: Identifying themes...")
    themes = identify_themes(
        all_predictions, all_predictions, model, cache_manager, batch_size=batch_size
    )

    print("Themese identified:")
    print(themes)

    return filtered_comments, all_predictions, themes


def main():
    parser = argparse.ArgumentParser(
        description="Run prediction analysis on HN comments"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini",
        choices=["gemini", "openai", "anthropic", "groq"],
        help="Model to use for analysis",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Number of comments to process in each batch",
    )
    parser.add_argument(
        "--force-rerun",
        action="store_true",
        help="Force rerun analysis, ignoring cache",
    )
    args = parser.parse_args()

    # Initialize the model
    model = get_model_by_name(args.model)

    # Initialize cache manager
    cache_manager = CacheManager()

    # Get comments from HN
    print("Fetching comments from Hacker News...")
    comments = fetch_hacker_news_comments("42490343")
    print(f"Found {len(comments)} comments")

    print(f"Running analysis for {len(comments)} comments")
    # Run analysis
    filtered_comments, predictions, themes = run_analysis_for_model(
        model=model,
        comments=comments,
        cache_manager=cache_manager,
        batch_size=args.batch_size,
        force_rerun=args.force_rerun,
    )

    # Serialize results
    print("\nSerializing results...")
    output_file_model_name = (
        model.model_name.split("/")[1] if "/" in model.model_name else model.model_name
    )
    serialize_data(
        themes,
        f"outputs/predictions_data_{output_file_model_name}.json",
        model,
    )

    print("\nAnalysis complete!")
    print(f"Processed {len(comments)} comments")
    print(f"Found {len(filtered_comments)} non-noisy comments")
    print(f"Extracted {len(predictions)} predictions")
    print(f"Identified {len(themes.themes) if themes else 0} themes")


if __name__ == "__main__":
    load_dotenv()
    main()
