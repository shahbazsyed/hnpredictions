"""Module containing Pydantic schemas for structured outputs."""

from pydantic import BaseModel, Field, conlist, confloat
from typing import List, Optional

class CommentClassification(BaseModel):
    """Represents the classification of a list of comments."""
    is_noisy: List[bool] = Field(
        description="A list of booleans, where `true` indicates a noisy comment and `false` a non-noisy one, in corresponding order to the input."
    )

class Prediction(BaseModel):
    """Represents a single prediction with its evaluation."""
    prediction: str = Field(description="The verbatim prediction extracted from the comment")
    probability: confloat(ge=0, le=1) = Field(description="Estimated probability of the prediction coming true (0-1)")
    justification: str = Field(description="Brief explanation of the probability assessment")

class PredictionEvaluation(BaseModel):
    """Represents the evaluation of predictions from a set of comments."""
    predictions: List[Prediction] = Field(description="List of evaluated predictions")

class Theme(BaseModel):
    """Represents a theme identified in the predictions."""
    theme: str = Field(description="Name of the theme")
    summary: str = Field(description="Brief description of what the theme encompasses")
    predictions: List[str] = Field(description="List of predictions that fall under this theme")

class ThemesList(BaseModel):
    """Represents a collection of identified themes."""
    themes: List[Theme] = Field(description="List of identified themes")
