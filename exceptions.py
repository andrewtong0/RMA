# CUSTOM EXCEPTIONS


# USED IN: praw_operations.py update_automoderator_filter_matches()
# When a name or value is to be removed from an automoderator list and it is not found
class AutomodRemovalNotFound(Exception):
    pass


# USED IN: praw_operations.py attempt_to_request_post()
# When neither a post or comment with the provided ID can be found
class NoPostOrCommentFound(Exception):
    pass
