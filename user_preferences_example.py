from enum import Enum
from classes import SubredditAndChannels

# ================
# USER PREFERENCES
# ================
# ENSURE THIS FILE IS RENAMED TO user_preferences.py AFTER YOUR INFORMATION IS SET

# Arrays to iterate and check through each subreddit with associated channels

# Note: Channel IDs abbreviated to CIDs
# SubredditAndChannels(
#   subreddit name as string,
#   array of CIDs to send posts and comments to,
#   array of CIDs to send ONLY posts to,
#   array of CIDs to send ONLY comments to,
#   array of CIDs to send filter matches + pings to,
#   array of CIDs to send secondary review content to,
#   array of CIDs to send bot debug info to,
#   hex code of embed colour,
#   boolean flag whether bot has moderator access to subreddit,
# )

# e.g. ProdSubredditsAndChannels = [SubredditAndChannels("food", [12345], [12345, 78901], [], [], [78901], [12345], 0x000000, False)]
ProdSubredditsAndChannels = []


# Filters here also pass through validation to ensure regex phrase is valid
# When you create any regex filters, add the names of the filters here (as strings) so that regex phrases get validated
RegexFilters = []


class Settings(Enum):
    # Bot prefix for commands
    BOT_PREFIX = "!"
    # Specify the name of the role to ping when a secondary review is requested (no spaces allowed - use underscores)
    BOT_SECONDARY_REVIEW_ROLE = "Secondary_Review"


# Time in minutes before bot subsequently polls for new posts
class BotConsts(Enum):
    POLL_TIMER = 5.0


BlacklistedSubreddits = []
BlacklistedChannelIds = []

RepostChannelIds = []


# ===================
# POWER USER FEATURES
# ===================
# The features below here are a bit complicated to use - if you aren't completely sure how to use these, don't touch it

# Developer channels
# If you do not need a second set of subreddits and channels for debugging purposes, you can leave this
DevSubredditsAndChannels = []
DevRepostChannelIds = []

# Filters listed here will also sync content to the automoderator wiki
# e.g. When using a blacklist/shadowban filter, users can be added via the bot, which will also be synced to the wiki
# Example synced filter: {"filter_name": "Shadowbans", "filter_log_reason": "Shadowbanned user"}
# Changes made to the Shadowbans filter will be synced with the automod wiki and log the change as "Shadowbanned user
SyncedFilters = []
# Comment string used to separate filters in the automoderator configuration
FilterSeparator = "---"

SENTIMENT_ANALYSIS_ENABLED = False
SENTIMENT_ANALYSIS_NEGATIVE_THRESHOLD = 0.50
