import constants
import datetime
import discord
import re
from enum import Enum


class RedditEmbedConsts(Enum):
    post_colour = 0xc77d00
    comment_colour = 0xfbff00
    error_colour = 0xff0000
    removed_thumbnail = "https://cdn4.iconfinder.com/data/icons/social-messaging-ui-coloricon-1/21/52-512.png"
    monitor_thumbnail = "https://c7.uihere.com/files/928/549/87/magnifying-glass-computer-icons-magnification-loupe.jpg"
    icon = "https://www.redditstatic.com/desktop2x/img/favicon/android-icon-192x192.png"
    username_link = "https://reddit.com/u/"
    regex_matchers = {
        "image": ["external\\-preview\\.redd\\.it", "preview\\.redd\\.it", "i\\.redd\\.it", "pbs\\.twimg\\.com"],
        "twitch_clip": ["twitch\\.tv"],
        "youtube": ["youtube\\.com"],
        "twitter": ["twitter\\.com"]
    }


def generate_reddit_user_link(username):
    return RedditEmbedConsts.username_link.value + username


def is_post_submission(post):
    return post["post_type"] == constants.DbEntry.REDDIT_SUBMISSION.value


def post_utc_to_timestamp(post):
    return datetime.datetime.utcfromtimestamp(post["created_time"]["utc"])


# TODO: Refactor this into two separate functions, one for post and one for comments? Unless too much duplication, but then maybe build a base of the message then pass in as a param
def construct_reddit_message(subreddit, post, triggered_matches, message_prefix, message_suffix):
    string_truncate = constants.StringConstants.STRING_TRUNCATE.value
    is_submission_post = is_post_submission(post)
    post_content = post["content"]
    embed_title = post["title"] if is_submission_post else post["author"]["username"] + " commented on a post"
    embed_message_body_raw = post_content[:constants.Restrictions.EMBED_BODY_CHAR_MAX.value - len(string_truncate) - len(message_prefix) - len(message_suffix)] + string_truncate if len(post_content) >= constants.Restrictions.EMBED_BODY_CHAR_MAX.value else post_content
    embed_message_body = message_prefix + "\n" + embed_message_body_raw + "\n" + message_suffix
    embed_timestamp = post_utc_to_timestamp(post)

    author_name = post["author"]["username"]
    embed_username_link = generate_reddit_user_link(author_name)
    author_icon = post["author"]["author_icon"]

    embed = discord.Embed(
        title=(embed_title[:constants.Restrictions.TITLE_CHAR_MAX.value - len(string_truncate)] + "...")
        if len(embed_title) > constants.Restrictions.TITLE_CHAR_MAX.value else embed_title,
        colour=discord.Colour(RedditEmbedConsts.post_colour.value) if is_submission_post else discord.Colour(RedditEmbedConsts.comment_colour.value),
        url=post["permalink"],
        description=embed_message_body,
        timestamp=embed_timestamp
    )

    # Generate content based on triggered filter matches
    # Generate string of names of all matches hit
    filter_name_matches = ""
    # From the triggered_matches, we should only be operating on "flavour" information here (does not affect
    #   functionality). Logical operations should go in the loop on triggered_matches in discord_bot
    for match in triggered_matches:
        filter_name_matches += " | " + match["filter"]["name"] + " "

    # Footer message should contain concatenation of filters hit, and post ID
    footer_content = "r/" + subreddit + " | " + filter_name_matches + " | Post ID: " + post["_id"]

    # embed_thumbnail_link = RedditEmbedConsts.icon.value  # Looks a bit ugly being so large and redundant
    # if filter_action == constants.FilterActions.REMOVE:
    #     embed_thumbnail_link = RedditEmbedConsts.reddit_removed_thumbnail.value
    # elif filter_action == constants.FilterActions.MONITOR:
    #     embed_thumbnail_link = RedditEmbedConsts.reddit_monitor_thumbnail.value
    # embed.set_thumbnail(url=embed_thumbnail_link)

    # Checking to see what kind of content is contained to determine how to display
    image_match = constants.create_regex_string(RedditEmbedConsts.regex_matchers.value["image"])
    twitch_clip_match = constants.create_regex_string(RedditEmbedConsts.regex_matchers.value["twitch_clip"])
    youtube_match = constants.create_regex_string(RedditEmbedConsts.regex_matchers.value["youtube"])
    twitter_match = constants.create_regex_string(RedditEmbedConsts.regex_matchers.value["twitter"])

    # Followup message is used in cases that require non-embed to display preview
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
        if contains_twitch_clip or contains_twitter or contains_twitch_clip or contains_youtube_video or contains_twitter:
            followup_message = post_content

    embed.set_author(name=author_name,
                     url=embed_username_link,
                     icon_url=author_icon)
    embed.set_footer(text=footer_content,
                     icon_url=RedditEmbedConsts.icon.value)

    output = {
        "embed": embed,
        "followup_message": followup_message
    }

    return output


def construct_user_report_embed(user_posts, username, user_data):
    tags = user_data["tags"]
    mod_comments = user_data["mod_comments"]
    user_karma = user_data["comment_karma"] + user_data["link_karma"]

    tags_string = ""
    for tag in tags:
        tags_string += tag + ", "
    tags_string = tags_string[:-2]
    if tags_string == "":
        tags_string = "(None)"

    embed = discord.Embed(
        title=("User Report for {}".format(username)),
        colour=discord.Colour(RedditEmbedConsts.post_colour.value),
        url=generate_reddit_user_link(username),
        description=("Karma: {} / Tags: {}".format(str(user_karma), tags_string))
    )

    for post in user_posts:
        is_submission_post = is_post_submission(post)
        embed.add_field(
            name=constants.StringConstants.STRING_POST.value if is_submission_post else constants.StringConstants.STRING_COMMENT.value,
            value=post["title"] if is_submission_post else post["content"],
            inline=True
        )
        embed.add_field(
            name="Permalink",
            value=post["permalink"],
            inline=True
        )
        embed.add_field(
            name=constants.StringConstants.TIMESTAMP_TITLE.value,
            value=str(post_utc_to_timestamp(post)),
            inline=True
        )

    for comment in mod_comments:
        mod_comment_author = comment["author"]["name"]
        mod_comment_timestamp = comment["timestamp"]
        embed.add_field(
            name="Moderator Comment / Added by @{} / {}".format(mod_comment_author, mod_comment_timestamp),
            value=comment["comment"]
        )

    return embed


# Constructs an embed to show when no user is found
def construct_user_not_found_embed(username):
    embed = discord.Embed(
        title="Error: User not found",
        colour=discord.Colour(RedditEmbedConsts.error_colour.value),
        url=generate_reddit_user_link(username),
        description="The user you tried to query for could not be found. Please check the associated link and verify the account is not banned or suspended."
    )
    return embed
