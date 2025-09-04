# bootstrap_nltk.py
import os
import pathlib
import nltk

# Use local nltk_data folder inside project
NLTK_DIR = pathlib.Path(__file__).parent.joinpath("nltk_data")
NLTK_DIR.mkdir(exist_ok=True)
if str(NLTK_DIR) not in nltk.data.path:
    nltk.data.path.append(str(NLTK_DIR))

# Try to ensure VADER is available; if SSL issues, we still look in local dir
try:
    from nltk.sentiment.vader import SentimentIntensityAnalyzer  # noqa
except LookupError:
    try:
        nltk.download("vader_lexicon", download_dir=str(NLTK_DIR))
    except Exception:
        # do not crash here; caller may handle absence gracefully
        pass
