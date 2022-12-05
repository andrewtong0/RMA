import re
import datetime
import prawcore
import discord
import logging
from discord.ext import tasks, commands

# File imports
import constants
import praw_operations
import filters
import wrangler
import user_preferences
import db_collection_operations
import environment_variables
import exceptions

# This file should only be used for Discord bot management

# ================
# FUNCTIONS/CONSTS
# ================


# Used for version command for verification of successful migration
rma_version = "2.3.2"


# Initializes filters on startup by grabbing filters
def set_filters():
    retrieved_filters = db_collection_operations.get_collection("filters")
    output_filters = []
    for f in retrieved_filters:
        output_filters.append(f)
    return output_filters


# Initialize metadata information
def set_metadata():
    retrieved_metadata = db_collection_operations.get_collection("metadata")
    metadata_dict = {}
    for metadata in retrieved_metadata:
        metadata_dict[metadata["name"]] = metadata
    return metadata_dict


# Return roles matching names in roles_to_find
def find_roles(roles, roles_to_find):
    found_roles = []
    for role_to_find in roles_to_find:
        found_role = next(role for role in roles if role_to_find == role.name)
        found_roles.append(found_role)
    return found_roles


def get_roles():
    return client.guilds[0].roles


# ==============
# INITIALIZATION
# ==============


# Single-point editing array depending on DEV_MODE flag
SelectedSubredditsAndChannels = []
if environment_variables.DEV_MODE:
    SelectedSubredditsAndChannels = user_preferences.DevSubredditsAndChannels
else:
    SelectedSubredditsAndChannels = user_preferences.ProdSubredditsAndChannels


print("DISCORD.PY VERSION: {}".format(discord.__version__))

client = commands.Bot(
    intents=discord.Intents.all(),
    command_prefix=user_preferences.Settings.BOT_PREFIX.value
)
db_filters = set_filters()
metadata_dict = set_metadata()

# =====================
# GENERIC BOT FUNCTIONS
# =====================


# Login status + presence flair
@client.event
async def on_ready():
    print('Discord Logged in as', client.user)
    await client.change_presence(activity=discord.Game(name='My prefix is {}'.format(user_preferences.Settings.BOT_PREFIX.value)))
    set_exceptions()
    await send_health_message(constants.BotHealthMessages.POLLING_START.value)
    await poll_new_posts.start()


def set_exceptions():
    poll_new_posts.add_exception_type(StopIteration)
    poll_new_posts.add_exception_type(prawcore.exceptions.NotFound)


def get_channel_from_id(channel_id):
    return client.get_channel(channel_id)


def get_channels_of_type(channel_type, subreddit_and_channels):
    # Set channel based on environment
    channels = []
    if channel_type == constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_ALL.value:
        for channel_id in subreddit_and_channels.main_channel_ids:
            channels.append(get_channel_from_id(channel_id))
    elif channel_type == constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_POSTS.value:
        for channel_id in subreddit_and_channels.post_channel_ids:
            channels.append(get_channel_from_id(channel_id))
    elif channel_type == constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_COMMENTS.value:
        for channel_id in subreddit_and_channels.comment_channel_ids:
            channels.append(get_channel_from_id(channel_id))
    elif channel_type == constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_PINGS.value:
        for channel_id in subreddit_and_channels.ping_channel_ids:
            channels.append(get_channel_from_id(channel_id))
    elif channel_type == constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_SECONDARY_REVIEW.value:
        for channel_id in subreddit_and_channels.secondary_review_channel_ids:
            channels.append(get_channel_from_id(channel_id))
    return channels


# Given a post ID or a URL, extract the ID
def get_post_id(id_or_url):
    is_entry_url = is_url(id_or_url)
    post_id = ""
    if is_entry_url:
        post_id = get_post_id_from_url(id_or_url)
    else:
        post_id = id_or_url
    return post_id


# Determine if the given value is a Reddit URL or an ID
def is_url(id_or_url):
    if constants.RedditUrlConsts.key_string.value in id_or_url:
        return True
    else:
        return False


# If given value is a URL, get either the post or direct comment link ID
def get_post_id_from_url(url):
    removed_domain = url.partition(constants.RedditUrlConsts.key_string.value)[2]
    # If URL ends with a slash, remove it so it doesn't mess up partitioning
    if removed_domain[-1:] == "/":
        removed_domain = removed_domain[:-1]
    split_on_slash = removed_domain.split(constants.RedditUrlConsts.key_string.url_delimiter.value)
    # If there are more than 4 sections, it is a comment link
    if len(split_on_slash) >= 5:
        comment_id_split = split_on_slash[4]
        query_param_indicator = constants.RedditUrlConsts.query_param_indicator.value
        if query_param_indicator in comment_id_split:
            comment_id_split = comment_id_split.split(query_param_indicator)[0]
        return comment_id_split
    # Otherwise it is a post link
    else:
        return split_on_slash[2]


