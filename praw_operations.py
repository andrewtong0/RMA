import re
import asyncpraw as praw
import asyncprawcore.exceptions
from pymongo import MongoClient
from datetime import datetime
import constants
import environment_variables
import user_preferences
import exceptions
import wrangler

# This file provides two public functions, get_and_store_posts and get_and_store_unstored to query for new posts with
# PRAW. All PRAW (Reddit) related operations are isolated to this file.


# PRAW setup
reddit = praw.Reddit(client_id=environment_variables.REDDIT_CLIENT_ID,
                     client_secret=environment_variables.REDDIT_CLIENT_SECRET,
                     user_agent=environment_variables.REDDIT_USER_AGENT,
                     username=environment_variables.REDDIT_USER_USERNAME,
                     password=environment_variables.REDDIT_USER_PASSWORD,
                     redirect_uri="http://localhost:8080")
print("PRAW Logged in successfully")
reddit.read_only = False

# Database setup
client = MongoClient(environment_variables.DATABASE_URI)
db = client.reddit


# It is safe to check if name starts with t3, it is a submission, and t1 are comments
def is_post_submission(post):
    raw_name = post.name
    tag = raw_name[:2]
    return tag == "t3"


# Gets the raw PRAW generator, and returns a list of submissions or comments
async def _get_posts(num_posts, posts_type, subreddit_name):
    subreddit = await reddit.subreddit(subreddit_name)
    if posts_type == constants.PostTypes.REDDIT_SUBMISSION:
        return await _convert_listing_generator_to_list(subreddit.new(limit=num_posts))
    elif posts_type == constants.PostTypes.REDDIT_COMMENT:
        return await _convert_listing_generator_to_list(subreddit.comments(limit=num_posts))


def create_invalid_author(author):
    author.name = "[DELETED]" + author.name
    return author


async def _convert_listing_generator_to_list(generator):
    output_list = []
    async for item in generator:
        output_list.append(item)
    return output_list


def convert_created_utc_to_ts(utc):
    return datetime.utcfromtimestamp(utc).strftime('%Y-%m-%d %H:%M:%S')


# Constructs an entry object from a post
async def construct_entry_object(subreddit_name, post, post_type):
    utc = post.created_utc
    timestamp = convert_created_utc_to_ts(utc)
    content = ""
    if post.author is not None:
        author = post.author
        if not hasattr(author, 'id'):
            author.id = 'NO_ID'
            author.icon_img = ''
            author.comment_karma = 0
            author.link_karma = 0
        try:
            await author.load()
        except asyncprawcore.exceptions.NotFound:
            author = create_invalid_author(author)
        if post_type == constants.PostTypes.REDDIT_SUBMISSION:
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
                    "username": author.name,
                    "uuid": author.id,
                    "author_icon": author.icon_img,
                    "comment_karma": author.comment_karma,
                    "post_karma": author.link_karma
                },
                "created_time": {
                    "timestamp": timestamp,
                    "utc": utc
                },
                "content": content,
                "permalink": wrangler.generated_reddit_permalink(post.permalink),
                # TODO: Check if content will always be more important than this - if you have image post w/ text, will content = the text and thumbnail = the image?
                "thumbnail": post.thumbnail,
                "extra_info": {
                    "initial_flair": post.link_flair_text,
                    # TODO: Fix this and refactor so it doesn't only leverage off of the author_url
                    "media_title": post.media["oembed"][
                        "title"] if post.media and "oembed" in post.media.keys() and "title" in post.media[
                        "oembed"].keys() else None,
                    "media_source": post.media["oembed"][
                        "author_url"] if post.media and "oembed" in post.media.keys() and "author_url" in post.media[
                        "oembed"].keys() else None
                }
            }
            return submission_entry
        elif post_type == constants.PostTypes.REDDIT_COMMENT:
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
                    "username": author.name,
                    "uuid": author.id,
                    "author_icon": author.icon_img,
                    "comment_karma": author.comment_karma,
                    "post_karma": author.link_karma
                },
                "created_time": {
                    "timestamp": timestamp,
                    "utc": utc
                },
                "content": post.body,
                "permalink": wrangler.generated_reddit_permalink(post.permalink),
                "submission_id": submission_id,
                "comment_parent_id": comment_parent_id
            }
            return submission_entry
    else:
        return None


