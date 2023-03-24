import constants
import user_preferences
from advanced_filter_files import semantic_analysis


def apply_advanced_filter(filter_type, post):
    if user_preferences.SENTIMENT_ANALYSIS_ENABLED and filter_type == constants.RedditFilterTypes.ADVANCED_SENTIMENT_ANALYSIS.value:
        return semantic_analysis.check_post_sentiment_violated(post)
    else:
        return None