# If the filter should be synced, return the filter, otherwise return None
def should_filter_be_synced(filter_name):
    for synced_filter in user_preferences.SyncedFilters:
        if filter_name.lower() in synced_filter["filter_name"].lower():
            return synced_filter
    return None


# Returns true if given regex ia a valid expression, false otherwise
def is_match_valid_regex(regex):
    try:
        re.compile(regex)
        return True
    except re.error:
        return False


# ===================
# REDDIT POST POLLING
# ===================

# Grabs new posts, stores them in the database
@tasks.loop(minutes=user_preferences.BotConsts.POLL_TIMER.value)
async def poll_new_posts():
    await send_health_message(constants.BotHealthMessages.POLLING_UP.value)
    print(poll_new_posts.next_iteration)
    for subreddit_and_channels in SelectedSubredditsAndChannels:
        await get_new_reddit_posts(10, subreddit_and_channels)


# Handle loop failures by restarting polling
@poll_new_posts.after_loop
async def on_poll_error():
    if poll_new_posts.is_being_cancelled() or poll_new_posts.failed():
        await send_health_message(constants.BotHealthMessages.TASK_FAILED_AND_RESTART.value)
        poll_new_posts.cancel()
        poll_new_posts.restart()


async def send_health_message(message):
    for subreddit_and_channels in SelectedSubredditsAndChannels:
        status_channel_ids = subreddit_and_channels.status_channel_ids
        for status_channel_id in status_channel_ids:
            current_channel = get_channel_from_id(status_channel_id)
            await current_channel.send(content=message)


# Sends message to Discord channel depending on the platform type and notification type
# Depending on the case, 1-3 messages can be sent for each post
# 1. A ping message if the post matches a filter
# 2. The message containing the post itself
# 3. A message containing a followup message (if any) - followup messages are used to provide content preview since
#    embeds do not support previews.
async def send_message(platform, subreddit_and_channels, reddit_object, triggered_matches, roles_to_ping=[], message_prefix="", message_suffix=""):
    embed = {}
    followup_message = ""  # Used if there are differences in schema where something else needs to be added
    channels = get_channels_of_type(constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_ALL.value, subreddit_and_channels)
    ping_channels = get_channels_of_type(constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_PINGS.value, subreddit_and_channels)
    is_post_submission = reddit_object["post_type"] == constants.PostTypes.REDDIT_SUBMISSION.value

    # Decided not to use is_post_submission here for clarity and in case additional post types are added later
    if reddit_object["post_type"] == constants.PostTypes.REDDIT_SUBMISSION.value:
        channels += get_channels_of_type(constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_POSTS.value, subreddit_and_channels)
    elif reddit_object["post_type"] == constants.PostTypes.REDDIT_COMMENT.value:
        channels += get_channels_of_type(constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_COMMENTS.value, subreddit_and_channels)
    channels = list(dict.fromkeys(channels))  # Filter duplicates from list (similar to sets)

    if platform == constants.Platforms.REDDIT.value:
        message_object = wrangler.construct_reddit_message(
            subreddit_and_channels.subreddit, reddit_object, triggered_matches
        )
        embed = message_object["embed"]
        followup_message = message_object["followup_message"]

    if roles_to_ping:  # TODO: Also take into account the platform for pings
        server_roles = get_roles()
        found_roles = find_roles(server_roles, roles_to_ping)  # TODO: Refactor guilds[0]

        # Pings do not work in embeds, so they must be done as a separate, non-embed message
        if found_roles:
            ping_string = ""
            ping_content = construct_ping_reasoning_block_string(triggered_matches)
            for found_role in found_roles:
                ping_string += found_role.mention + " "
            for ping_channel in ping_channels:
                await send_main_post_message_and_add_reactions(ping_channel, embed, is_post_submission)
                await ping_channel.send("Post alert {}\n{}".format(ping_string, ping_content))
                if followup_message:
                    await ping_channel.send(content=followup_message)

    for channel in channels:
        await send_main_post_message_and_add_reactions(channel, embed, is_post_submission)
        if followup_message:
            await channel.send(content=followup_message)


