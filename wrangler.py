import constants
import datetime
import discord
import re

import user_preferences
import environment_variables


def generate_reddit_user_link(username):
    return constants.RedditEmbedConsts.username_link.value + username


def is_post_submission(post):
    return post["post_type"] == constants.PostTypes.REDDIT_SUBMISSION.value


def post_utc_to_timestamp(post):
    return datetime.datetime.utcfromtimestamp(post["created_time"]["utc"])


# Checks if number of characters has exceeded embed character limit
def exceeds_embed_char_limit(num_chars):
    return num_chars > constants.CharacterLimits.EMBED_TOTAL_CHARS.value


# Given two limits (usually total char limit and another), truncate based on whichever is hit first
def truncate_string_on_lower_limit(string, limit1, limit2):
    if limit1 < limit2:
        return string[:limit1]
    else:
        return string[:limit2]


# If string exceeds max num characters for embed of the section-specific limit, truncate
def truncate_embed_string_if_necessary(string, num_chars_so_far, string_char_limit):
    string_len = len(string)
    truncate_string = constants.StringConstants.STRING_TRUNCATE.value
    truncate_string_len = len(truncate_string)

    if exceeds_embed_char_limit(num_chars_so_far + string_len) or string_len > string_char_limit:
        string = truncate_string_on_lower_limit(
            string,
            constants.CharacterLimits.EMBED_TOTAL_CHARS.value - num_chars_so_far - truncate_string_len,
            string_char_limit - truncate_string_len
        )
        string += truncate_string
    return string


# Removes fields from embed between ranges i1 and i2
def remove_fields_in_range(embed, i1, i2):
    upper_range = i2
    lower_range = i1 - 1
    for index in range(lower_range, upper_range):
        # Index to remove since list shortens as items are removed, so must be done from back end
        index_to_remove = upper_range + lower_range - index
        embed.remove_field(index_to_remove)


# Depending on the action type, will truncate embed to not hit character limit and return the embed and an additional
#    information message in case another action was taken to provide context
def truncate_embed(embed, action=constants.MessageLimitActions.TRUNCATE):
    additional_info = ""

    # Rolling value for embed length, updated in order of importance (so important values aren't truncated early)
    num_chars_so_far = 0

    # If the embed title exceeds the limit
    embed.title = truncate_embed_string_if_necessary(embed.title, num_chars_so_far, constants.CharacterLimits.EMBED_TITLE.value)
    # Note: Do not store len(embed.title) in a variable since the value is updated due to truncation and may change
    num_chars_so_far += len(embed.title)

    # If the embed description exceeds the limit
    embed.description = truncate_embed_string_if_necessary(embed.description, num_chars_so_far, constants.CharacterLimits.EMBED_DESCRIPTION.value)
    num_chars_so_far += len(embed.description)

    # If the author name exceeds limit
    embed.set_author(name=truncate_embed_string_if_necessary(embed.author.name, num_chars_so_far, constants.CharacterLimits.EMBED_AUTHOR.value),
                     url=embed.author.url,
                     icon_url=embed.author.icon_url)
    num_chars_so_far += len(embed.author.name)

    # If the footer exceeds limit
    embed.set_footer(text=truncate_embed_string_if_necessary(embed.footer.text, num_chars_so_far, constants.CharacterLimits.EMBED_FOOTER.value),
                     icon_url=embed.footer.icon_url)
    num_chars_so_far += len(embed.footer.text)

    # If the character limit of the fields along with title/description exceed limit, take action on fields
    fields = embed.fields
    if len(fields) > 0:
        # TODO: This currently doesn't do anything anymore since the additional_info is attached now
        # Reserve characters for truncate string just in case
        num_chars_so_far += len(constants.StringConstants.EMBED_FIELD_TRUNCATE_MESSAGE.value) + constants.StringConstants.EMBED_FIELD_TRUNCATE_NUMBER.value

        # Preliminary check to see if number of fields exceeds limit
        if len(fields) > constants.CharacterLimits.EMBED_NUM_FIELDS.value:
            remove_fields_in_range(embed, constants.CharacterLimits.EMBED_NUM_FIELDS.value + 1, len(fields))
            fields = embed.fields  # Update count after removing extras

        # Check over all fields and ensure field character limits are met
        for index in range(len(fields)):
            field = fields[index]

            field_name = truncate_embed_string_if_necessary(field.name, num_chars_so_far, constants.CharacterLimits.EMBED_FIELD_NAME.value)
            num_chars_so_far += len(field_name)
            field_value = truncate_embed_string_if_necessary(field.value, num_chars_so_far, constants.CharacterLimits.EMBED_FIELD_VALUE.value)
            num_chars_so_far += len(field_value)
            embed.set_field_at(index=index,
                               name=field_name,
                               value=field_value,
                               inline=field.inline)

            # If after taking into account this field we exceed limit, truncate current and additional fields
            if num_chars_so_far >= constants.CharacterLimits.EMBED_TOTAL_CHARS.value:
                # TRUNCATE: Remove all additional fields including this one and list how many more remaining
                if action == constants.MessageLimitActions.TRUNCATE:
                    remove_fields_in_range(embed, index, len(fields))
                    additional_info = constants.StringConstants.EMBED_FIELD_TRUNCATE_MESSAGE.value.format(len(fields) - index - 1)
                    break
                # TODO: Implement additional truncation methods
                # elif action == constants.MessageLimitActions.MULTI:
                # elif action == constants.MessageLimitActions.PAGINATE:
    return {
        "embed": embed,
        "additional_info": additional_info
    }