# Attempts to store each entry object in database with helper function, returns a list of all successfully stored posts
def store_entry_objects(entry_objects, posts_type):
    posts_stored = []
    for entry_object in entry_objects:
        if not _is_post_in_db(entry_object, posts_type):
            _store_entry_object_helper(entry_object, posts_type)
            posts_stored.append(entry_object)
    return posts_stored


# Stores a single entry object into the database
def _store_entry_object_helper(entry_object, post_type):
    if post_type == constants.PostTypes.REDDIT_SUBMISSION:
        db.submissions.insert_one(entry_object)
    elif post_type == constants.PostTypes.REDDIT_COMMENT:
        db.comments.insert_one(entry_object)


# Check if post is already in database, return true if it is, false if not
def _is_post_in_db(entry_object, post_type, ignore_buffer_items=None):
    if ignore_buffer_items is None:
        ignore_buffer_items = []
    post_id = entry_object["_id"]
    # Check if the post ID is in the buffer of IDs to ignore
    if post_id not in ignore_buffer_items:
        id_object = {"_id": post_id}
        queried_post = db.submissions.find_one(
            id_object) if post_type == constants.PostTypes.REDDIT_SUBMISSION else db.comments.find_one(id_object)
        if post_type == constants.PostTypes.REDDIT_SUBMISSION and queried_post is None:
            return False
        elif post_type == constants.PostTypes.REDDIT_COMMENT and queried_post is None:
            return False
        return True
    else:
        return False


# Gets the number of specified posts, constructs entry objects, and stores new posts in the database
async def get_and_store_posts(num_posts, post_type, subreddit_name):
    posts = await _get_posts(num_posts, post_type, subreddit_name)
    entry_objects = [await construct_entry_object(subreddit_name, post, post_type) for post in posts]
    entry_objects = remove_invalid_posts(entry_objects)
    new_posts = store_entry_objects(entry_objects, post_type)
    print("Posts retrieved")
    return new_posts


# Will repeatedly get posts on each iteration increasing by post_chunk_size until a post was already stored
async def get_and_store_unstored(post_chunk_size, post_type, subreddit_name, ignore_buffer_items):
    num_queries = 1
    new_posts = []
    while True:
        posts = await _get_posts(post_chunk_size * num_queries, post_type, subreddit_name)
        entry_objects = [await construct_entry_object(subreddit_name, post, post_type) for post in
                         posts[(post_chunk_size * -1):]]
        entry_objects = remove_invalid_posts(entry_objects)
        sorted_entry_objects = sort_by_created_time(entry_objects, False)
        are_all_posts_stored = True
        for entry_object in sorted_entry_objects:
            if not _is_post_in_db(entry_object, post_type, ignore_buffer_items):
                are_all_posts_stored = False
        if are_all_posts_stored:
            break
        new_posts = store_entry_objects(entry_objects, post_type)
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


async def get_redditor(username):
    return await reddit.redditor(username)


# Determines the highest priority of action to be taken
def determine_priority_action(post_and_matches):
    # Default at 0, all actions are > 0
    priority_action = 0
    action_dictionary = constants.ActionPriorityDictionary
    matches = post_and_matches["matches"]
    for match in matches:
        match_action = match["action"]
        if type(match_action) == dict:
            match_action = match_action["action"]
        if match_action in action_dictionary.keys():
            current_action = action_dictionary[match_action]
            if current_action > priority_action:
                priority_action = current_action
    final_action = action_dictionary[str(priority_action)]
    return final_action


async def request_post(post_id, post_type):
    if post_type == constants.PostTypes.REDDIT_SUBMISSION.value:
        return await reddit.submission(id=post_id)
    elif post_type == constants.PostTypes.REDDIT_COMMENT.value:
        return await reddit.comment(post_id)