async def send_message_to_channels(channel_ids, message):
    channels = []
    for channel_id in channel_ids:
        channels.append(get_channel_from_id(channel_id))
    for channel in channels:
        await channel.send(content=message)


def construct_ping_reasoning_block_string(matches):
    matches_string = ""
    for match in matches:
        matches_string += "```{}: {}```".format(match["filter"]["name"], match["flagged_content"])
    return matches_string


# Abstracted calls to send main Reddit post/comment message into function for single point editing
# Override flag since normally to check if post is submission, we query DB, which causes a race condition if post
# is stored before it can be queried. Override bypasses this check and adds the flair.
async def send_main_post_message_and_add_reactions(channel, embed, override=False, flag_reaction=True, additional_message=""):
    # TODO: Make this the only truncation since this feels like double truncation
    truncated_embed = wrangler.truncate_embed(embed)["embed"]
    message = None
    if len(truncated_embed) + len(additional_message) > constants.CharacterLimits.EMBED_TOTAL_CHARS.value:
        await channel.send(content=additional_message)
        message = await channel.send(embed=truncated_embed)
    else:
        message = await channel.send(content=additional_message, embed=truncated_embed)

    # Flag reaction set to boolean so that it can be overrided to not display in secondary review channels and instead
    #     display approve/deny reacts
    if flag_reaction:
        await message.add_reaction(constants.RedditReactEmojis.GENERATE_USER_REPORT.value)
        post_id = get_embed_post_id(embed)
        if override or db_collection_operations.is_post_submission(post_id):
            await message.add_reaction(constants.RedditReactEmojis.GENERATE_NEGATIVE_COMMENT_TREE.value)
        await message.add_reaction(constants.RedditReactEmojis.SECONDARY_REVIEW_FLAG.value)
        await message.add_reaction(constants.RedditReactEmojis.ADD_POST_TO_USER_MOD_COMMENTS.value)
        if environment_variables.HAS_MOD:
            await message.add_reaction(constants.RedditReactEmojis.POST_APPROVE.value)
            await message.add_reaction(constants.RedditReactEmojis.POST_REMOVE.value)
            await message.add_reaction(constants.RedditReactEmojis.POST_LOCK.value)
    else:
        await message.add_reaction(constants.RedditReactEmojis.SECONDARY_REVIEW_APPROVE.value)
        await message.add_reaction(constants.RedditReactEmojis.SECONDARY_REVIEW_REJECT.value)
        await message.add_reaction(constants.RedditReactEmojis.SECONDARY_REVIEW_UPVOTE.value)
        await message.add_reaction(constants.RedditReactEmojis.SECONDARY_REVIEW_DOWNVOTE.value)


async def send_message_and_potentially_ping(post_and_matches, subreddit_and_channels):
    roles_to_ping = []
    post = post_and_matches["post"]
    matches = post_and_matches["matches"]
    for match in matches:
        for filter_specific_role in match["filter"]["roles_to_ping"]:
            roles_to_ping.append(filter_specific_role)
    await send_message(constants.Platforms.REDDIT.value, subreddit_and_channels, post, matches, roles_to_ping)


# Take the required action on the post
async def actions_on_post(post_and_matches, subreddit_and_channels):
    priority_action = praw_operations.determine_priority_action(post_and_matches)
    if priority_action == constants.FilterActions.REMOVE.value and subreddit_and_channels.has_mod:
        post_id = post_and_matches["post"]["_id"]
        post_type = post_and_matches["post"]["post_type"]
        await praw_operations.action_on_post(post_id, constants.RedditOperationTypes.REMOVE.value, post_type)
        await send_message_to_channels(subreddit_and_channels.ping_channel_ids, constants.FilterActions.REMOVE_MESSAGE.value)

    # TODO: Integrate priority action into ping message so we know what action is taken
    await send_message_and_potentially_ping(post_and_matches, subreddit_and_channels)