def get_subreddit_colour(subreddit):
    subreddits_and_channels = user_preferences.DevSubredditsAndChannels if environment_variables.DEV_MODE else user_preferences.ProdSubredditsAndChannels
    for subreddit_and_channels in subreddits_and_channels:
        if subreddit_and_channels.subreddit == subreddit:
            return subreddit_and_channels.embed_colour


# TODO: Refactor this into two separate functions, one for post and one for comments? Unless too much duplication, but then maybe build a base of the message then pass in as a param
def construct_reddit_message(subreddit, post, triggered_matches):
    is_submission_post = is_post_submission(post)
    post_content = post["content"]

    # TODO: Tidy this up, currently very messy
    # Add post flair if submission post
    post_flair_raw = ""
    if is_submission_post and "extra_info" in post.keys():
        post_flair_raw = post["extra_info"]["initial_flair"] if post["extra_info"]["initial_flair"] is not None else "UNFLAIRED"
    post_flair = "[" + post_flair_raw + "] " if is_submission_post else ""

    embed_title = post_flair + post["title"] if is_submission_post else post["author"]["username"] + " commented on a post"
    embed_message_body = post_content
    embed_timestamp = post_utc_to_timestamp(post)

    author_name = post["author"]["username"]
    embed_username_link = generate_reddit_user_link(author_name)
    author_icon = post["author"]["author_icon"]

    embed_colour = get_subreddit_colour(subreddit)
    if embed_colour is None:
        embed_colour = discord.Colour(constants.RedditEmbedConsts.post_colour.value) if is_submission_post else discord.Colour(
            constants.RedditEmbedConsts.comment_colour.value)

    embed = discord.Embed(
        title=embed_title,
        colour=embed_colour,
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
        filter_name_matches += match["filter"]["name"] + ", "
    filter_name_matches = filter_name_matches[:-2]

    # Footer message should contain concatenation of filters hit, and post ID
    id_prefix = constants.StringConstants.SUBMISSION_ID.value if is_submission_post else constants.StringConstants.COMMENT_ID.value
    footer_content = "r/" + subreddit + " | " + filter_name_matches + " | " + id_prefix + post["_id"]

    # embed_thumbnail_link = constants.RedditEmbedConsts.icon.value  # Looks a bit ugly being so large and redundant
    # if filter_action == constants.FilterActions.REMOVE:
    #     embed_thumbnail_link = constants.RedditEmbedConsts.reddit_removed_thumbnail.value
    # elif filter_action == constants.FilterActions.MONITOR:
    #     embed_thumbnail_link = constants.RedditEmbedConsts.reddit_monitor_thumbnail.value
    # embed.set_thumbnail(url=embed_thumbnail_link)

    # Checking to see what kind of content is contained to determine how to display
    image_match = constants.create_regex_string(constants.RedditEmbedConsts.regex_matchers.value["image"])
    twitch_clip_match = constants.create_regex_string(constants.RedditEmbedConsts.regex_matchers.value["twitch_clip"])
    youtube_match = constants.create_regex_string(constants.RedditEmbedConsts.regex_matchers.value["youtube"])
    twitter_match = constants.create_regex_string(constants.RedditEmbedConsts.regex_matchers.value["twitter"])

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
                     icon_url=constants.RedditEmbedConsts.icon.value)

    embed = truncate_embed(embed)["embed"]

    output = {
        "embed": embed,
        "followup_message": followup_message
    }

    return output


