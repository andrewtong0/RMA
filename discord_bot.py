import asyncio
import discord
import re
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
def set_filters():
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


def get_roles():
    return client.guilds[0].roles


# ==============
# INITIALIZATION
# ==============

client = commands.Bot(command_prefix=user_preferences.Settings.BOT_PREFIX.value)
db_filters = set_filters()

# =====================
# GENERIC BOT FUNCTIONS
# =====================


# Login status + presence flair
@client.event
async def on_ready():
    print('Logged in as', client.user)
    await client.change_presence(activity=discord.Game(name='***REMOVED***'))


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


# ===================
# REDDIT POST POLLING
# ===================

# Grabs new posts, stores them in the database
async def poll_new_posts():
    await client.wait_until_ready()
    while not client.is_closed():
        for subreddit_and_channels in user_preferences.SelectedSubredditsAndChannels:
            await get_new_reddit_posts(10, subreddit_and_channels)
        await asyncio.sleep(user_preferences.BotConsts.POLL_TIMER.value)


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
    is_post_submission = reddit_object["post_type"] == constants.DbEntry.REDDIT_SUBMISSION.value

    # Decided not to use is_post_submission here for clarity and in case additional post types are added later
    if reddit_object["post_type"] == constants.DbEntry.REDDIT_SUBMISSION.value:
        channels += get_channels_of_type(constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_POSTS.value, subreddit_and_channels)
    elif reddit_object["post_type"] == constants.DbEntry.REDDIT_COMMENT.value:
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
        found_roles = find_role(server_roles, roles_to_ping)  # TODO: Refactor guilds[0]

        # Pings do not work in embeds, so they must be done as a separate, non-embed message
        if found_roles:
            ping_string = ""
            for found_role in found_roles:
                ping_string += found_role.mention + " "
            for ping_channel in ping_channels:
                await send_main_post_message_and_add_reactions(ping_channel, embed, is_post_submission)
                await ping_channel.send("Post alert {}".format(ping_string))
                if followup_message:
                    await ping_channel.send(content=followup_message)

    for channel in channels:
        await send_main_post_message_and_add_reactions(channel, embed, is_post_submission)
        if followup_message:
            await channel.send(content=followup_message)


# Abstracted calls to send main Reddit post/comment message into function for single point editing
# Override flag since normally to check if post is submission, we query DB, which causes a race condition if post
# is stored before it can be queried. Override bypasses this check and adds the flair.
async def send_main_post_message_and_add_reactions(channel, embed, override=False, flag_reaction=True, additional_message=""):
    message = await channel.send(content=additional_message, embed=embed)

    # Flag reaction set to boolean so that it can be overrided to not display in secondary review channels and instead
    # display approve/deny reacts
    if flag_reaction:
        await message.add_reaction(constants.RedditReactEmojis.GENERATE_USER_REPORT.value)
        post_id = get_embed_post_id(embed)
        if override or db_collection_operations.is_post_submission(post_id):
            await message.add_reaction(constants.RedditReactEmojis.GENERATE_NEGATIVE_COMMENT_TREE.value)
        await message.add_reaction(constants.RedditReactEmojis.SECONDARY_REVIEW_FLAG.value)
        await message.add_reaction(constants.RedditReactEmojis.ADD_POST_TO_USER_MOD_COMMENTS.value)
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


# We take action on all posts, regardless if they have matches (if there are no matches, we only send a message)
async def actions_on_posts(post_and_matches, subreddit_and_channels):
    priority_action = praw_operations.determine_priority_action(post_and_matches)
    # TODO: Integrate priority action into ping message so we know what action is taken
    await send_message_and_potentially_ping(post_and_matches, subreddit_and_channels)


# Gets all new Reddit posts and stores them in the database
async def get_new_reddit_posts(num_posts, subreddit_and_channels):
    # Refresh filters on each poll
    global db_filters
    db_filters = set_filters()

    subreddit_name = subreddit_and_channels.subreddit
    new_submissions = praw_operations.get_and_store_unstored(num_posts, constants.DbEntry.REDDIT_SUBMISSION, subreddit_name)
    new_comments = praw_operations.get_and_store_unstored(num_posts, constants.DbEntry.REDDIT_COMMENT, subreddit_name)
    new_posts = praw_operations.sort_by_created_time(new_submissions + new_comments, False)
    if new_posts:
        print(str(len(new_posts)) + " new posts found.")
        print(new_posts)
    posts_and_matches = filters.apply_all_filters(db_filters, new_posts, constants.Platforms.REDDIT.value)
    for post_and_matches in posts_and_matches:
        await actions_on_posts(post_and_matches, subreddit_and_channels)


def check_user_is_not_bot(user_to_check):
    return client.user.id != user_to_check.id


def check_message_is_from_bot(message):
    return message.author.id == client.user.id


# Returns all comments from a post with negative karma values
def get_negative_comment_tree(submission):
    pruned_comments = []
    comments = praw_operations.request_sorted_comments(submission)
    # Remove all comments >= 0 karma
    for comment in comments:
        if comment.score < 0:
            pruned_comments.append(comment)
    return pruned_comments


def get_embed_post_id(embed):
    # TODO: Fix this, it's a bit hacky right now to get the Post ID by partioning - if any text is added after the post ID, it gets messed up
    footer = embed.footer.text
    post_id = footer.partition(constants.StringConstants.POST_ID.value)[2]
    return post_id