# Gets all new Reddit posts and stores them in the database
async def get_new_reddit_posts(num_posts, subreddit_and_channels):
    # Refresh filters on each poll
    global db_filters
    global metadata_dict
    db_filters = set_filters()
    metadata_dict = set_metadata()

    ignore_buffer_items = metadata_dict[constants.DatabaseMetadataInfo.IGNORE_BUFFER_NAME.value]["items"]
    subreddit_name = subreddit_and_channels.subreddit
    new_submissions = await praw_operations.get_and_store_unstored(
        num_posts, constants.PostTypes.REDDIT_SUBMISSION, subreddit_name, ignore_buffer_items
    )
    new_comments = await praw_operations.get_and_store_unstored(
        num_posts, constants.PostTypes.REDDIT_COMMENT, subreddit_name, ignore_buffer_items
    )
    new_posts = praw_operations.sort_by_created_time(new_submissions + new_comments, False)

    db_collection_operations.clear_ignore_buffer()
    if new_posts:
        print("{} / {} new posts found on {}".format(datetime.datetime.now(), str(len(new_posts)), subreddit_name))
        # print(new_posts)

    # Scan user history for blacklisted subreddits
    blacklisted_channels = []
    # TODO: Add multi-subreddit support (send to associated channel for subreddit), consider updating classes.py
    for blacklisted_channel in user_preferences.BlacklistedChannelIds:
        blacklisted_channels.append(get_channel_from_id(blacklisted_channel))
    for new_post in new_posts:
        history_object = await praw_operations.scan_user_history(new_post)
        if len(history_object) > 0:
            # TODO: Convert to a nicer embed
            removal_message = "**BLACKLISTED SUBREDDIT ACTIVITY**\n" + "User: " +\
                              constants.RedditEmbedConsts.username_link.value + history_object["username"] + "\n" +\
                              "Blacklisted Subreddit: r/" + history_object["infracting_subreddit"] + "\n" +\
                              "Blacklisted Activity: " + history_object["permalink"] + "\n" +\
                              "Current Post: " + new_post["permalink"]
            if environment_variables.REMOVE_BLACKLISTED_SUBREDDIT_PARTICIPANT_POSTS:
                await praw_operations.action_on_post(new_post["_id"], constants.RedditOperationTypes.REMOVE.value, new_post["post_type"])
            for channel in blacklisted_channels:
                await channel.send(content=removal_message)

    # Check if post is a repost
    repost_channels = []
    # TODO: Add multi-subreddit support (send to associated channel for subreddit), consider updating classes.py
    for repost_channel in user_preferences.RepostChannelIds:
        repost_channels.append(get_channel_from_id(repost_channel))
    if environment_variables.REPOST_SETTINGS["SCAN_FOR_REPOSTS"]:
        for new_post in new_posts:
            if new_post["post_type"] != constants.PostTypes.REDDIT_SUBMISSION.value:
                continue
            reposts = db_collection_operations.get_reposts_of_post(new_post["_id"])
            if len(reposts) == 0:
                continue
            # TODO: Convert to a nicer embed
            reposts_string = ""
            for repost in reposts:
                reposts_string += repost["permalink"] + "\n"
            repost_message = "**POTENTIAL REPOST FOUND**\n" + "User: " +\
                                  constants.RedditEmbedConsts.username_link.value + new_post["author"]["username"] + "\n" +\
                                  "Suspected Post: " + new_post["permalink"] + "\n" +\
                                  "Original Post(s): \n" + reposts_string
            if environment_variables.REPOST_SETTINGS["DELETE_REPOSTS"]:
                await praw_operations.action_on_post(new_post["_id"], constants.RedditOperationTypes.REMOVE.value, new_post["post_type"])
            for channel in repost_channels:
                await channel.send(content=repost_message)

    posts_and_matches = await filters.apply_all_filters(db_filters, new_posts, constants.Platforms.REDDIT.value)
    for post_and_matches in posts_and_matches:
        await actions_on_post(post_and_matches, subreddit_and_channels)


def check_user_is_not_bot(user_to_check):
    return client.user.id != user_to_check.id


def check_message_is_from_bot(message):
    return message.author.id == client.user.id


# Returns all comments from a post with negative karma values
async def get_negative_comment_tree(submission):
    if submission is not None:
        pruned_comments = []
        comments = await praw_operations.request_sorted_comments(submission)
        # Remove all comments >= 0 karma
        for comment in comments:
            if comment.score < 0:
                pruned_comments.append(comment)
        return pruned_comments
    else:
        return None


def get_embed_post_id(embed):
    # TODO: Fix this, it's a bit hacky right now to get the Post ID by partioning - if any text is added after the post ID, it gets messed up
    footer = embed.footer.text
    submission_id_prefix = constants.StringConstants.SUBMISSION_ID.value
    comment_id_prefix = constants.StringConstants.COMMENT_ID.value
    post_id = footer.partition(submission_id_prefix) if submission_id_prefix in footer else footer.partition(comment_id_prefix)
    post_id = post_id[2]
    return post_id


# Returns embed post type (e.g. post/submission)
def get_embed_post_type(embed):
    footer = embed.footer.text
    if footer is not embed.Empty:
        if constants.StringConstants.SUBMISSION_ID.value in footer:
            return constants.PostTypes.REDDIT_SUBMISSION.value
        elif constants.StringConstants.COMMENT_ID.value in footer:
            return constants.PostTypes.REDDIT_COMMENT.value
    else:
        return None


