from enum import Enum


class Identifiers(Enum):
    DISCORD_MENTION_PREFIX = "@"


# Enumeration to store supported platforms
class Platforms(Enum):
    REDDIT = "reddit"


# Enumeration to store entry types
class PostTypes(Enum):
    REDDIT_SUBMISSION = "reddit_submission"
    REDDIT_COMMENT = "reddit_comment"


# Enumeration to store filter actions
class FilterActions(Enum):
    REMOVE = "remove"
    REMOVE_MESSAGE = "==========\n🗑 Post Removed"
    MONITOR = "monitor"


# Enumeration to store Reddit filter types
class RedditFilterTypes(Enum):
    USERS = "users"
    SUBREDDITS = "subreddits"
    POSTS = "posts"
    MEDIA_SOURCE = "media_source"
    MEDIA_SOURCE_HISTORY = "media_source_history"
    ADVANCED_SENTIMENT_ANALYSIS = "sentiment_analysis"


class RedditUserUpsertStatus(Enum):
    SUCCESS = "success"
    SUSPENDED = "suspended"
    MISSING = "missing"


class RedditAutomodEditStatus(Enum):
    SUCCESS = "success"
    FAIL = "fail"
    MISSING_PRIVILEGES = "missing_privileges"


class RedditOperationTypes(Enum):
    ADD = "add"
    APPROVE = "approve"
    REMOVE = "remove"
    LOCK = "lock"
    UNLOCK = "unlock"
    ERROR = "error"


class RedditFilterActions(Enum):
    SHADOWBAN = "Shadowban"
    WATCHLIST = "Watchlist"


class MessageLimitActions(Enum):
    TRUNCATE = "truncate"
    MULTI = "multi"
    PAGINATE = "paginate"


class CharacterLimits(Enum):
    REGULAR_MESSAGE = 2000
    EMBED_TITLE = 256
    EMBED_DESCRIPTION = 2048
    EMBED_AUTHOR = 256
    EMBED_FOOTER = 2048
    EMBED_NUM_FIELDS = 25
    EMBED_FIELD_NAME = 256
    EMBED_FIELD_VALUE = 1024
    EMBED_TOTAL_CHARS = 6000


class RedditReactEmojis(Enum):
    GENERATE_USER_REPORT = "❔"             # White question mark
    GENERATE_NEGATIVE_COMMENT_TREE = "❗"    # Red exclamation mark
    CLEAR_GENERATED_EMBED = "❌"            # Red "X"
    SECONDARY_REVIEW_FLAG = "🚩"            # Red flag
    SECONDARY_REVIEW_APPROVE = "✅"         # Green check mark
    SECONDARY_REVIEW_REJECT = "🚫"          # Red "no-entry" sign
    SECONDARY_REVIEW_UPVOTE = "👍"          # Thumbs up
    SECONDARY_REVIEW_DOWNVOTE = "👎"        # Thumbs down
    ADD_POST_TO_USER_MOD_COMMENTS = "📝"    # Notepad and pencil
    POST_LOCK = "🔒"                        # Locked lock
    POST_UNLOCK = "🔓"                      # Unlocked lock
    POST_APPROVE = "☑"                     # Blue check mark
    POST_REMOVE = "🗑️"                     # Wastebasket
    EMOJI_CONTAINER = "[]"                  # Brackets surrounding react emoji feedback


# Reacts that after clicking, should remove original message
ReactsThatClearMessage = [
    RedditReactEmojis.CLEAR_GENERATED_EMBED.value,
    RedditReactEmojis.SECONDARY_REVIEW_APPROVE.value,
    RedditReactEmojis.SECONDARY_REVIEW_REJECT.value
]

# Reacts that shouldn't be removed after being clicked
ReactsThatPersist = [
    RedditReactEmojis.SECONDARY_REVIEW_FLAG.value,
    RedditReactEmojis.SECONDARY_REVIEW_UPVOTE.value,
    RedditReactEmojis.SECONDARY_REVIEW_DOWNVOTE.value,
    RedditReactEmojis.ADD_POST_TO_USER_MOD_COMMENTS.value,
    RedditReactEmojis.POST_APPROVE.value,
    RedditReactEmojis.POST_REMOVE.value
]

