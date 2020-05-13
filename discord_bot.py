from enum import Enum
import os
import asyncio
import discord
import re
import datetime

# File imports
import constants
import post_grabber
import filters
import message_constructor
import user_preferences

# This file should only be used for communication via Discord - no actions should be made here.


class BotConsts(Enum):
    BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
    POLL_TIMER = 1000


def find_role(roles, roles_to_find):
    found_roles = []
    for role_to_find in roles_to_find:
        found_role = next(role for role in roles if role_to_find == role.name)
        found_roles.append(found_role)
    return found_roles


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


# DiscordBot object
class DiscordBot(discord.Client):
    # Initializes background polling task
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters = {}
        self.set_filters()
        self.bg_check = self.loop.create_task(self.poll_new_posts())

    # Login status + presence flair
    async def on_ready(self):
        print('Logged in as', self.user)
        await self.change_presence(activity=discord.Game(name='***REMOVED***'))

    # Initializes filters on startup by grabbing filters
    def set_filters(self):
        retrieved_filters = filters.get_all_filters()
        output_filters = []
        for f in retrieved_filters:
            output_filters.append(f)
        self.filters = output_filters

    # Grabs new posts, stores them in the database
    async def poll_new_posts(self):
        await self.wait_until_ready()
        while not self.is_closed():
            await self.get_new_reddit_posts(10)
            await asyncio.sleep(BotConsts.POLL_TIMER.value)

    # Sends message to Discord channel depending on the platform type and notification type
    async def send_message(self, platform, reddit_object, triggered_matches, roles_to_ping=[], message_prefix="", message_suffix=""):
        embed = {}
        followup_message = ""  # Used if there are differences in schema where something else needs to be added
        if platform == constants.Platforms.REDDIT.value:
            message_object = message_constructor.construct_reddit_message(
                reddit_object, triggered_matches, message_prefix, message_suffix
            )
            embed = message_object["embed"]
            followup_message = message_object["followup_message"]
        channel = self.get_channel(user_preferences.Channels.REDDIT_MAIN_CHANNEL.value)
        if roles_to_ping:  # TODO: Also take into account the platform for pings
            found_roles = find_role(discordBot.guilds[0].roles, roles_to_ping)  # TODO: Refactor out [0] since if the bot is in multiple servers, this may not reference the right server
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
            await channel.send(embed=embed, content=followup_message)

    # Gets all new Reddit posts and stores them in the database
    async def get_new_reddit_posts(self, num_posts):
        new_submissions = post_grabber.get_and_store_posts(num_posts, constants.DbEntry.REDDIT_SUBMISSION)
        new_comments = post_grabber.get_and_store_posts(num_posts, constants.DbEntry.REDDIT_COMMENT)
        new_posts = post_grabber.sort_by_created_time(new_submissions + new_comments)
        print("NEW POSTS")
        print(new_posts)
        for post in new_posts:
            # TODO: Platform needs to be changed to pull from the post/comment after adding to the submissions/comments in database
            triggered_matches = post_triggers_filter(post, self.filters, constants.Platforms.REDDIT.value)
            roles_to_ping = []

            # All triggered match "logical" operations (things that affect functionality beyond flavour text) should
            #   be done within this loop over triggered_matches, NOT the one in message_constructor.py
            for match in triggered_matches:
                for filter_specific_role in match["filter"]["roles_to_ping"]:
                    # TODO: Determine if there are multiple matches, what the most extreme match is
                    roles_to_ping.append(filter_specific_role)

            await self.send_message(constants.Platforms.REDDIT.value, post, triggered_matches, roles_to_ping)

    # Add match to filter
    async def add_match_to_filter(self, match):



# Initialize and run Discord bot
discordBot = DiscordBot()
discordBot.run(os.environ.get("DISCORD_BOT_TOKEN"))