# TODO: If the actual title contains the same emoji, it will be removed from it as well
# TODO: - One idea is to add in a divider (e.g. |) to identify the separation between emojis and the title, but the divider might also be a character in the title
# Removes an emoji from the embed title
def remove_emoji_from_embed_title(embed, emoji):
    title = embed.title
    if emoji in title:
        embed.title = re.sub(emoji + " ", "", title)
    return embed


# Adds emoji to an embed title
def add_emoji_to_embed_title(embed, emoji):
    if emoji == constants.RedditReactEmojis.POST_APPROVE.value:
        embed = remove_emoji_from_embed_title(embed, constants.RedditReactEmojis.POST_REMOVE.value)
    elif emoji == constants.RedditReactEmojis.POST_REMOVE.value:
        embed = remove_emoji_from_embed_title(embed, constants.RedditReactEmojis.POST_APPROVE.value)
    embed.title = emoji + " " + embed.title
    return embed


# Action is either add or remove, not other options (due to the else block catching all)
async def edit_message_embed_with_emoji(message, embed, emoji, action):
    new_embed = add_emoji_to_embed_title(embed, emoji) if action == constants.RedditOperationTypes.ADD.value else remove_emoji_from_embed_title(embed, emoji)
    truncated_embed = wrangler.truncate_embed(new_embed)["embed"]
    await message.edit(embed=truncated_embed)


