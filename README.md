# RMA
Reddit Moderation Assistant, a Discord bot that provides a plethora of functionality that Reddit moderation tools are missing

## Features:
- **Live Feed:** All posts and comments are sent to Discord channels, Choose between a general channel that displays both posts and comments, individual post/comment channels, channels for only pings due to filters.
- **Database Integration:** RMA stores all found comments and posts into a separate database. If a user deletes their post or comment, the content will still be stored and associated to the user for reference.
- **Custom Filter System:** Specify the filter type (e.g. content regex, username match, YouTube channel source match), an associated Discord role to ping when a match is found, and an action to take when the match is found. Change the list of potential matches for a filter on the fly with chat commands.
- **User Report System:** Generate a user report based on the posts found within the database, add moderator comments or links to previous posts to their user report.
- **Intuitive Reacts:** Click reacts generated on posts and comments to generate user reports, get a comment tree of all negative comments on a post, flag a post or comment for secondary review, or add a post to a the user's report.
- **Secondary Review:** Flag a post to placed under secondary review - the post/comment will be sent to a separate channel and will ping anyone with the associated role. It can then be either approved or rejected, which will ping the user that requested the secondary review so that they know hwo to proceed.
- **Automoderator Modifications:** Functionality to add or remove users from automoderator watchlists or shadowban lists.
- **Database Catchup:** If the bot or any associated APIs go down, when the bot is able to reconnect, it will pull and store all posts missed during the downtime to ensure your database is complete and accurate.
- **Reddit Moderator Actions:** If the bot is provided with moderator privileges, you can remove, lock, and approve posts, all directly from Discord using reacts. When an action is done via the provided reacts, the embed title is updated to show any actions taken so other moderators scrolling through the queue don't conflict with your actions.

## Requirements:
- **MongoDB Database:** A MongoDB URI must be provided to store posts and conduct database commands.
- **Reddit API Credentials:** In order to query for posts, Reddit API credentials are required. If moderator functinos are also desired, you must also provide login credentials for an account with moderator privileges.
- **Discord Bot Credentials:** To host the Discord bot, you need a bot account set up with the appropriate credentials.

## Roadmap:
- **Standalone Client?** Potential for a standalone client to manage this, external from Discord.
