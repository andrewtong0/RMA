import re
import constants
import datetime
import db_collection_operations


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
        filter_type = content_filter["type"]
        # If content is coming from Reddit
        if content_filter["platform"] == constants.Platforms.REDDIT.value:
            # If filter is of user filter type and user is in matches, add match
            if filter_type == constants.RedditFilterTypes.USERS.value and post["author"]["username"] in content_filter["matches"]:
                matches_for_post = add_matched_filter(matches_for_post, content_filter, post["author"]["username"])
            # If filter is of post type

            elif filter_type == constants.RedditFilterTypes.POSTS.value:
                # Check post against all regex phrases
                for regex_phrase in content_filter["matches"]:
                    # Submissions also have titles, so we should check the title in addition to the content of the post
                    if post["post_type"] == constants.PostTypes.REDDIT_SUBMISSION.value:
                        if re.search(regex_phrase, post["title"]):
                            matches_for_post = add_matched_filter(matches_for_post, content_filter, regex_phrase)
                    if re.search(regex_phrase, post["content"]):
                        matches_for_post = add_matched_filter(matches_for_post, content_filter, regex_phrase)

            elif filter_type == constants.RedditFilterTypes.MEDIA_SOURCE.value:
                if is_media_source_submission_in_filter(post, content_filter):
                    # TODO: Refactor the flagged_content and make it more abstract to instead say the title of the channel rather than the link as the flagged match
                    matches_for_post = add_matched_filter(matches_for_post, content_filter, post["extra_info"]["media_source"])

            # Media source history filters have objects in their matches array that also store historical (date) data
            #   therefore, must be treated differently
            elif filter_type == constants.RedditFilterTypes.MEDIA_SOURCE_HISTORY.value:
                parent_filter = get_parent_filter(filters, content_filter["parent"])
                # Check if the post is a match for a parent filter (e.g. from a verified channel)
                if parent_filter and is_media_source_submission_in_filter(post, parent_filter):
                    found_matches = []
                    media_title = post["extra_info"]["media_title"]
                    found_match = get_history_media_title_match(media_title, content_filter["matches"])
                    # If the media has been posted before
                    if found_match:
                        match_object = compare_media_to_cooldown(found_match, post, content_filter["action"]["cooldown"])
                        # If the post violates the cooldown
                        if match_object["violates_cooldown"]:
                            found_matches.append(match_object)
                            updated_matches = update_history_media_title_by_title(media_title, content_filter["matches"], post)
                            db_collection_operations.update_media_source_history_matches(content_filter["name"], updated_matches)
                    # If the media is a match for the parent but hasn't been posted, add it to the filter
                    else:
                        match_to_add = {"match": media_title, "date_added": datetime.datetime.fromtimestamp(post["created_time"]["utc"])}
                        db_collection_operations.attempt_add_or_remove_match(
                            content_filter["name"], match_to_add, constants.RedditOperationTypes.ADD.value
                        )
                        # Since the filter values don't update until the next poll for posts, we artificially
                        #   update it here so subsequent posts in the same batch will check with the latest values
                        content_filter["matches"].append(match_to_add)

                    if len(found_matches) > 0:
                        # If we had multiple matches, get only the newest one
                        most_recent_match = get_newest_match(found_matches)
                        match_string = cooldown_media_content_string(most_recent_match)
                        matches_for_post = add_matched_filter(matches_for_post, content_filter, match_string)
            # TODO: Implement this once subreddit is stored or we figure out how to do subreddit blacklist
            # elif post_filter.type == constants.RedditFilterTypes.SUBREDDITS.value and post.subreddit in post_filter.matches:
    return matches_for_post


def get_history_media_title_match(media_title, filter_matches):
    for match in filter_matches:
        if match["match"] == media_title:
            return match
    return None


def update_history_media_title_by_title(media_title, filter_matches, post):
    for match in filter_matches:
        if match["match"] == media_title:
            match["date_added"] = datetime.datetime.fromtimestamp(post["created_time"]["utc"])
    return filter_matches


def is_media_source_submission_in_filter(post, content_filter):
    return post["post_type"] == constants.PostTypes.REDDIT_SUBMISSION.value and post["extra_info"]["media_source"] in content_filter["matches"]


def cooldown_media_content_string(cooldown_object):
    time_since_last = (cooldown_object["current_post_date"] - cooldown_object["previous_post_date"])
    date_comparison_string = "\nDate Last Posted: {}\nDate of New Post: {}\nTime Delta: {}".format(
        cooldown_object["previous_post_date"], cooldown_object["current_post_date"], time_since_last
    )
    return date_comparison_string


# Given an array of match objects with timestamps, return the most recent one
def get_newest_match(match_objects):
    newest_object = {"previous_post_date": datetime.datetime(1, 1, 1)}
    for match_object in match_objects:
        match_date = match_object["previous_post_date"]
        if match_date > newest_object["previous_post_date"]:
            newest_object = match_object
    return newest_object


# Return object with the match, date last posted, current post date, and a boolean describing whether the cooldown was violated
# Cooldown is represented in minutes
def compare_media_to_cooldown(match, post, cooldown):
    match_date = match["date_added"]
    current_date = datetime.datetime.fromtimestamp(post["created_time"]["utc"])
    minutes_since_post = (current_date - match_date).seconds / 60
    return {
        "match": match["match"],
        "previous_post_date": match_date,
        "current_post_date": current_date,
        "violates_cooldown": minutes_since_post < cooldown
    }


def get_parent_filter(filters, parent_filter_name):
    for content_filter in filters:
        if content_filter["name"] == parent_filter_name:
            return content_filter
    return None


def add_matched_filter(current_matches, new_match_filter, new_match_content):
    current_matches.append({
        "filter": new_match_filter,
        "flagged_content": new_match_content,
        "action": new_match_filter["action"]
    })
    return current_matches


# Apply all filters across acquired content
def apply_all_filters(filters, content, content_type):
    matches_for_content = []
    # If content is Reddit specific, call the Reddit specific filtering process
    if content_type == constants.Platforms.REDDIT.value:
        matches_for_content = _filter_reddit(filters, content)
    return matches_for_content
