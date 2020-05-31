import asyncio
import discord
from discord.ext import commands

# File imports
import constants
import praw_operations
import filters
import wrangler
import user_preferences
import db_collection_operations
import environment_variables

# This file should only be used for Discord bot management

# ================
# FUNCTIONS/CONSTS
# ================


# Initializes filters on startup by grabbing filters
def get_filters():
    retrieved_filters = db_collection_operations.get_collection("filters")
    output_filters = []
    for f in retrieved_filters:
        output_filters.append(f)
    return output_filters


# Return roles matching names in roles_to_find
def find_role(roles, roles_to_find):
    found_roles = []
    for role_to_find in roles_to_find:
        found_role = next(role for role in roles if role_to_find == role.name)
        found_roles.append(found_role)
    return found_roles


# ==============
# INITIALIZATION
# ==============

client = commands.Bot(command_prefix=user_preferences.Settings.BOT_PREFIX.value)
db_filters = get_filters()

# =====================
# GENERIC BOT FUNCTIONS
# =====================


# Login status + presence flair
@client.event
async def on_ready():
    print('Logged in as', client.user)
    await client.change_presence(activity=discord.Game(name='***REMOVED***'))


def get_channels_from_ids(channel_ids):
    channels = []
    for channel_id in channel_ids:
        channels.append(client.get_channel(channel_id))
    return channels


def get_channels_of_type(channel_type):
    # Set channel based on environment
    channels = []
    if channel_type == constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_ALL.value:
        for channel in user_preferences.SelectedSubredditsAndChannels:
            channels += get_channels_from_ids(channel.main_channel_ids)
    elif channel_type == constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_POSTS.value:
        for channel in user_preferences.SelectedSubredditsAndChannels:
            channels += get_channels_from_ids(channel.post_channel_ids)
    elif channel_type == constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_COMMENTS.value:
        for channel in user_preferences.SelectedSubredditsAndChannels:
            channels += get_channels_from_ids(channel.comment_channel_ids)
    elif channel_type == constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_PINGS.value:
        for channel in user_preferences.SelectedSubredditsAndChannels:
            channels += get_channels_from_ids(channel.ping_channel_ids)
    return channels


# ===================
# REDDIT POST POLLING
# ===================

# Grabs new posts, stores them in the database
async def poll_new_posts():
    await client.wait_until_ready()
    while not client.is_closed():
        await get_new_reddit_posts(10)
        await asyncio.sleep(user_preferences.BotConsts.POLL_TIMER.value)


# Sends message to Discord channel depending on the platform type and notification type
# Depending on the case, 1-3 messages can be sent for each post
# 1. A ping message if the post matches a filter
# 2. The message containing the post itself
# 3. A message containing a followup message (if any) - followup messages are used to provide content preview since
#    embeds do not support previews.
async def send_message(platform, reddit_object, triggered_matches, roles_to_ping=[], message_prefix="", message_suffix=""):
    embed = {}
    followup_message = ""  # Used if there are differences in schema where something else needs to be added
    channels = get_channels_of_type(constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_ALL.value)
    ping_channels = get_channels_of_type(constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_PINGS.value)
    if reddit_object["post_type"] == constants.DbEntry.REDDIT_SUBMISSION.value:
        channels += get_channels_of_type(constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_POSTS.value)
    elif reddit_object["post_type"] == constants.DbEntry.REDDIT_COMMENT.value:
        channels += get_channels_of_type(constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_COMMENTS.value)

    if platform == constants.Platforms.REDDIT.value:
        message_object = wrangler.construct_reddit_message(
            reddit_object, triggered_matches, message_prefix, message_suffix
        )
        embed = message_object["embed"]
        followup_message = message_object["followup_message"]

    for channel in channels:
        if roles_to_ping:  # TODO: Also take into account the platform for pings
            found_roles = find_role(client.guilds[1].roles, roles_to_ping)  # TODO: Refactor out [0] since if the bot is in multiple servers, this may not reference the right server

            # Pings do not work in embeds, so they must be done as a separate, non-embed message
            if found_roles:
                ping_string = ""
                for found_role in found_roles:
                    ping_string += found_role.mention + " "
                for ping_channel in ping_channels:
                    await ping_channel.send(embed=embed)
                    await ping_channel.send("Post alert {}".format(ping_string))
                    if followup_message:
                        await ping_channel.send(content=followup_message)
        await channel.send(embed=embed)
        if followup_message:
            await channel.send(content=followup_message)