# TODO: Find a better way to check if a post/comment ID is invalid
# When it is unknown whether the provided ID is a post or comment, return whatever is found
async def attempt_to_request_post(post_id):
    try:
        submission_attempt = await reddit.submission(id=post_id)
        # Dummy variable to test if accessing comments throws an exception, which it does if the post ID is invalid
        comments = submission_attempt.comments
        return {"post": submission_attempt, "type": constants.PostTypes.REDDIT_SUBMISSION}
    except:
        try:
            comment_attempt = await reddit.comment(id=post_id)
            return {"post": comment_attempt, "type": constants.PostTypes.REDDIT_COMMENT}
        except:
            raise exceptions.NoPostOrCommentFound


async def request_sorted_comments(submission):
    # Raw list of all comments (recursed through comment trees)
    submission_comments = await submission.comments()
    await submission_comments.replace_more(limit=None)
    comments = await _convert_listing_generator_to_list(submission_comments)

    # Sort comments based on karma (lowest values first)
    sorted_comments = sorted(comments, key=lambda comment: comment.score, reverse=False)

    # Remove comments that have been deleted (i.e. no author)
    tidied_list = [comment for comment in sorted_comments if comment.author and comment.author.name]
    return tidied_list


async def _get_automoderator_wikipage(subreddit_name):
    subreddit = await reddit.subreddit(subreddit_name)
    async for wikipage in subreddit.wiki:
        if wikipage.name == "config/automoderator":
            return await subreddit.wiki.get_page("config/automoderator")
    return constants.RedditAutomodEditStatus.FAIL.value


async def update_automoderator_page(synced_filter, new_match, action):
    if environment_variables.HAS_MOD:
        filter_name = synced_filter["filter_name"]

        automod_wikipage = await _get_automoderator_wikipage(environment_variables.PRIORITY_SUBREDDIT)
        automod_filters = automod_wikipage.content_md.split(user_preferences.FilterSeparator)
        queried_filter_and_index = get_automoderator_filter(automod_filters, filter_name)
        if queried_filter_and_index is not None:
            try:
                updated_filter = update_automoderator_filter_matches(
                    queried_filter_and_index["filter"],
                    new_match,
                    action
                )
                automod_filters[queried_filter_and_index["index"]] = updated_filter
                updated_automod_filters = user_preferences.FilterSeparator.join(automod_filters)
                await automod_wikipage.edit(content=updated_automod_filters, reason=synced_filter["filter_log_reason"])
                return constants.RedditAutomodEditStatus.SUCCESS.value
            except exceptions.AutomodRemovalNotFound:
                return constants.RedditAutomodEditStatus.FAIL.value
    return constants.RedditAutomodEditStatus.MISSING_PRIVILEGES.value


def get_automoderator_filter(automod_filters, filter_name):
    for index, automod_filter in enumerate(automod_filters, 0):
        if filter_name.lower() in automod_filter.lower():
            return {"filter": automod_filter, "index": index}
    return None


# TODO: Refactor to generalize and get matches, even if form is not in an array with brackets []
# Returns updated filter with new matches
def update_automoderator_filter_matches(automod_filter, new_match, action):
    # Find list of matches (e.g. list of names for shadowbans) between brackets
    matches = re.search(r"\[(.*)\]", automod_filter).group(1)
    if action == constants.RedditOperationTypes.ADD.value:
        matches += ", {}".format(new_match)
    elif action == constants.RedditOperationTypes.REMOVE.value:
        search_string = r"\,?\s*" + re.escape(new_match)
        search_result = re.search(search_string, matches)

        partitioned_matches = matches.partition(search_result.group())
        if partitioned_matches[1] != "":
            prefix = partitioned_matches[0]
            suffix = partitioned_matches[2]
            matches = prefix + suffix

            # If we are removing the first entry in the list, ensure there is no extra comma at the beginning
            if matches[0] == ",":
                matches = matches[1:].lstrip()
        else:
            raise exceptions.AutomodRemovalNotFound
    # Re-add brackets since they are removed via search
    matches = "[{}]".format(matches)

    new_filter = re.sub(r"\[(.*)\]", matches, automod_filter)
    return new_filter


