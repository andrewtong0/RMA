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


class Restrictions(Enum):
    TITLE_CHAR_MAX = 252


# Currently only works with 1 word strings (e.g. links) with whitespace checks
def create_regex_string(regex_matchers):
    return ".*((" + ")|(".join(regex_matchers) + ")).*"
