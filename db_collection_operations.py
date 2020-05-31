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
    # TODO: attempt_add_or_remove_user_tag currently returns non-null/null - refactor to leveerage or potentially remove those returns on attempt_add_or_remove_user_tag
    if queried_filter is not None and queried_filter["type"] == constants.RedditFilterTypes.USERS.value:
        attempt_add_or_remove_user_tag(new_match, filter_name, operation_type)

    # If adding match, push value, otherwise, pull out value
    if operation_type == constants.RedditFilterOperationTypes.ADD.value and new_match not in queried_matches:
        return db.filters.find_one_and_update(filter_name_object, {"$push": {"matches": new_match}})
    elif operation_type == constants.RedditFilterOperationTypes.REMOVE.value and new_match in queried_matches:
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
        operation_type = constants.RedditFilterOperationTypes.ERROR.value
    return _add_or_remove_user_tag(username, role_tag, operation_type)


# Adds ore removes tag on user
def _add_or_remove_user_tag(username, role_tag, operation_type):
    user_tags = _get_user_tags(username)
    if operation_type == constants.RedditFilterOperationTypes.ADD.value and role_tag not in user_tags:
        db.users.update({"username": username}, {"$push": {"tags": role_tag}})
    elif operation_type == constants.RedditFilterOperationTypes.REMOVE.value and role_tag in user_tags:
        db.users.update({"username": username}, {"$pull": {"tags": role_tag}})
    # This is hit in error case (RedditFilterOperationTypes.ERROR)
    else:
        return None


# Gets list of user tags
def _get_user_tags(username):
    user = db.users.find_one({"username": username})
    return user["tags"] if user else []


# Adds a user comment by upserting user (to ensure they exist) and adding comment
def add_user_comment(context, username, comment):
    user_status = add_or_update_user(username)
    if user_status == constants.RedditUserUpsertStatus.SUCCESS.value:
        initiating_message = context.message
        comment_object = {
            "comment": comment,
            "timestamp": initiating_message.created_at,
            "author": {
                "uuid": initiating_message.author.id,
                "name": initiating_message.author.name
            }
        }
        return db.users.find_one_and_update({"username": username}, {"$push": {"mod_comments": comment_object}})
    else:
        return None
