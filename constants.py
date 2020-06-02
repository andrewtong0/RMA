from enum import Enum


class Identifiers(Enum):
    DISCORD_MENTION_PREFIX = "@"


# Enumeration to store supported platforms
class Platforms(Enum):
    REDDIT = "reddit"


# Enumeration to store entry types
class DbEntry(Enum):
    REDDIT_SUBMISSION = "reddit_submission"
    REDDIT_COMMENT = "reddit_comment"


# Enumeration to store filter actions
class FilterActions(Enum):
    REMOVE = "remove"
    MONITOR = "monitor"


# Enumeration to store Reddit filter types
class RedditFilterTypes(Enum):
    USERS = "users"
    SUBREDDITS = "subreddits"
    POSTS = "posts"


class RedditUserUpsertStatus(Enum):
    SUCCESS = "success"
    SUSPENDED = "suspended"
    MISSING = "missing"


class RedditFilterOperationTypes(Enum):
    ADD = "add"
    REMOVE = "remove"
    ERROR = "error"


class RedditFilterActions(Enum):
    SHADOWBAN = "Shadowban"
    WATCHLIST = "Watchlist"


class MessageLimitActions(Enum):
    TRUNCATE = "truncate"
    MULTI = "multi"
    PAGINATE = "paginate"


class CharacterLimits(Enum):
    EMBED_TITLE = 256
    EMBED_DESCRIPTION = 2048
    EMBED_AUTHOR = 256
    EMBED_FOOTER = 2048
    EMBED_NUM_FIELDS = 25
    EMBED_FIELD_NAME = 256
    EMBED_FIELD_VALUE = 1024
    EMBED_TOTAL_CHARS = 6000


class StringConstants(Enum):
    STRING_POST = "Post"
    STRING_COMMENT = "Comment"
    TIMESTAMP_TITLE = "Timestamp"
    STRING_TRUNCATE = "..."
    EMBED_FIELD_TRUNCATE_MESSAGE = "Embed truncated to exclude {} post(s)."
    EMBED_FIELD_TRUNCATE_NUMBER = 6  # For above string, we reserve this many characters for the count of # posts removed (e.g. 6 = a 6 digit number)


class RedditDiscordChannelTypes(Enum):
    RD_CHANNELTYPE_ALL = "rd_all"
    RD_CHANNELTYPE_POSTS = "rd_posts"
    RD_CHANNELTYPE_COMMENTS = "rd_comments"
    RD_CHANNELTYPE_PINGS = "rd_pings"


# Currently only works with 1 word strings (e.g. links) with whitespace checks
def create_regex_string(regex_matchers):
    return ".*((" + ")|(".join(regex_matchers) + ")).*"
