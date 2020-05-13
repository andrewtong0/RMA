from enum import Enum
import os
import asyncio
import discord
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
    async def send_message(self, platform, reddit_object, content_filter, message_footer, message_prefix="", message_suffix="", roles_to_ping=[]):
        embed = {}
        followup_message = ""  # Used if there are differences in schema where something else needs to be added
        if platform == constants.Platforms.REDDIT:
            message_object = message_constructor.construct_reddit_message(
                reddit_object, content_filter, message_footer, message_prefix, message_suffix
            )
            embed = message_object["embed"]
            followup_message = message_object["followup_message"]
        channel = self.get_channel(user_preferences.Channels.REDDIT_MAIN_CHANNEL.value)
        if user_preferences.Channels.USERS_TO_PING:  # TODO: Also take into account the platform for pings
            await channel.send(embed=embed)
            if followup_message:
                await channel.send(content=followup_message)
        await channel.send(embed=embed, content=followup_message)

    # Gets all new Reddit posts and stores them in the database
    async def get_new_reddit_posts(self, num_posts):
        new_submissions = post_grabber.get_and_store_posts(num_posts, constants.DbEntry.REDDIT_SUBMISSION)
        new_comments = post_grabber.get_and_store_posts(num_posts, constants.DbEntry.REDDIT_COMMENT)
        new_posts = post_grabber.sort_by_created_time(new_submissions + new_comments)
        print("NEW POSTS")
        print(new_posts)
        for post in new_posts:
            # if self.filters and user_preferences.Settings.FILTERS.value:
            #     matches_and_posts = filters.apply_all_filters(self.filters, new_posts)
            #     matches = matches_and_posts["matches"]
            #     post_matches = matches_and_posts["posts"]
            #     for index in range(len(post_matches)):
            #         await self.send_message(constants.Platforms.REDDIT, post_matches[index], {"action": constants.FilterActions.MONITOR.value, "name": "Shadowbans"}, str(matches[index]))
            #         # Filter info should be removed from send_message
            await self.send_message(constants.Platforms.REDDIT, post, {"action": constants.FilterActions.MONITOR.value, "name": "Shadowbans"}, "Shadowban | " + post["_id"], "<@160296617382117377>")


# Initialize and run Discord bot
discordBot = DiscordBot()
discordBot.run(os.environ.get("DISCORD_BOT_TOKEN"))
