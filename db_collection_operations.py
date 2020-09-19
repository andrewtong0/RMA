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
def attempt_add_or_remove_match(filter_name, new_match, operation_type):
    # Find associated filter
    filter_name_object = {"name": filter_name}
    queried_filter = db.filters.find_one(filter_name_object)
    queried_matches = queried_filter["matches"]

    # If filter is user filter, should add/remove user tag (also has duplicate checking)
    # TODO: attempt_add_or_remove_user_tag currently returns non-null/null - refactor to leverage or potentially remove those returns on attempt_add_or_remove_user_tag
    if queried_filter is not None and queried_filter["type"] == constants.RedditFilterTypes.USERS.value:
        attempt_add_or_remove_user_tag(new_match, filter_name, operation_type)

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
def generate_user_comments(username):
    user_status = add_or_update_user(username)
    if user_status == constants.RedditUserUpsertStatus.SUCCESS.value:
        user_data = get_user_data(username)
        embed = wrangler.construct_user_moderator_comments_embed(user_data, username)
        return embed
    else:
        return wrangler.construct_user_not_found_embed(username)


# Generates user report embed based on user posts from username
def generate_user_report(username):
    user_status = add_or_update_user(username)
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
def add_or_update_user(username):
    userdata = praw_operations.get_redditor(username)
    # Shadowbanned and non-existent accounts error out
    # TODO: Try to find exploitable variable rather than using try/catch
    try:
        if len(userdata.__dict__) > 0:
            _add_or_update_user_db(username, userdata)
            return constants.RedditUserUpsertStatus.SUCCESS.value
        else:
            return constants.RedditUserUpsertStatus.MISSING.value
    except:
        return constants.RedditUserUpsertStatus.SUSPENDED.value


# If user already in database, only updates, if not already in database, instantiates empty lists for mod comments
# and tags then updates information.
def _add_or_update_user_db(username, userdata):
    id_object = {"_id": userdata.id}
    if db.users.find_one(id_object) is None:
        db.users.insert_one({
            "_id": userdata.id,
            "username": username,
            "mod_comments": [],
            "tags": []
        })

    db.users.update(id_object, {"$set": {
        "account_creation_utc": userdata.created_utc,
        "icon_img": userdata.icon_img,
        "comment_karma": userdata.comment_karma,
        "link_karma": userdata.link_karma,
    }})


# Attempts to add user tag, returns True on success, false on failure
def attempt_add_or_remove_user_tag(username, role_tag, operation_type):
    user_status = add_or_update_user(username)
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
def add_user_comment(message, username, comment_author, comment):
    user_status = add_or_update_user(username)
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
def remove_user_comment(username, comment_id):
    user_status = add_or_update_user(username)
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
