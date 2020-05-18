import os
import re
from pymongo import MongoClient
import constants

# Database setup
client = MongoClient(str(os.environ.get("DATABASE_URI")))
db = client.reddit
collection = db["filters"]


def get_all_filters():
    filters = collection.find()
    return filters


def get_filter(platform, filter_type, filter_action):
    return db.submissions.find_one({"platform": platform, "type": filter_type, "action": filter_action})


def add_match_to_filter(platform, filter_type, filter_action, new_matches):
    current_filter = get_filter(platform, filter_type, filter_action)
    current_matches = current_filter.matches
    updated_matches = _filter_new_matches(current_matches, new_matches)
    db.filters.update_one({'_id': current_filter["_id"]}, {"matches": updated_matches}, upsert=True)
    # Should also send a message to notify the status of the addition


# If new match(es) are not already in the current list, add them
def _filter_new_matches(current_matches, new_matches):
    filtered_new_matches = []
    if type(new_matches) is list:
        for new_match in new_matches:
            if new_match not in current_matches:
                filtered_new_matches.append(new_match)
    elif type(new_matches) is str:
        filtered_new_matches = current_matches.append(new_matches)
    return filtered_new_matches


# From the filter in the database, remove a match if it exists
def remove_match_from_filter(platform, filter_type, filter_action, match):
    current_filter = get_filter(platform, filter_type, filter_action)
    current_matches = current_filter.matches
    if match in current_matches:
        current_matches.remove(match)
    else:
        print("Fail")
    db.filters.update_one({'_id': current_filter["_id"]}, {"matches": current_matches}, upsert=True)
    # Replace print and add message feedback


# Switch case to handle different filters, returns matching posts with reasons and information for each match
# Posts and their match information are at the same index (e.g. matches[0] has the match info for matched_posts[0])
def _find_reddit_matches(reddit_filter, posts):
    matches = []
    matched_posts = []
    for post in posts:
        if reddit_filter["type"] == constants.FilterTypes.USERS.value:
            if post["author"]["username"] in reddit_filter["matches"]:
                matches.append({"post": post, "reason": reddit_filter["name"], "info": None})
                matched_posts.append(post)
        if reddit_filter["type"] == constants.FilterTypes.SUBREDDITS.value:
            # Import Reddit investigator here and call
            print("To be implemented")
        if reddit_filter["type"] == constants.FilterTypes.POSTS.value:
            infractions = _filter_reddit_regex(reddit_filter, post)
            if infractions:
                matches.append({"post": post, "reason": reddit_filter["name"], "info": infractions})
                matched_posts.append(post)
    matches_and_posts = {"matches": matches, "posts": matched_posts}
    return matches_and_posts


def _filter_reddit_regex(reddit_filter, post):
    infractions = []
    for regex in reddit_filter.matches:
        if re.match(regex, post["content"]):
            infractions.append(regex)
        if post["title"] and re.match(regex, post["title"]):
            infractions.append(regex)
    return infractions


def _action_on_reddit_matches(reddit_filter, matches):
    for post in matches:
        context = ""
        if reddit_filter.action == constants.FilterActions.REMOVE:
            # Remove post and notify users
            # removePost()
            context = "Shadowban"
        elif reddit_filter.action == constants.FilterActions.MONITOR:
            context = "Watchlist"
        # Send notification in discord_bot.py


def filter_reddit(filter_type, filter_action, posts):
    post_filter = get_filter(constants.Platforms.REDDIT, filter_type, filter_action)
    matches = _find_reddit_matches(post_filter, posts)
    _action_on_reddit_matches(post_filter, matches)


def apply_all_filters(filters, posts):
    matches_and_posts = []
    for content_filter in filters:
        if content_filter["platform"] == "reddit":
            matches_and_posts = _find_reddit_matches(content_filter, posts)
    return matches_and_posts