# Splits initial reaction to appropriate call
async def handle_reaction(reaction, user):
    message = reaction.message
    react_emoji = reaction.emoji
    # If the reaction is not from bot and the message being reacted to is a bot message
    if check_user_is_not_bot(user) and check_message_is_from_bot(reaction.message):
        if react_emoji == constants.RedditReactEmojis.GENERATE_USER_REPORT.value:
            embed = db_collection_operations.generate_user_report(message.embeds[0].author.name)
            generated_message = await message.channel.send(embed=embed)
            await generated_message.add_reaction(constants.RedditReactEmojis.CLEAR_GENERATED_EMBED.value)
        # If conditional satisfied, is submission post type (negative comment tree react only available for submissions)
        elif react_emoji == constants.RedditReactEmojis.GENERATE_NEGATIVE_COMMENT_TREE.value:
            message_embed = reaction.message.embeds[0]
            post_id = get_embed_post_id(message_embed)
            submission = praw_operations.request_submission(post_id)
            comments = get_negative_comment_tree(submission)
            embed = wrangler.construct_negative_comment_tree_embed(submission, comments)
            generated_message = await message.channel.send(embed=embed)
            await generated_message.add_reaction(constants.RedditReactEmojis.CLEAR_GENERATED_EMBED.value)
        elif react_emoji == constants.RedditReactEmojis.SECONDARY_REVIEW_FLAG.value:
            original_embed = message.embeds[0]
            # Extracts subreddit from footer
            subreddit = original_embed.footer.text.partition("r/")[2].partition(" |")[0]  # TODO: Refactor into constants or clean up
            selected_sub_and_ch = None
            for subreddit_and_channels in user_preferences.SelectedSubredditsAndChannels:
                if subreddit == subreddit_and_channels.subreddit:
                    selected_sub_and_ch = subreddit_and_channels
                    break
            server_roles = get_roles()
            secondary_review_role = find_role(server_roles, [user_preferences.Settings.BOT_SECONDARY_REVIEW_ROLE.value])
            flag_message_channels = get_channels_of_type(constants.RedditDiscordChannelTypes.RD_CHANNELTYPE_SECONDARY_REVIEW.value, selected_sub_and_ch)
            for channel in flag_message_channels:
                reviewer_ping = secondary_review_role[0].mention + " " if secondary_review_role is not [] else ""
                request_message = "{}{} {} {} ({})".format(reviewer_ping, constants.StringConstants.SECONDARY_REVIEW_TITLE_PREFIX.value, constants.StringConstants.SECONDARY_REVIEW_REQUESTED_BY_SEPARATOR.value, user.name, user.id)
                await send_main_post_message_and_add_reactions(channel, original_embed, False, False, request_message)
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
        elif react_emoji == constants.RedditReactEmojis.ADD_POST_TO_USER_MOD_COMMENTS.value:
            embed = message.embeds[0]
            comment = "[{}]({})".format(embed.description, embed.url)
            mod_comment = db_collection_operations.add_user_comment(message, embed.author.name, user, comment)
            if mod_comment:
                await message.channel.send("Added post to user mod comments.")
            else:
                await message.channel.send("Failed to add post to user mod comments.")

        # Reset reaction to allow for repeated actions
        if reaction.emoji not in constants.ReactsThatPersist:
            await message.remove_reaction(reaction.emoji, user)

        # This must be run after reaction removal since it will attempt to remove react from nonexistent message
        if reaction.emoji in constants.ReactsThatClearMessage:
            await message.delete()


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
        messages_output = wrangler.truncate_message(matches_output)
        for message in messages_output:
            await context.send(message)
    else:
        await context.send("There was an issue finding the matches for {}. Verify the specified filter.".format(filter_name))


# Get post or comment by ID and send embed message. If nothing is found, send error message.
@client.command()
async def get_post(context, post_id):
    post = db_collection_operations.get_post(post_id)
    if post is not None:
        embed = wrangler.construct_reddit_message(post["subreddit"], post, [])["embed"]
        await send_main_post_message_and_add_reactions(context.channel, embed)
    else:
        comment = db_collection_operations.get_comment(post_id)
        if comment is not None:
            embed = wrangler.construct_reddit_message(comment["subreddit"], comment, [])["embed"]
            await send_main_post_message_and_add_reactions(context.channel, embed)
        else:
            await context.channel.send("Failed to send message. Please verify the post ID.")


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
    print("User Report")
    embed = db_collection_operations.generate_user_report(username)
    await context.send(embed=embed)


@client.command()
async def add_user_comment(context, username, *comment):
    # Since comment string is separated by spaces, Discord will recognize each word as a separate param
    comment_string = ""
    for word in comment:
        comment_string += word + " "
    comment_string = comment_string[:-1]  # Remove extra space at end
    comment_added = db_collection_operations.add_user_comment(context.message, username, context.message.author, comment_string)
    if comment_added:
        await context.send("Moderator comment added to {}.".format(username))
    else:
        await context.send("There was an issue adding your comment.")


@client.command()
async def subscribe(context, role):
    server_roles = get_roles()
    found_roles = find_role(server_roles, [role])

    if not found_roles:
        await context.channel.send("Failed to find role.")

    for role in found_roles:
        await context.author.add_roles(role)
        await context.channel.send("Successfully assigned role.")


@client.command()
async def unsubscribe(context, role):
    server_roles = get_roles()
    found_roles = find_role(server_roles, [role])

    if not found_roles:
        await context.channel.send("Failed to find role.")

    for role in found_roles:
        await context.author.remove_roles(role)
        await context.channel.send("Successfully removed role.")


@client.event
async def on_reaction_add(reaction, user):
    await handle_reaction(reaction, user)
    # print(reaction)


# Initialize and run Discord bot
client.loop.create_task(poll_new_posts())
if environment_variables.DEV_MODE:
    client.run(environment_variables.DEV_DISCORD_BOT_TOKEN)
else:
    client.run(environment_variables.LIVE_DISCORD_BOT_TOKEN)
