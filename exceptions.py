# CUSTOM EXCEPTIONS


# USED IN: praw_operations.py update_automoderator_filter_matches()
# When a name or value is to be removed from an automoderator list and it is not found
class AutomodRemovalNotFound(Exception):
    pass


# USED IN: praw_operations.py attempt_to_request_post()
# When neither a post or comment with the provided ID can be found
class NoPostOrCommentFound(Exception):
    pass


# USED IN: discord_bot.py is_filter_name_valid() (used by various commands)
# When a provided filter name for a command does not match any filter
class InvalidFilterName(Exception):
    pass
