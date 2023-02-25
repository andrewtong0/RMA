from pymongo import MongoClient
import wrangler
import praw_operations
import constants
import environment_variables

# Database setup
client = MongoClient(environment_variables.DATABASE_URI)
db = client.reddit


# Attempts to add or remove match on filter, returns the newly updated matches if successful
# If the filter is of user type, will also update tags
async def attempt_add_or_remove_match(filter_name, new_match, operation_type):
    # Find associated filter
    filter_name_object = {"name": filter_name}
    queried_filter = db.filters.find_one(filter_name_object)
    queried_matches = queried_filter["matches"]

    # If filter is user filter, should add/remove user tag (also has duplicate checking)
    # TODO: attempt_add_or_remove_user_tag currently returns non-null/null - refactor to leverage or potentially remove those returns on attempt_add_or_remove_user_tag
    if queried_filter is not None and queried_filter["type"] == constants.RedditFilterTypes.USERS.value:
        await attempt_add_or_remove_user_tag(new_match, filter_name, operation_type)

    # If adding match, push value, otherwise, pull out value
    if operation_type == constants.RedditOperationTypes.ADD.value and new_match not in queried_matches:
        return db.filters.find_one_and_update(filter_name_object, {"$push": {"matches": new_match}})
    elif operation_type == constants.RedditOperationTypes.REMOVE.value and new_match in queried_matches:
        return db.filters.find_one_and_update(filter_name_object, {"$pull": {"matches": new_match}})
    else:
        # If there was an issue or if match was not in/already in matches
        return None


def get_collection(collection):
    return db[collection].find()


# Attempts to get matches for a specific filter
def get_matches(filter_name):
    return db.filters.find_one({"name": filter_name})


# Returns user data
def get_user_data(username):
    return db.users.find_one({"username": username})


# Function used to map filters to just their names
def map_filter_names(db_filter):
    return db_filter["name"]


# Attempts to get a list of all the filters and maps to only return the filter names
def get_filters():
    return map(map_filter_names, db.filters.find())


# Generates user comments embed
async def generate_user_comments(username):
    user_status = await add_or_update_user(username)
    if user_status == constants.RedditUserUpsertStatus.SUCCESS.value:
        user_data = get_user_data(username)
        embed = wrangler.construct_user_moderator_comments_embed(user_data, username)
        return embed
    else:
        return wrangler.construct_user_not_found_embed(username)


# Generates user report embed based on user posts from username
async def generate_user_report(username):
    user_status = await add_or_update_user(username)
    if user_status == constants.RedditUserUpsertStatus.SUCCESS.value:
        user_posts = get_user_posts(username)
        user_data = get_user_data(username)
        embed = wrangler.construct_user_report_embed(user_posts, username, user_data)
        return embed
    else:
        return wrangler.construct_user_not_found_embed(username)


# Grabs all posts (submissions + comments) of a user for user report
def get_user_posts(username):
    user_posts = []
    submissions = db.submissions.find({"author.username": username})
    for submission in submissions:
        user_posts.append(submission)
    comments = db.comments.find({"author.username": username})
    for comment in comments:
        user_posts.append(comment)
    user_posts = praw_operations.sort_by_created_time(user_posts, True)
    return user_posts


# Upserts user information to database, runs checks to ensure user exists/not shadowbanned
async def add_or_update_user(username):
    # TODO: Check whether shadowbanned and non-existent accounts error out
    try:
        return await _add_or_update_user_db(username)
    except:
        return constants.RedditUserUpsertStatus.SUSPENDED.value


def _add_new_user_to_db(username, userdata):
    db.users.insert_one({
        "_id": userdata.id,
        "username": username,
        "mod_comments": [],
        "tags": [],
        "reports": [],
    })


# If user already in database, only updates, if not already in database, instantiates empty lists for mod comments
#   and tags then updates information.
async def _add_or_update_user_db(username):
    userdata = await praw_operations.get_redditor(username)
    await userdata.load()
    id_object = {"_id": userdata.id}
    if db.users.find_one(id_object) is None:
        _add_new_user_to_db(username, userdata)

    if hasattr(userdata, 'is_suspended'):
        return constants.RedditUserUpsertStatus.MISSING.value

    db.users.update(id_object, {"$set": {
        "account_creation_utc": userdata.created_utc,
        "icon_img": userdata.icon_img,
        "comment_karma": userdata.comment_karma,
        "link_karma": userdata.link_karma,
    }})

    return constants.RedditUserUpsertStatus.SUCCESS.value


