from enum import Enum
import os
import asyncio
import discord
from discord.ext import commands
import re
import datetime

# File imports
import constants
import praw_operations
import filters
import wrangler
import user_preferences
import db_collection_operations

# This file should only be used for Discord bot management

# ================
# FUNCTIONS/CONSTS
# ================


class BotConsts(Enum):
    BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
    POLL_TIMER = 300


# Initializes filters on startup by grabbing filters
def get_filters():
    retrieved_filters = filters.get_all_filters()
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


# Checks a post against all filters, returns list of filters triggered to generate message
def post_triggers_filter(post, post_filters, platform):
    # Stores list of triggered filters and the content caught by the filters
    triggered_matches = []
    for post_filter in post_filters:
        if platform == constants.Platforms.REDDIT.value and post_filter["platform"] == constants.Platforms.REDDIT.value:
            if post_filter["type"] == constants.RedditFilterTypes.USERS.value and post["author"]["username"] in post_filter["matches"]:
                triggered_matches.append({"filter": post_filter, "flagged_content": post["author"]["username"], "action": post_filter["action"]})
            elif post_filter["type"] == constants.RedditFilterTypes.POSTS.value:
                for regex_phrase in post_filter["matches"]:
                    # Submissions also have titles, so we should check the title in addition to the content of the post
                    if post["post_type"] == constants.DbEntry.REDDIT_SUBMISSION.value:
                        if re.match(regex_phrase, post["title"]):
                            triggered_matches.append({"filter": post_filter, "flagged_content": regex_phrase,
                                                      "action": post_filter["action"]})
                    if re.match(regex_phrase, post["content"]):
                        triggered_matches.append({"filter": post_filter, "flagged_content": regex_phrase,
                                                  "action": post_filter["action"]})
            # TODO: Implement this once subreddit is stored or we figure out how to do subreddit blacklist
            # elif post_filter.type == constants.RedditFilterTypes.SUBREDDITS.value and post.subreddit in post_filter.matches:
    return triggered_matches

# =====================
# GENERIC BOT FUNCTIONS
# =====================


# Login status + presence flair
@client.event
async def on_ready():
    print('Logged in as', client.user)
    await client.change_presence(activity=discord.Game(name='***REMOVED***'))


# ===================
# REDDIT POST POLLING
# ===================

# Grabs new posts, stores them in the database
async def poll_new_posts():
    await client.wait_until_ready()
    while not client.is_closed():
        await get_new_reddit_posts(10)
        await asyncio.sleep(BotConsts.POLL_TIMER.value)


# Sends message to Discord channel depending on the platform type and notification type
async def send_message(platform, reddit_object, triggered_matches, roles_to_ping=[], message_prefix="", message_suffix=""):
    embed = {}
    followup_message = ""  # Used if there are differences in schema where something else needs to be added
    if platform == constants.Platforms.REDDIT.value:
        message_object = wrangler.construct_reddit_message(
            reddit_object, triggered_matches, message_prefix, message_suffix
        )
        embed = message_object["embed"]
        followup_message = message_object["followup_message"]
    channel = client.get_channel(user_preferences.Channels.REDDIT_MAIN_CHANNEL.value)
    if roles_to_ping:  # TODO: Also take into account the platform for pings
        found_roles = find_role(client.guilds[0].roles, roles_to_ping)  # TODO: Refactor out [0] since if the bot is in multiple servers, this may not reference the right server
        # Pings do not work in embeds, so they must be done as a separate, not embed message
        if found_roles:
            ping_string = ""
            for found_role in found_roles:
                ping_string += found_role.mention + " "
            await channel.send("Post alert {}".format(ping_string))
        await channel.send(embed=embed)
        if followup_message:
            await channel.send(content=followup_message)
    else:
        await channel.send(embed=embed)
        if followup_message:
            await channel.send(content=followup_message)


# Gets all new Reddit posts and stores them in the database
async def get_new_reddit_posts(num_posts):
    new_submissions = praw_operations.get_and_store_unstored(num_posts, constants.DbEntry.REDDIT_SUBMISSION)
    new_comments = praw_operations.get_and_store_unstored(num_posts, constants.DbEntry.REDDIT_COMMENT)
    new_posts = praw_operations.sort_by_created_time(new_submissions + new_comments)
    print("NEW POSTS")
    print(new_posts)
    for post in new_posts:
        # TODO: Platform needs to be changed to pull from the post/comment after adding to the submissions/comments in database
        triggered_matches = post_triggers_filter(post, db_filters, constants.Platforms.REDDIT.value)
        roles_to_ping = []

        # All triggered match "logical" operations (things that affect functionality beyond flavour text) should
        #   be done within this loop over triggered_matches, NOT the one in wrangler.py
        for match in triggered_matches:
            for filter_specific_role in match["filter"]["roles_to_ping"]:
                # TODO: Determine if there are multiple matches, what the most extreme match is
                roles_to_ping.append(filter_specific_role)

        await send_message(constants.Platforms.REDDIT.value, post, triggered_matches, roles_to_ping)


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
        await context.send("There was an issue adding {} to {}. Verify the specified filter name and ensure the match has not already been added.".format(filter_name, new_match))


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
        await context.send("There was an issue removing {} from {}. Verify the specified filter name and ensure the match exists in the list of matches.".format(filter_name, match_to_remove))


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


# TODO: Invert posts from user_report (newest at top)
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
client.run(os.environ.get("DISCORD_BOT_TOKEN"))