# Splits initial reaction to appropriate call
async def handle_reaction(reaction, user):
    message = reaction.message
    react_emoji = reaction.emoji
    # If the reaction is not from bot and the message being reacted to is a bot message
    if check_user_is_not_bot(user) and check_message_is_from_bot(reaction.message):
        post_type = get_embed_post_type(message.embeds[0])
        message_main_embed = message.embeds[0]

        if react_emoji == constants.RedditReactEmojis.GENERATE_USER_REPORT.value:
            embed = await db_collection_operations.generate_user_report(message_main_embed.author.name)
            generated_message = await message.channel.send(embed=embed)
            await generated_message.add_reaction(constants.RedditReactEmojis.CLEAR_GENERATED_EMBED.value)
        # If conditional satisfied, is submission post type (negative comment tree react only available for submissions)
        elif react_emoji == constants.RedditReactEmojis.GENERATE_NEGATIVE_COMMENT_TREE.value:
            post_id = get_embed_post_id(message_main_embed)
            submission = await praw_operations.request_post(post_id, constants.PostTypes.REDDIT_SUBMISSION.value)
            comments = await get_negative_comment_tree(submission)
            embed_and_info = wrangler.construct_negative_comment_tree_embed(submission, comments)
            embed = embed_and_info["embed"]
            additional_info = embed_and_info["additional_info"]
            generated_message = await message.channel.send(embed=embed)
            if additional_info != "":
                await message.channel.send(content=additional_info)
            await generated_message.add_reaction(constants.RedditReactEmojis.CLEAR_GENERATED_EMBED.value)
        # Sends post to secondary review channel
        elif react_emoji == constants.RedditReactEmojis.SECONDARY_REVIEW_FLAG.value:
            original_embed = message_main_embed
            # Extracts subreddit from footer
            subreddit = original_embed.footer.text.partition("r/")[2].partition(" |")[0]  # TODO: Refactor into constants or clean up
            selected_sub_and_ch = None
            for subreddit_and_channels in SelectedSubredditsAndChannels:
                if subreddit == subreddit_and_channels.subreddit:
                    selected_sub_and_ch = subreddit_and_channels
                    break
            if selected_sub_and_ch is None:
                await reaction.message.channel.send(content="An internal error has occurred and the specified subreddit could not be found.")
                return
            server_roles = get_roles()
            secondary_review_role = find_roles(server_roles, [user_preferences.Settings.BOT_SECONDARY_REVIEW_ROLE.value])
            flag_message_channels = get_channels_of_type(constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_SECONDARY_REVIEW.value, selected_sub_and_ch)
            if secondary_review_role and flag_message_channels:
                for channel in flag_message_channels:
                    reviewer_ping = secondary_review_role[0].mention + " " if secondary_review_role is not [] else ""
                    request_message = "{}{} {} {} ({})".format(reviewer_ping, constants.StringConstants.SECONDARY_REVIEW_TITLE_PREFIX.value, constants.StringConstants.SECONDARY_REVIEW_REQUESTED_BY_SEPARATOR.value, user.name, user.id)
                    await send_main_post_message_and_add_reactions(channel, original_embed, False, False, request_message)
                await edit_message_embed_with_emoji(message, message_main_embed, react_emoji, constants.RedditOperationTypes.ADD.value)
            else:
                await reaction.message.channel.send(content="The secondary review role could not be found or the associated channel to send reviewed content to could not be found.")
        # Handle secondary review approve/reject
        elif react_emoji == constants.RedditReactEmojis.SECONDARY_REVIEW_APPROVE.value or react_emoji == constants.RedditReactEmojis.SECONDARY_REVIEW_REJECT.value:
            is_approved = False
            if react_emoji == constants.RedditReactEmojis.SECONDARY_REVIEW_APPROVE.value:
                is_approved = True
            review_requester_uuid = message.content.partition(" (")[2].partition(")")[0]  # Do not delete the space in the first partition match
            review_requester = "<@" + review_requester_uuid + ">"
            review_fulfiller = "<@" + str(user.id) + ">"
            embed = await wrangler.construct_approve_or_reject_review_embed(message.embeds[0], review_requester, review_fulfiller, is_approved, message.reactions, client.user.id)
            await message.channel.send(content=review_requester, embed=embed)
        # Adds post to a user's moderator comments
        elif react_emoji == constants.RedditReactEmojis.ADD_POST_TO_USER_MOD_COMMENTS.value:
            comment = "[{}]({})".format(message_main_embed.description, message_main_embed.url)
            mod_comment = await db_collection_operations.add_user_comment(message, message_main_embed.author.name, user, comment)
            if mod_comment:
                await message.channel.send("Added post to user mod comments.")
            else:
                await message.channel.send("Failed to add post to user mod comments.")
            await edit_message_embed_with_emoji(message, message_main_embed, react_emoji, constants.RedditOperationTypes.ADD.value)
        elif environment_variables.HAS_MOD and react_emoji in constants.ReactsThatRequireMod:
            # Lock post
            if react_emoji == constants.RedditReactEmojis.POST_LOCK.value:
                post_id = get_embed_post_id(message_main_embed)
                await praw_operations.action_on_post(post_id, constants.RedditOperationTypes.LOCK.value, post_type)
                await message.remove_reaction(react_emoji, client.user)
                await message.add_reaction(constants.RedditReactEmojis.POST_UNLOCK.value)
                await edit_message_embed_with_emoji(message, message_main_embed, react_emoji, constants.RedditOperationTypes.ADD.value)
            # Unlock post
            elif react_emoji == constants.RedditReactEmojis.POST_UNLOCK.value:
                post_id = get_embed_post_id(message_main_embed)
                await praw_operations.action_on_post(post_id, constants.RedditOperationTypes.UNLOCK.value, post_type)
                await message.remove_reaction(react_emoji, client.user)
                await message.add_reaction(constants.RedditReactEmojis.POST_LOCK.value)
                await edit_message_embed_with_emoji(message, message_main_embed, constants.RedditReactEmojis.POST_LOCK.value, constants.RedditOperationTypes.REMOVE.value)
            # Approve post
            elif react_emoji == constants.RedditReactEmojis.POST_REMOVE.value:
                post_id = get_embed_post_id(message_main_embed)
                await praw_operations.action_on_post(post_id, constants.RedditOperationTypes.REMOVE.value, post_type)
                await edit_message_embed_with_emoji(message, message_main_embed, react_emoji, constants.RedditOperationTypes.ADD.value)
            # Remove post
            elif react_emoji == constants.RedditReactEmojis.POST_APPROVE.value:
                post_id = get_embed_post_id(message_main_embed)
                await praw_operations.action_on_post(post_id, constants.RedditOperationTypes.APPROVE.value, post_type)
                await edit_message_embed_with_emoji(message, message_main_embed, react_emoji, constants.RedditOperationTypes.ADD.value)

        # Reset reaction to allow for repeated actions
        if reaction.emoji not in constants.ReactsThatPersist:
            await message.remove_reaction(reaction.emoji, user)

        # This must be run after reaction removal since it will attempt to remove react from nonexistent message
        if reaction.emoji in constants.ReactsThatClearMessage:
            await message.delete()


# Throws NoPostOrCommentFound exception if filter name is not in database filters
async def is_filter_name_valid(filter_name, context):
    try:
        for db_filter in db_filters:
            if db_filter["name"] == filter_name:
                return True
        raise exceptions.NoPostOrCommentFound
    except exceptions.NoPostOrCommentFound:
        await context.send(content="The specified filter could not be found. Please double-check the filter name.")
        return False