def construct_user_report_embed(user_posts, username, user_data):
    user_karma = get_user_karma(user_data)
    tags_string = get_user_tags(user_data)

    embed = discord.Embed(
        title=("User Report for {}".format(username)),
        colour=discord.Colour(constants.RedditEmbedConsts.post_colour.value),
        url=generate_reddit_user_link(username),
        description=("Karma: {} / Tags: {}".format(str(user_karma), tags_string))
    )

    # Add moderator comments to embed
    embed = add_mod_comment_embed_fields(embed, user_data)

    for post in user_posts:
        is_submission_post = is_post_submission(post)
        embed.add_field(
            name=constants.StringConstants.STRING_POST.value if is_submission_post else constants.StringConstants.STRING_COMMENT.value,
            value=post["title"] if is_submission_post else post["content"],
            inline=True
        )
        embed.add_field(
            name="Permalink" + " (ID: " + post["_id"] + ")",
            value=post["permalink"],
            inline=True
        )
        embed.add_field(
            name=constants.StringConstants.TIMESTAMP_TITLE.value,
            value=str(post_utc_to_timestamp(post)),
            inline=True
        )

    embed.set_author(name=constants.BotAuthorDetails.NAME.value,
                     icon_url=constants.BotAuthorDetails.ICON_URL.value)

    embed = truncate_embed(embed)["embed"]
    return embed


def construct_user_moderator_comments_embed(user_data, username):
    user_karma = get_user_karma(user_data)
    tags_string = get_user_tags(user_data)

    embed = discord.Embed(
        title=("User Report for {}".format(username)),
        colour=discord.Colour(constants.RedditEmbedConsts.post_colour.value),
        url=generate_reddit_user_link(username),
        description=("Karma: {} / Tags: {}".format(str(user_karma), tags_string))
    )

    # Add moderator comments to embed
    embed = add_mod_comment_embed_fields(embed, user_data)

    embed.set_author(name=constants.BotAuthorDetails.NAME.value,
                     icon_url=constants.BotAuthorDetails.ICON_URL.value)

    embed = truncate_embed(embed)["embed"]
    return embed


def get_user_karma(user_data):
    return user_data["comment_karma"] + user_data["link_karma"]


def get_user_tags(user_data):
    tags = user_data["tags"]
    tags_string = ""
    for tag in tags:
        tags_string += tag + ", "
    tags_string = tags_string[:-2]
    if tags_string == "":
        tags_string = "(None)"
    return tags_string


def add_mod_comment_embed_fields(embed, user_data):
    mod_comments = user_data["mod_comments"]
    for comment in mod_comments:
        mod_comment_author = comment["author"]["name"]
        mod_comment_timestamp = comment["timestamp"]
        embed.add_field(
            name="[CID: {}] Moderator Comment/ Added by @{} / {}".format(
                str(mod_comments.index(comment)),
                mod_comment_author,
                mod_comment_timestamp.strftime("%Y-%m-%d %H:%M")
            ),
            value=comment["comment"],
            inline=False
        )
    return embed


# Constructs an embed to show when no user is found
def construct_user_not_found_embed(username):
    embed = discord.Embed(
        title="Error: User not found",
        colour=discord.Colour(constants.RedditEmbedConsts.error_colour.value),
        url=generate_reddit_user_link(username),
        description="The user you tried to query for could not be found. Please check the associated link and verify the account is not banned or suspended."
    )
    return embed


def construct_negative_comment_tree_embed(submission, comments):
    embed = discord.Embed(
        title=submission.title,
        colour=discord.Colour(constants.RedditEmbedConsts.post_colour.value),
        url=constants.RedditEmbedConsts.permalink_domain.value + submission.permalink
    )
    embed.set_author(name="Negative Comment Tree")

    for comment in comments:
        author = comment.author.name
        author_link = constants.RedditEmbedConsts.username_link.value + author
        comment_link = constants.RedditEmbedConsts.permalink_domain.value + comment.permalink
        links = "[Profile]({}) | [Comment Link]({})".format(author_link, comment_link)
        body = comment.body + "\n" + links

        name_and_karma = "[" + str(comment.score) + "] " + author
        embed.add_field(name=name_and_karma,
                        value=body,
                        inline=False)
    embed_and_info = truncate_embed(embed)
    return embed_and_info


