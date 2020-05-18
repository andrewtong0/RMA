from enum import Enum


class IDENTIFIERS(Enum):
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


class RedditFilterActions(Enum):
    SHADOWBAN = "Shadowban"
    WATCHLIST = "Watchlist"


class Restrictions(Enum):
    TITLE_CHAR_MAX = 255
    EMBED_BODY_CHAR_MAX = 5999


class StringConstants(Enum):
    STRING_POST = "Post"
    STRING_COMMENT = "Comment"
    TIMESTAMP_TITLE = "Timestamp"
    STRING_TRUNCATE = "..."


# Currently only works with 1 word strings (e.g. links) with whitespace checks
def create_regex_string(regex_matchers):
    return ".*((" + ")|(".join(regex_matchers) + ")).*"