# ============
# BOT COMMANDS
# ============
# TODO: Handle invalid commands gracefully

# TODO: Figure out if add and remove match can be refactored into one function
# Add match to filter
@client.command()
async def add_match(context, filter_name, new_match):
    filter_name_valid = await is_filter_name_valid(filter_name, context)
    if not filter_name_valid:
        return

    # Preliminary check before adding to the database in case new match shouldn't be added
    if filter_name in user_preferences.RegexFilters:
        if not is_match_valid_regex(new_match):
            escaped_match = new_match.replace('"', r'\"')
            await context.send("{} appears to be an invalid regular expression.".format(escaped_match))
            return

    # Add match to database
    add_result = await db_collection_operations.attempt_add_or_remove_match(filter_name, new_match, constants.RedditOperationTypes.ADD.value)
    if add_result:
        # If the filter should also be synced with the automoderator wiki, do it here in addition to updating database
        filter_sync_result = should_filter_be_synced(filter_name)
        automod_result = ""
        if filter_sync_result is not None:
            automod_result = await praw_operations.update_automoderator_page(
                filter_sync_result,
                new_match,
                constants.RedditOperationTypes.ADD.value
            )
            if automod_result == constants.RedditAutomodEditStatus.SUCCESS.value:
                await context.send("{} successfully added to {}".format(new_match, filter_name))
            elif automod_result == constants.RedditAutomodEditStatus.FAIL.value:
                await context.send("There was an issue adding {} to the Reddit automoderator page.".format(new_match))
            elif automod_result == constants.RedditAutomodEditStatus.MISSING_PRIVILEGES.value:
                await context.send("{} could not be added to the Reddit automoderator page due to missing privileges.".format(new_match))
        else:
            await context.send("{} successfully added to {}".format(new_match, filter_name))
    else:
        await context.send("There was an issue adding {} to {}. Verify the specified filter name and ensure the match has not already been added.".format(new_match, filter_name))


@client.command()
async def bulk_add_match(context, filter_name, *matches):
    filter_name_valid = await is_filter_name_valid(filter_name, context)
    if not filter_name_valid:
        return

    if filter_name not in user_preferences.RegexFilters:
        for match in matches:
            match = match.replace(",", "")
            await add_match(context, filter_name, match)
        await context.send("Bulk match adding complete. ")
    else:
        await context.send("Bulk match adding is not supported for regex filters (since commas and spaces are used to separate matches, which conflicts with regex).")


@client.command()
async def remove_match(context, filter_name, match_to_remove):
    filter_name_valid = await is_filter_name_valid(filter_name, context)
    if not filter_name_valid:
        return

    remove_result = await db_collection_operations.attempt_add_or_remove_match(filter_name, match_to_remove, constants.RedditOperationTypes.REMOVE.value)
    if remove_result:
        # If the filter should also be synced with the automoderator wiki, do it here in addition to updating database
        filter_sync_result = should_filter_be_synced(filter_name)
        if filter_sync_result is not None:
            automod_result = await praw_operations.update_automoderator_page(
                filter_sync_result,
                match_to_remove,
                constants.RedditOperationTypes.REMOVE.value
            )
            if automod_result == constants.RedditAutomodEditStatus.SUCCESS.value:
                await context.send("{} successfully removed from {}".format(match_to_remove, filter_name))
            elif automod_result == constants.RedditAutomodEditStatus.FAIL.value:
                await context.send("There was an issue removing {} from the Reddit automoderator page.".format(match_to_remove))
            elif automod_result == constants.RedditAutomodEditStatus.MISSING_PRIVILEGES.value:
                await context.send( "{} could not be removed from the Reddit automoderator page due to missing privileges.".format(match_to_remove))
        else:
            # TODO: Refactor to remove duplicate line from above
            await context.send("{} successfully removed from {}".format(match_to_remove, filter_name))
    else:
        await context.send("There was an issue removing {} from {}. Verify the specified filter name and ensure the match exists in the list of matches.".format(match_to_remove, filter_name))


@client.command()
async def get_matches(context, filter_name):
    filter_name_valid = await is_filter_name_valid(filter_name, context)
    if not filter_name_valid:
        return

    matches = db_collection_operations.get_matches(filter_name)
    if matches:
        matches = matches["matches"]
        matches_output = ""
        for match in matches:
            matches_output += match + ", "
        matches_output = matches_output[:-2]  # Remove extra comma and space after last element
        messages_output = wrangler.truncate_message_into_code_blocks(matches_output)
        for message in messages_output:
            await context.send(message)
    else:
        await context.send("There was an issue finding the matches for {}. Verify the specified filter.".format(filter_name))