async def add_user_reacts_to_string(reaction, vote_icon_string, bot_uuid):
    users = await reaction.users().flatten()
    current_string = ""
    for user in users:
        if user.id != bot_uuid:
            current_string += vote_icon_string + " " + user.name + "\n"
    return current_string


async def get_vote_score_and_string(reactions, bot_uuid):
    upvote_emoji = constants.RedditReactEmojis.SECONDARY_REVIEW_UPVOTE.value
    downvote_emoji = constants.RedditReactEmojis.SECONDARY_REVIEW_DOWNVOTE.value
    vote_score = 0
    vote_string = ""
    for reaction in reactions:
        reaction_emoji = reaction.emoji
        if reaction_emoji == upvote_emoji or reaction_emoji == downvote_emoji:
            if reaction_emoji == upvote_emoji:
                vote_score += reaction.count
                vote_string += await add_user_reacts_to_string(reaction, "[+1]", bot_uuid)
            elif reaction_emoji == downvote_emoji:
                vote_score -= reaction.count
                vote_string += await add_user_reacts_to_string(reaction, "[-1]", bot_uuid)
    return {
        "vote_score": vote_score,
        "vote_string": vote_string
    }


async def construct_approve_or_reject_review_embed(reviewed_post_embed, review_requester, review_fulfiller, is_approved, reactions, bot_uuid):
    embed_colour = 0
    status_result = ""
    if is_approved:
        embed_colour = constants.RedditEmbedConsts.approve_colour.value
        status_result = constants.RedditReactEmojis.SECONDARY_REVIEW_APPROVE.value + " Approved"
    else:
        embed_colour = constants.RedditEmbedConsts.reject_colour.value
        status_result = constants.RedditReactEmojis.SECONDARY_REVIEW_REJECT.value + " Rejected"

    embed_description = reviewed_post_embed.description
    embed = discord.Embed(
        title=status_result + " | " + reviewed_post_embed.title,
        description=embed_description,
        colour=discord.Colour(embed_colour),
        url=reviewed_post_embed.url
    )
    embed.add_field(
        name="Review Requested By:",
        value=review_requester,
        inline=True
    )
    embed.add_field(
        name="Review Fulfilled By:",
        value=review_fulfiller,
        inline=True
    )

    vote_results = await get_vote_score_and_string(reactions, bot_uuid)
    if vote_results["vote_score"] != 0:
        embed.add_field(
            name="Vote Results ({}):".format(vote_results["vote_score"]),
            value=vote_results["vote_string"],
            inline=True
        )

    embed.set_author(
        name="Secondary Review Status"
    )
    embed = truncate_embed(embed)["embed"]
    return embed


# TODO: Make this not split words into two, escape characters (or perhaps just make it a code block)
# Return array of truncated strings to bypass character limit as several messages sent as code blocks
def truncate_message_into_code_blocks(message):
    output_messages = []
    char_limit = constants.CharacterLimits.REGULAR_MESSAGE.value
    code_block_indicator = constants.StringConstants.TRUNCATE_CODE_BLOCK_CHARS.value
    code_block_indicator_len = len(code_block_indicator)

    # TODO: This can be tidied up to not use a conditional
    if len(message) + code_block_indicator_len * 2 > char_limit:
        remaining_message = message
        while len(remaining_message) + code_block_indicator_len * 2 > char_limit:
            truncated_messages = truncate_message_helper(remaining_message, char_limit)
            output_messages.append(truncated_messages[0])
            remaining_message = truncated_messages[len(truncated_messages) - 1]
        if remaining_message not in output_messages:
            output_messages.append(code_block_indicator + remaining_message + code_block_indicator)
    else:
        message = code_block_indicator + message + code_block_indicator
        output_messages = [message]
    return output_messages


# Returns 2 strings, one that hits character limit, and one as remaining characters
def truncate_message_helper(message, char_limit):
    code_block_indicator = constants.StringConstants.TRUNCATE_CODE_BLOCK_CHARS.value
    if len(message) + len(code_block_indicator) * 2 > char_limit:
        char_limit_with_code_indicators = char_limit - len(code_block_indicator) * 2
        verified_message = code_block_indicator + message[:char_limit_with_code_indicators] + code_block_indicator
        return [verified_message, message[char_limit_with_code_indicators:]]
    else:
        verified_message = code_block_indicator + message + code_block_indicator
        return [verified_message]
