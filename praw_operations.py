import praw
from pymongo import MongoClient
from datetime import datetime
import constants
import environment_variables


# This file provides two public functions, get_and_store_posts and get_and_store_unstored to query for new posts with
# PRAW. All PRAW (Reddit) related operations are isolated to this file.


# PRAW setup
reddit = praw.Reddit(client_id=str(environment_variables.REDDIT_CLIENT_ID),
                     client_secret=str(environment_variables.REDDIT_CLIENT_SECRET),
                     user_agent=str(environment_variables.REDDIT_USER_AGENT))
reddit.read_only = True


# Database setup
client = MongoClient(environment_variables.DATABASE_URI)
db = client.reddit


# Gets the raw PRAW generator, and returns a list of submissions or comments
def _get_posts(num_posts, posts_type, subreddit_name):
    subreddit = reddit.subreddit(subreddit_name)
    if posts_type == constants.DbEntry.REDDIT_SUBMISSION:
        return list(subreddit.new(limit=num_posts))
    elif posts_type == constants.DbEntry.REDDIT_COMMENT:
        return list(subreddit.comments(limit=num_posts))


# Constructs an entry object from a post
def _construct_entry_object(subreddit_name, post, post_type):
    utc = post.created_utc
    timestamp = datetime.utcfromtimestamp(utc).strftime('%Y-%m-%d %H:%M:%S')
    permalink_domain = "https://reddit.com"
    content = ""
    if post.author:
        if post_type == constants.DbEntry.REDDIT_SUBMISSION:
            if post.selftext:
                content = post.selftext
            else:
                # content = post.preview["images"][0]["source"]["url"] / Check if the preview is actually a mirror and if so then have to switch between this and the url
                content = post.url

            submission_entry = {
                "_id": post.id,
                "subreddit": subreddit_name,
                "post_type": post_type.value,
                "title": post.title,
                "author": {
                    "username": post.author.name,
                    "uuid": post.author.id,
                    "author_icon": post.author.icon_img,
                    "comment_karma": post.author.comment_karma,
                    "post_karma": post.author.link_karma
                },
                "created_time": {
                    "timestamp": timestamp,
                    "utc": utc
                },
                "content": content,
                "permalink": permalink_domain + post.permalink,
                # TODO: Check if content will always be more important than this - if you have image post w/ text, will content = the text and thumbnail = the image?
                "thumbnail": post.thumbnail
            }
            return submission_entry
        elif post_type == constants.DbEntry.REDDIT_COMMENT:
            # Substring is taken since IDs are prefixed with t3_ or t1_ depending on depth, but is irrelevant to us
            # and makes queries harder
            submission_id = post.link_id[3:]
            comment_parent_id = post.parent_id[3:]
            # Check if the comment is a top level comment
            if submission_id == comment_parent_id:
                # If comment is top level, signify with --- for quick reading
                comment_parent_id = "---"
            submission_entry = {
                "_id": post.id,
                "subreddit": subreddit_name,
                "post_type": post_type.value,
                "author": {
                    "username": post.author.name,
                    "uuid": post.author.id,
                    "author_icon": post.author.icon_img,
                    "comment_karma": post.author.comment_karma,
                    "post_karma": post.author.link_karma
                },
                "created_time": {
                    "timestamp": timestamp,
                    "utc": utc
                },
                "content": post.body,
                "permalink": permalink_domain + post.permalink,
                "submission_id": submission_id,
                "comment_parent_id": comment_parent_id
            }
            return submission_entry
    else:
        return None


# Attempts to store each entry object in database with helper function, returns a list of all successfully stored posts
def _store_entry_objects(entry_objects, posts_type):
    posts_stored = []
    for entry_object in entry_objects:
        if not _is_post_in_db(entry_object, posts_type):
            _store_entry_object_helper(entry_object, posts_type)
            posts_stored.append(entry_object)
    return posts_stored


# Stores a single entry object into the database
def _store_entry_object_helper(entry_object, post_type):
    if post_type == constants.DbEntry.REDDIT_SUBMISSION:
        db.submissions.insert_one(entry_object)
    elif post_type == constants.DbEntry.REDDIT_COMMENT:
        db.comments.insert_one(entry_object)


# Check if post is already in database, return true if it is, false if not
def _is_post_in_db(entry_object, post_type):
    id_object = {"_id": entry_object["_id"]}
    queried_post = db.submissions.find_one(id_object) if post_type == constants.DbEntry.REDDIT_SUBMISSION else db.comments.find_one(id_object)
    if post_type == constants.DbEntry.REDDIT_SUBMISSION and queried_post is None:
        return False
    elif post_type == constants.DbEntry.REDDIT_COMMENT and queried_post is None:
        return False
    return True


# Gets the number of specified posts, constructs entry objects, and stores new posts in the database
def get_and_store_posts(num_posts, post_type, subreddit_name):
    posts = _get_posts(num_posts, post_type, subreddit_name)
    entry_objects = [_construct_entry_object(subreddit_name, post, post_type) for post in posts]
    entry_objects = remove_invalid_posts(entry_objects)
    new_posts = _store_entry_objects(entry_objects, post_type)
    print("Posts retrieved")
    return new_posts


# Will repeatedly get posts on each iteration increasing by post_chunk_size until a post was already stored
def get_and_store_unstored(post_chunk_size, post_type, subreddit_name):
    num_queries = 1
    new_posts = []
    while True:
        posts = _get_posts(post_chunk_size * num_queries, post_type, subreddit_name)
        entry_objects = [_construct_entry_object(subreddit_name, post, post_type) for post in posts[(post_chunk_size * -1):]]
        entry_objects = remove_invalid_posts(entry_objects)
        sorted_entry_objects = sort_by_created_time(entry_objects, False)
        were_all_already_stored = _is_post_in_db(sorted_entry_objects[-1], post_type)
        if were_all_already_stored:
            break
        new_posts = _store_entry_objects(entry_objects, post_type)
        print("Query " + str(num_queries) + "...")
        num_queries += 1
    print("Querying complete")
    return new_posts


def remove_invalid_posts(post_entry_objects):
    output_list = []
    for post_entry_object in post_entry_objects:
        if post_entry_object is not None:
            output_list.append(post_entry_object)
    return output_list


# Takes in list of posts and sorts by date, sort order is determined by is_reversed
def sort_by_created_time(post_list, is_reversed):
    output_list = sorted(post_list, key=lambda post: post["created_time"]["utc"], reverse=is_reversed)
    return output_list


def get_redditor(username):
    return reddit.redditor(username)


def determine_priority_action(post_and_matches):
    priority_action = ""
    matches = post_and_matches["matches"]
    for match in matches:
        match_action = match["action"]
        if match_action == constants.FilterActions.REMOVE.value:
            priority_action = constants.RedditFilterActions.SHADOWBAN.value
        elif match_action == constants.FilterActions.MONITOR.value and priority_action != constants.RedditFilterActions.SHADOWBAN.value:
            priority_action = constants.RedditFilterActions.WATCHLIST.value
    return priority_action