# Reacts that require mod status on the subreddit
ReactsThatRequireMod = [
    RedditReactEmojis.POST_APPROVE.value,
    RedditReactEmojis.POST_REMOVE.value,
    RedditReactEmojis.POST_LOCK.value,
    RedditReactEmojis.POST_UNLOCK.value
]


class RedditUrlConsts(Enum):
    key_string = "reddit.com/r/"
    url_delimiter = "/"
    query_param_indicator = "?"


class RedditEmbedConsts(Enum):
    post_colour = 0xc77d00
    comment_colour = 0xfbff00
    error_colour = 0xff0000
    approve_colour = 0x40e300
    reject_colour = 0xfc0000
    report_colour = 0xfffb00
    permalink_domain = "https://reddit.com"
    username_link = "https://reddit.com/u/"
    removed_thumbnail = "https://cdn4.iconfinder.com/data/icons/social-messaging-ui-coloricon-1/21/52-512.png"
    monitor_thumbnail = "https://c7.uihere.com/files/928/549/87/magnifying-glass-computer-icons-magnification-loupe.jpg"
    icon = "https://www.redditstatic.com/desktop2x/img/favicon/android-icon-192x192.png"
    regex_matchers = {
        "image": ["external\\-preview\\.redd\\.it", "preview\\.redd\\.it", "i\\.redd\\.it", "pbs\\.twimg\\.com"],
        "twitch_clip": ["twitch\\.tv"],
        "youtube": ["youtube\\.com"],
        "twitter": ["twitter\\.com"]
    }


class BotAuthorDetails(Enum):
    NAME = "RMA",
    ICON_URL = "https://www.redditstatic.com/desktop2x/img/favicon/android-icon-192x192.png"


class StringConstants(Enum):
    SUBMISSION_ID = "Submission ID: "
    COMMENT_ID = "Comment ID: "
    STRING_POST = "Post"
    STRING_COMMENT = "Comment"
    TIMESTAMP_TITLE = "Timestamp"
    STRING_TRUNCATE = "..."
    TRUNCATE_CODE_BLOCK_CHARS = '```'
    EMBED_FIELD_TRUNCATE_MESSAGE = "Embed truncated to exclude {} post(s)."
    EMBED_FIELD_TRUNCATE_NUMBER = 6  # For above string, we reserve this many characters for the count of # posts removed (e.g. 6 = a 6 digit number)
    SECONDARY_REVIEW_TITLE_PREFIX = "Secondary review requested"
    SECONDARY_REVIEW_REQUESTED_BY_SEPARATOR = "by"


class RedditDiscordChannelTypes(Enum):
    RD_CHANNELTYPE_ALL = "rd_all"
    RD_CHANNELTYPE_POSTS = "rd_posts"
    RD_CHANNELTYPE_COMMENTS = "rd_comments"
    RD_CHANNELTYPE_PINGS = "rd_pings"
    RD_CHANNELTYPE_SECONDARY_REVIEW = "rd_secondary_review"
    RD_CHANNELTYPE_REPORTS = "rd_reports"


class BotHealthMessages(Enum):
    POLLING_START = "Polling loop task has started."
    POLLING_UP = "Bot querying for posts..."
    TASK_FAILED_AND_RESTART = "An internal loop task has failed. Attempting to restart..."


class DatabaseMetadataInfo(Enum):
    IGNORE_BUFFER_NAME = "Ignore Buffer"  # Name field for the ignore buffer in the database metadata
    REPORT_TIMESTAMPS_NAME = "Latest Report Timestamps"  # Name field for report timestamps metadata
    REPORT_TIMESTAMPS_DESCRIPTION = "Stores timestamps of latest reports received per subreddit to determine whether " \
                                    "report stream contains new reports "


ActionPriorityDictionary = {
    FilterActions.REMOVE.value: 4,
    "4": FilterActions.REMOVE.value,

    FilterActions.MONITOR.value: 1,
    "1": FilterActions.MONITOR.value,

    "0": None
}


# Currently only works with 1 word strings (e.g. links) with whitespace checks
def create_regex_string(regex_matchers):
    return ".*((" + ")|(".join(regex_matchers) + ")).*"
