import constants
import datetime
import discord
import re
from enum import Enum


class RedditEmbedConsts(Enum):
    colour = 0xc77d00
    removed_thumbnail = "https://cdn4.iconfinder.com/data/icons/social-messaging-ui-coloricon-1/21/52-512.png"
    monitor_thumbnail = "https://c7.uihere.com/files/928/549/87/magnifying-glass-computer-icons-magnification-loupe.jpg"
    icon = "https://www.redditstatic.com/desktop2x/img/favicon/android-icon-192x192.png"
    username_link = "https://reddit.com/u/"
    regex_matchers = {
        "image": ["external\\-preview\\.redd\\.it", "preview\\.redd\\.it", "i\\.redd\\.it", "pbs\\.twimg\\.com"],
        "twitch_clip": ["clips\\.twitch\\.tv"],
        "youtube": ["youtube\\.com"],
        "twitter": ["twitter\\.com"]
    }


def construct_reddit_message(post, content_filter, message_footer, message_prefix, message_suffix, roles_to_ping):
    is_submission_post = post["post_type"] == constants.DbEntry.REDDIT_SUBMISSION.value
    post_content = post["content"]
    embed_title = post["title"] if is_submission_post else post_content
    embed_message_body_raw = post_content if is_submission_post else ""
    embed_message_body = message_prefix + "\n" + embed_message_body_raw + "\n" + message_suffix
    embed_timestamp = datetime.datetime.utcfromtimestamp(post["created_time"]["utc"])

    author_name = post["author"]["username"]
    embed_username_link = RedditEmbedConsts.username_link.value + author_name

    embed = discord.Embed(
        title=embed_title,
        colour=discord.Colour(RedditEmbedConsts.colour.value),
        url=post["permalink"],
        description=embed_message_body,
        timestamp=embed_timestamp
    )

    filter_action = content_filter["action"]
    filter_name = content_filter["name"]
    # embed_thumbnail_link = RedditEmbedConsts.icon.value  # Looks a bit ugly being so large and redundant
    # if filter_action == constants.FilterActions.REMOVE:
    #     embed_thumbnail_link = RedditEmbedConsts.reddit_removed_thumbnail.value
    # elif filter_action == constants.FilterActions.MONITOR:
    #     embed_thumbnail_link = RedditEmbedConsts.reddit_monitor_thumbnail.value
    # embed.set_thumbnail(url=embed_thumbnail_link)

    image_match = constants.create_regex_string(RedditEmbedConsts.regex_matchers.value["image"])
    twitch_clip_match = constants.create_regex_string(RedditEmbedConsts.regex_matchers.value["twitch_clip"])
    youtube_match = constants.create_regex_string(RedditEmbedConsts.regex_matchers.value["youtube"])
    twitter_match = constants.create_regex_string(RedditEmbedConsts.regex_matchers.value["twitter"])

    followup_message = ""
    contains_image = re.match(image_match, post_content) is not None
    contains_twitch_clip = re.match(twitch_clip_match, post_content) is not None
    contains_youtube_video = re.match(youtube_match, post_content) is not None
    contains_twitter = re.match(twitter_match, post_content) is not None
    if is_submission_post:
        # Image embed set
        post_thumbnail = post["thumbnail"]
        embed_image_link = post_content if contains_image else post_thumbnail
        if "http" in embed_image_link and not contains_twitch_clip:
            embed.set_image(url=embed_image_link)
        # Twitch clip preview set
        if contains_twitch_clip or contains_twitter:
            followup_message = post_content

    # Formatting for the separate message contains the content for preview
    spacer = " | "
    if contains_twitch_clip or contains_youtube_video or contains_twitter:
        followup_message = message_footer + spacer + post_content

    embed.set_author(name=author_name,
                     url=embed_username_link,
                     icon_url="https://cdn.discordapp.com/embed/avatars/0.png")
    embed.set_footer(text=filter_name,
                     icon_url=RedditEmbedConsts.icon.value)

    output = {
        "embed": embed,
        "followup_message": followup_message
    }

    return output
