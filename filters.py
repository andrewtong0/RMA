import re
import constants


# Apply all filters across all Reddit content
# TODO: Consider concat instead of "matches_for_posts =" in case we want to run against multiple platforms?
def _filter_reddit(filters, content):
    matches_for_posts = _find_reddit_matches_for_posts(filters, content)
    return matches_for_posts


# Given a filter, check every new post against it
def _find_reddit_matches_for_posts(filters, posts):
    matches_for_posts = []
    for post in posts:
        matches_for_post = _find_reddit_matches_for_post(filters, post)
        matches_for_posts.append({
            "post": post,
            "matches": matches_for_post
        })
    return matches_for_posts


# Given a post and a filter, check if it matches against any filters
def _find_reddit_matches_for_post(filters, post):
    # Stores list of triggered filters and the content caught by the filters
    matches_for_post = []

    for content_filter in filters:
        if content_filter["platform"] == constants.Platforms.REDDIT.value:
            # If filter is of user filter type and user is in matches, add match
            if content_filter["type"] == constants.RedditFilterTypes.USERS.value and post["author"]["username"] in content_filter["matches"]:
                matches_for_post.append({"filter": content_filter, "flagged_content": post["author"]["username"], "action": content_filter["action"]})
            elif content_filter["type"] == constants.RedditFilterTypes.POSTS.value:
                for regex_phrase in content_filter["matches"]:
                    # Submissions also have titles, so we should check the title in addition to the content of the post
                    if post["post_type"] == constants.DbEntry.REDDIT_SUBMISSION.value:
                        if re.match(regex_phrase, post["title"]):
                            matches_for_post.append({"filter": content_filter, "flagged_content": regex_phrase,
                                                     "action": content_filter["action"]})
                    if re.match(regex_phrase, post["content"]):
                        matches_for_post.append({"filter": content_filter, "flagged_content": regex_phrase,
                                                 "action": content_filter["action"]})
            elif content_filter["type"] == constants.RedditFilterTypes.MEDIA_SOURCE.value:
                if post["post_type"] == constants.DbEntry.REDDIT_SUBMISSION.value and post["extra_info"]["media_source"] in content_filter["matches"]:
                    # TODO: Refactor the flagged_content and make it more abstract to instead say the title of the channel rather than the link as the flagged match
                    matches_for_post.append({"filter": content_filter,
                                             "flagged_content": post["extra_info"]["media_source"],
                                            "action": content_filter["action"]})
            # TODO: Implement this once subreddit is stored or we figure out how to do subreddit blacklist
            # elif post_filter.type == constants.RedditFilterTypes.SUBREDDITS.value and post.subreddit in post_filter.matches:
    return matches_for_post


# Apply all filters across acquired content
def apply_all_filters(filters, content, content_type):
    matches_for_content = []
    # If content is Reddit specific, call the Reddit specific filtering process
    if content_type == constants.Platforms.REDDIT.value:
        matches_for_content = _filter_reddit(filters, content)
    return matches_for_content