# Attempts to add user tag, returns True on success, false on failure
async def attempt_add_or_remove_user_tag(username, role_tag, operation_type):
    user_status = await add_or_update_user(username)
    if user_status != constants.RedditUserUpsertStatus.SUCCESS.value:
        operation_type = constants.RedditOperationTypes.ERROR.value
    return _add_or_remove_user_tag(username, role_tag, operation_type)


# Adds ore removes tag on user
def _add_or_remove_user_tag(username, role_tag, operation_type):
    user_tags = _get_user_tags(username)
    if operation_type == constants.RedditOperationTypes.ADD.value and role_tag not in user_tags:
        db.users.update({"username": username}, {"$push": {"tags": role_tag}})
    elif operation_type == constants.RedditOperationTypes.REMOVE.value and role_tag in user_tags:
        db.users.update({"username": username}, {"$pull": {"tags": role_tag}})
    # This is hit in error case (RedditOperationTypes.ERROR)
    else:
        return None


# Gets list of user tags
def _get_user_tags(username):
    user = db.users.find_one({"username": username})
    return user["tags"] if user else []


# Adds a user comment by upserting user (to ensure they exist) and adding comment
async def add_user_comment(message, username, comment_author, comment):
    user_status = await add_or_update_user(username)
    if user_status == constants.RedditUserUpsertStatus.SUCCESS.value:
        comment_object = {
            "comment": comment,
            "timestamp": message.created_at,
            "author": {
                "uuid": comment_author.id,
                "name": comment_author.name
            }
        }
        return db.users.find_one_and_update({"username": username}, {"$push": {"mod_comments": comment_object}})
    else:
        return None


# Removes a user comment
async def remove_user_comment(username, comment_id):
    user_status = await add_or_update_user(username)
    comment = get_user_comment(username, int(comment_id))
    if user_status == constants.RedditUserUpsertStatus.SUCCESS.value and comment is not None:
        return db.users.find_one_and_update({"username": username}, {"$pull": {"mod_comments": comment}})
    else:
        return None


# TODO: Deterine if this is worth having since it is unused; cases that use mod comments get full user_data anyway
# Gets moderator comments on a user
def get_user_moderator_comments(username):
    user_data = get_user_data(username)
    if user_data is not None:
        return user_data["mod_comments"]
    else:
        return None


# Gets the user data and returns the comment at provided index
def get_user_comment(username, comment_id):
    mod_comments = get_user_moderator_comments(username)
    if mod_comments is not None:
        return mod_comments[comment_id]
    else:
        return None


def get_post(post_id):
    return db.submissions.find_one({"_id": post_id})


def get_comment(post_id):
    return db.comments.find_one({"_id": post_id})


# Checks if post in database is of submission or comment type
def is_post_submission(post_id):
    post = get_post(post_id)
    # If a post is found, reverify that it is a submission (although this is a double check since we're querying the submissions collection anyways)
    if post is not None:
        return post["post_type"] == constants.PostTypes.REDDIT_SUBMISSION.value
    return False


def add_post_id_to_ignore_buffer(post_id):
    db.metadata.find_one_and_update(
        {"name": constants.DatabaseMetadataInfo.IGNORE_BUFFER_NAME.value},
        {"$push": {"items": post_id}}
    )


def get_ignore_buffer():
    return db.metadata.find_one({"name": constants.DatabaseMetadataInfo.IGNORE_BUFFER_NAME.value})


def clear_ignore_buffer():
    db.metadata.find_one_and_update(
        {"name": constants.DatabaseMetadataInfo.IGNORE_BUFFER_NAME.value},
        {"$set": {"items": []}}
    )


def update_media_source_history_matches(filter_name, updated_matches):
    filter_name_object = {"name": filter_name}
    db.filters.find_one_and_update(filter_name_object, {"$set": {"matches": updated_matches}})


# Checks if post is repost
def get_reposts_of_post(post_id):
    post = get_post(post_id)
    post_title = post["title"]
    post_id = post["_id"]
    if post is not None:
        # Repost Parameters:
        # - Submissions with same name
        # - Do not fetch self
        reposts = db.submissions.find({
            "title": post_title,
            "_id": {"$ne": post_id}
        })
        return list(reposts)
    return []


async def db_operations_on_reported_content(subreddit_name, reported_content):
    latest_comment_timestamp = reported_content["comments"][0]["created_utc"] if len(reported_content["comments"]) > 0 else 0
    latest_submission_timestamp = reported_content["submissions"][0]["created_utc"] if len(reported_content["submissions"]) > 0 else 0
    latest_current_timestamp = max(latest_comment_timestamp, latest_submission_timestamp)
    latest_stored_timestamp = _get_latest_stored_report_timestamp(subreddit_name) or 0
    combined_reported_content = reported_content["comments"] + reported_content["submissions"]

    new_reports = []
    # If we have new reports, log them, and update the latest timestamp
    if latest_stored_timestamp == 0 or latest_stored_timestamp < latest_current_timestamp:
        for report in combined_reported_content:
            # Only log new reports
            if latest_stored_timestamp < report["created_utc"]:
                await _log_reported_content(report)
                new_reports.append(_construct_report(report))
        _update_latest_report_timestamp(subreddit_name, latest_current_timestamp)
    return new_reports


