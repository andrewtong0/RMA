import os
from transformers import pipeline
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import user_preferences
from environment_variables import SENTIMENT_ANALYSIS_MODEL_DIR, SENTIMENT_ANALYSIS_MODEL_NAME


def _save_model_to_disk(model_name_to_save):
    temp_tokenizer = AutoTokenizer.from_pretrained(model_name_to_save)
    temp_model = AutoModelForSequenceClassification.from_pretrained(model_name_to_save)

    temp_tokenizer.save_pretrained(SENTIMENT_ANALYSIS_MODEL_DIR)
    temp_model.save_pretrained(SENTIMENT_ANALYSIS_MODEL_DIR)


# Save model to disk if we don't have it (usually only done on first run)
if not os.path.exists(SENTIMENT_ANALYSIS_MODEL_DIR):
    _save_model_to_disk(SENTIMENT_ANALYSIS_MODEL_NAME)


tokenizer = AutoTokenizer.from_pretrained(SENTIMENT_ANALYSIS_MODEL_DIR)
model = AutoModelForSequenceClassification.from_pretrained(SENTIMENT_ANALYSIS_MODEL_DIR)
classifier = pipeline("sentiment-analysis", tokenizer=tokenizer, model=model)


def _classify_strings(strings):
    return classifier(strings)


def _match_feedback_string(res):
    score_str = str(round(res["score"], 3) * 100)
    return "Sentiment Score: {} (Threshold: {})".format(
        score_str, user_preferences.SENTIMENT_ANALYSIS_NEGATIVE_THRESHOLD)


def check_post_sentiment_violated(post):
    content_string = post["content"]
    res = _classify_strings(content_string)[0]
    if res["label"].lower() == "negative" and res["score"] >= user_preferences.SENTIMENT_ANALYSIS_NEGATIVE_THRESHOLD:
        return _match_feedback_string(res)
    else:
        return None