async def send_message_and_potentially_ping(post_and_matches):
    roles_to_ping = []
    post = post_and_matches["post"]
    matches = post_and_matches["matches"]
    for match in matches:
        for filter_specific_role in match["filter"]["roles_to_ping"]:
            roles_to_ping.append(filter_specific_role)
    await send_message(constants.Platforms.REDDIT.value, post, matches, roles_to_ping)


# We take action on all posts, regardless if they have matches (if there are no matches, we only send a message)
async def actions_on_posts(post_and_matches):
    priority_action = praw_operations.determine_priority_action(post_and_matches)
    # TODO: Integrate priority action into ping message so we know what action is taken
    await send_message_and_potentially_ping(post_and_matches)


# Gets all new Reddit posts and stores them in the database
async def get_new_reddit_posts(num_posts):
    new_submissions = praw_operations.get_and_store_unstored(num_posts, constants.DbEntry.REDDIT_SUBMISSION)
    new_comments = praw_operations.get_and_store_unstored(num_posts, constants.DbEntry.REDDIT_COMMENT)
    new_posts = praw_operations.sort_by_created_time(new_submissions + new_comments, False)
    if new_posts:
        print(str(len(new_posts)) + " new posts found.")
        print(new_posts)
    posts_and_matches = filters.apply_all_filters(db_filters, new_posts, constants.Platforms.REDDIT.value)
    for post_and_matches in posts_and_matches:
        await actions_on_posts(post_and_matches)


# ============
# BOT COMMANDS
# ============
# TODO: Handle invalid commands gracefully

# Add match to filter
@client.command()
async def add_match(context, filter_name, new_match):
    add_result = db_collection_operations.attempt_add_or_remove_match(filter_name, new_match, constants.RedditFilterOperationTypes.ADD.value)
    if add_result:
        await context.send("{} successfully added to {}".format(new_match, filter_name))
    else:
        await context.send("There was an issue adding {} to {}. Verify the specified filter name and ensure the match has not already been added.".format(new_match, filter_name))


@client.command()
async def bulk_add_match(context, filter_name, *matches):
    for match in matches:
        match = match.replace(",", "")
        await add_match(context, filter_name, match)
    await context.send("Bulk match adding complete. ")


@client.command()
async def remove_match(context, filter_name, match_to_remove):
    remove_result = db_collection_operations.attempt_add_or_remove_match(filter_name, match_to_remove, constants.RedditFilterOperationTypes.REMOVE.value)
    if remove_result:
        await context.send("{} successfully removed from {}".format(match_to_remove, filter_name))
    else:
        await context.send("There was an issue removing {} from {}. Verify the specified filter name and ensure the match exists in the list of matches.".format(match_to_remove, filter_name))


@client.command()
async def get_matches(context, filter_name):
    matches = db_collection_operations.get_matches(filter_name)
    if matches:
        matches = matches["matches"]
        matches_output = ""
        for match in matches:
            matches_output += match + ", "
        matches_output = matches_output[:-2]  # Remove extra comma and space after last element
        await context.send("{}: {}".format(filter_name, matches_output))
    else:
        await context.send("There was an issue finding the matches for {}. Verify the specified filter.".format(filter_name))


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
    embed = db_collection_operations.generate_user_report(username)
    await context.send(embed=embed)


@client.command()
async def add_user_comment(context, username, *comment):
    # Since comment string is separated by spaces, Discord will recognize each word as a separate param
    comment_string = ""
    for word in comment:
        comment_string += word + " "
    comment_string = comment_string[:-1]  # Remove extra space at end
    comment_added = db_collection_operations.add_user_comment(context, username, comment_string)
    if comment_added:
        await context.send("Moderator comment added to {}.".format(username))
    else:
        await context.send("There was an issue adding your comment.")


# Initialize and run Discord bot
client.loop.create_task(poll_new_posts())
if environment_variables.DEV_MODE:
    client.run(environment_variables.DEV_DISCORD_BOT_TOKEN)
else:
    client.run(environment_variables.LIVE_DISCORD_BOT_TOKEN)