async def action_on_post(post_id, action, post_type):
    post_instance = await request_post(post_id, post_type)
    if action == constants.RedditOperationTypes.APPROVE.value:
        await post_instance.mod.approve()
    elif action == constants.RedditOperationTypes.REMOVE.value:
        await post_instance.mod.remove()
    elif action == constants.RedditOperationTypes.LOCK.value:
        await post_instance.mod.lock()
    elif action == constants.RedditOperationTypes.UNLOCK.value:
        await post_instance.mod.unlock()


async def scan_user_history(post):
    username = post["author"]["username"]
    redditor = await reddit.redditor(username)
    await redditor.load()
    submissions = redditor.new()
    async for submission in submissions:
        post_subreddit = submission.subreddit.display_name
        for subreddit in user_preferences.BlacklistedSubreddits:
            if post_subreddit.lower() == subreddit.lower():
                post_object = {
                    "_id": submission.id,
                    "infracting_subreddit": subreddit,
                    "username": submission.author.name,
                    "permalink": wrangler.generated_reddit_permalink(submission.permalink)
                }
                return post_object
    return {}


async def iterate_through_reports(gen):
    output = []
    async for item in gen:
        output.append(item)
    return output


# Fetch reported posts by post type
async def fetch_reported_posts(subreddit_moderation, post_type):
    reported_content = []
    post_type_param = "submissions" if post_type == constants.PostTypes.REDDIT_SUBMISSION.value else "comments"
    reports_generator = subreddit_moderation.reports(only=post_type_param)
    async for report in reports_generator:
        reported_content.append(report)
    return reported_content


async def fetch_latest_reports(subreddit_name):
    subreddit = await reddit.subreddit(subreddit_name)
    subreddit_moderation = subreddit.mod
    comment_reports = await fetch_reported_posts(
        subreddit_moderation, constants.PostTypes.REDDIT_COMMENT.value)
    submission_reports = await fetch_reported_posts(
        subreddit_moderation, constants.PostTypes.REDDIT_SUBMISSION.value)

    cleaned_reported_comments = await _clean_reported_content(
        comment_reports, constants.PostTypes.REDDIT_COMMENT.value)
    cleaned_reported_submissions = await _clean_reported_content(
        submission_reports, constants.PostTypes.REDDIT_SUBMISSION.value)

    return {
        "comments": cleaned_reported_comments,
        "submissions": cleaned_reported_submissions,
    }


async def _clean_reported_content(reported_content, post_type):
    cleaned_posts = []
    for content in reported_content:
        try:
            if post_type == constants.PostTypes.REDDIT_SUBMISSION.value:
                cleaned_posts.append(_clean_reported_submission(content))
            elif post_type == constants.PostTypes.REDDIT_COMMENT.value:
                cleaned_posts.append(_clean_reported_comment(content))
            else:
                print("No matching post type for reported content")
        except:
            print("Error processing reported content")
    return cleaned_posts


def _clean_reported_submission(reported_submission):
    return {
        "post_type": constants.PostTypes.REDDIT_SUBMISSION.value,
        "author": reported_submission.author,
        "created_utc": reported_submission.created_utc,
        "post_id": reported_submission.id,
        "name": reported_submission.name,
        "permalink": wrangler.generated_reddit_permalink(reported_submission.permalink),
        "score": reported_submission.score,
        "selftext": reported_submission.selftext,
        "subreddit": reported_submission.subreddit.display_name,
        "title": reported_submission.title,
        "mod_reports": reported_submission.mod_reports,
        "user_reports": reported_submission.user_reports,
    }


def _clean_reported_comment(reported_comment):
    return {
        "post_type": constants.PostTypes.REDDIT_COMMENT.value,
        "author": reported_comment.author,
        "body": reported_comment.body,
        "created_utc": reported_comment.created_utc,
        "post_id": reported_comment.id,
        "is_submitter": reported_comment.is_submitter,
        "link_id": reported_comment.link_id,
        "parent_id": reported_comment.parent_id,
        "permalink": wrangler.generated_reddit_permalink(reported_comment.permalink),
        "score": reported_comment.score,
        "subreddit": reported_comment.subreddit.display_name,
        "mod_reports": reported_comment.mod_reports,
        "user_reports": reported_comment.user_reports,
    }