# Checks metadata for latest report timestamp, creates report metadata if nonexistent
def _get_latest_stored_report_timestamp(subreddit_name):
    query = {"name": constants.DatabaseMetadataInfo.REPORT_TIMESTAMPS_NAME.value}
    # Create metadata object if it doesn't exist
    if db.metadata.find_one(query) is None:
        _create_reports_metadata()

    latest_subreddit_reports = db.metadata.find_one(query)["latest_subreddit_reports"]
    stored_latest_timestamp = None
    if subreddit_name in latest_subreddit_reports:
        # If we have a timestamp for a previous report on this subreddit, fetch the timestamp
        stored_latest_timestamp = latest_subreddit_reports[subreddit_name]

    return stored_latest_timestamp


# Creates the default report metadata entry
def _create_reports_metadata():
    db.metadata.insert_one({
        "name": constants.DatabaseMetadataInfo.REPORT_TIMESTAMPS_NAME.value,
        "description": constants.DatabaseMetadataInfo.REPORT_TIMESTAMPS_DESCRIPTION.value,
        "latest_subreddit_reports": {},
    })


# Update the store timestamp to a newer timestamp
def _update_latest_report_timestamp(subreddit_name, curr_latest_timestamp):
    reports_metadata_query = {"name": constants.DatabaseMetadataInfo.REPORT_TIMESTAMPS_NAME.value}
    report_timestamps = db.metadata.find_one(reports_metadata_query)
    updated_timestamps = report_timestamps["latest_subreddit_reports"]
    updated_timestamps[subreddit_name] = curr_latest_timestamp
    db.metadata.find_one_and_update(
        reports_metadata_query, {"$set": {"latest_subreddit_reports": updated_timestamps}})


async def _log_reported_content(content):
    # Ensure user exists in database before attempting to add report
    await _add_or_update_user_db(content["author"].name)

    # Log the report to the user and to the post, the report date, and permalink to reported content
    await _add_and_update_user_reports(content)


# Add user report to user
# Note: If changing schema here, also change in _add_or_update_user_db()
async def _add_and_update_user_reports(content):
    username = content["author"].name
    userdata = await praw_operations.get_redditor(username)
    await userdata.load()
    id_object = {"_id": userdata.id}

    # Insert user if they are not already in the database
    if db.users.find_one(id_object) is None:
        _add_new_user_to_db(username, userdata)

    # Create new report object from this report
    report_object = _construct_report(content)
    # We can remove the username since we are associating this report to the user
    report_object.pop('username', None)

    # Fetch user reports, add new report, and update existing reports
    user = db.users.find_one(id_object)
    user_reports = user["reports"] if "reports" in user else {}

    # Check whether this post has been reported before, if so, merge report counts
    if report_object["post_id"] in user_reports:
        stored_reports_for_post = user_reports[report_object["post_id"]]["reports"]
        stored_reports_for_post.update(report_object["reports"])
        user_reports[report_object["post_id"]]["reports"] = stored_reports_for_post
    else:
        # Otherwise, create new entry in user_reports for given post
        user_reports[report_object["post_id"]] = report_object

    db.users.update(id_object, {"$set": {
        "reports": user_reports
    }})


# Reports contain both the report reasoning/message (0), and the author of the reported content (1)
#   for our use case, we only care about the message
def filter_only_report_content(reports):
    output = []
    for report in reports:
        output.append(report[0])
    return output


def count_reports(reports):
    report_counts = {}
    for report in reports:
        if report in report_counts:
            report_counts[report] = report_counts[report] + 1
        else:
            report_counts[report] = 1
    return report_counts


# Construct user reports object
def _construct_report(content):
    report_counts = count_reports(
        filter_only_report_content(content["mod_reports"]) + filter_only_report_content(content["user_reports"]))
    return {
        "post_id": content["post_id"],
        "post_type": content["post_type"],
        "username": content["author"].name,
        "content": content["title"] if content["post_type"] == constants.PostTypes.REDDIT_SUBMISSION.value else content["body"],
        "timestamp": praw_operations.convert_created_utc_to_ts(content["created_utc"]),
        "permalink": content["permalink"],
        "reports": report_counts,
    }