# Get post or comment by ID and send embed message. If nothing is found, send error message.
@client.command()
async def get_post(context, post_id_or_url):
    post_id = get_post_id(post_id_or_url)
    post = db_collection_operations.get_post(post_id)
    # If it is a post
    if post is not None:
        embed = wrangler.construct_reddit_message(post["subreddit"], post, [])["embed"]
        await send_main_post_message_and_add_reactions(context.channel, embed)
    else:
        # If it is a comment
        comment = db_collection_operations.get_comment(post_id)
        if comment is not None:
            embed = wrangler.construct_reddit_message(comment["subreddit"], comment, [])["embed"]
            await send_main_post_message_and_add_reactions(context.channel, embed)
        # Otherwise, the post or comment has not yet been queried for
        else:
            try:
                post_and_type = await praw_operations.attempt_to_request_post(post_id)
                praw_post = post_and_type["post"]
                if praw_post is not None:
                    subreddit = praw_post.subreddit.display_name
                    post_type = post_and_type["type"]
                    entry_object = await praw_operations.construct_entry_object(subreddit, praw_post, post_type)
                    valid_entry_object_as_array = praw_operations.remove_invalid_posts([entry_object])
                    praw_operations.store_entry_objects(valid_entry_object_as_array, post_type)
                    db_collection_operations.add_post_id_to_ignore_buffer(post_id)
                    await get_post(context, post_id)
            except exceptions.NoPostOrCommentFound:
                await context.channel.send("Failed to find post. Please verify the post ID.")


@client.command()
async def get_filters(context):
    filter_names = db_collection_operations.get_filters()
    if filter_names:
        filter_names_string = ""
        for filter_name in filter_names:
            filter_names_string += filter_name + ", "
        filter_names_string = filter_names_string[:-2]
        await context.send("Filters: {}".format(filter_names_string))
    else:
        await context.send("No filters found.")


@client.command()
async def user_report(context, username):
    embed = await db_collection_operations.generate_user_report(username)
    await context.send(embed=embed)


@client.command()
async def user_comments(context, username):
    embed = await db_collection_operations.generate_user_comments(username)
    await context.send(embed=embed)


@client.command()
async def add_user_comment(context, username, *, comment):
    comment_added = await db_collection_operations.add_user_comment(context.message, username, context.message.author, comment)
    if comment_added:
        await context.send("Moderator comment added to {}.".format(username))
    else:
        await context.send("There was an issue adding your comment.")


@client.command()
async def remove_user_comment(context, username, comment_id):
    comment_removed = await db_collection_operations.remove_user_comment(username, comment_id)
    if comment_removed:
        await context.send("Moderator comment removed from {}.".format(username))
    else:
        await context.send(
            "There was an issue removing the specified comment. Please verify the comment ID and the given username."
        )


@client.command()
async def subscribe(context, role):
    server_roles = get_roles()
    found_roles = find_roles(server_roles, [role])

    if not found_roles:
        await context.channel.send("Failed to find role.")

    for role in found_roles:
        await context.author.add_roles(role)
        await context.channel.send("Successfully assigned role.")


@client.command()
async def unsubscribe(context, role):
    server_roles = get_roles()
    found_roles = find_roles(server_roles, [role])

    if not found_roles:
        await context.channel.send("Failed to find role.")

    for role in found_roles:
        await context.author.remove_roles(role)
        await context.channel.send("Successfully removed role.")


@client.command()
async def ping(context):
    await context.send("Pong!")


@client.command()
async def version(context):
    await context.send("v" + rma_version)


@client.event
async def on_reaction_add(reaction, user):
    await handle_reaction(reaction, user)
    if environment_variables.DEV_MODE:
        if check_user_is_not_bot(user):
            print("React interacted with: {}".format(reaction))


@client.event
async def on_command_error(context, exception):
    if exception.__class__ == discord.ext.commands.errors.MissingRequiredArgument:
        await context.send("Your command is missing one or more arguments. Please double-check your input and try again.")


# Set up logging
if environment_variables.ENABLE_LOGGING:
    logger = logging.getLogger('discord')
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    logger.addHandler(handler)


# Initialize and run Discord bot
if environment_variables.DEV_MODE:
    client.run(environment_variables.DEV_DISCORD_BOT_TOKEN)
else:
    client.run(environment_variables.LIVE_DISCORD_BOT_TOKEN)
