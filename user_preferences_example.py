from enum import Enum
import constants
import environment_variables


# Class constructor for a subreddit and its associated channels to send messages to
class SubredditAndChannels:
    def __init__(self, subreddit, main_channel_ids, post_channel_ids, comment_channel_ids, ping_channel_ids, secondary_review_channel_ids, status_channel_ids, embed_colour, has_mod):
        self.subreddit = subreddit
        self.main_channel_ids = main_channel_ids
        self.post_channel_ids = post_channel_ids
        self.comment_channel_ids = comment_channel_ids
        self.ping_channel_ids = ping_channel_ids
        self.secondary_review_channel_ids = secondary_review_channel_ids
        self.status_channel_ids = status_channel_ids
        self.embed_colour = embed_colour
        self.has_mod = has_mod


# Arrays to iterate and check through each subreddit with associated channels
# Production channels
ProdSubredditsAndChannels = []


# Developer channels
DevSubredditsAndChannels = []

# Filters that should also update the values in the wiki
SyncedFilters = []
RegexFilters = []
FilterSeparator = "---"


# Single-point editing array depending on DEV_MODE flag
SelectedSubredditsAndChannels = []
if environment_variables.DEV_MODE:
    SelectedSubredditsAndChannels = DevSubredditsAndChannels
else:
    SelectedSubredditsAndChannels = ProdSubredditsAndChannels


ActionPriorityDictionary = {
    constants.FilterActions.REMOVE.value: 4,
    "4": constants.FilterActions.REMOVE.value,

    constants.FilterActions.MONITOR.value: 1,
    "1": constants.FilterActions.MONITOR.value,

    "0": None
}


class Settings(Enum):
    BOT_PREFIX = "!"
    BOT_SECONDARY_REVIEW_ROLE = "Secondary_Review"


class BotConsts(Enum):
    POLL_TIMER = 5.0
