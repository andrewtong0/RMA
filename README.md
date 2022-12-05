# RMA

![RMA Logo](https://i.imgur.com/g9qtToI.png)

Reddit Moderation Assistant, a Discord bot that provides a plethora of moderation functionality through Discord's interface.

[Check out RMA's features here!](https://andrewtong.me/RMA-Website/)

<details><summary>Setup Tutorial</summary>
  
MongoDB Basic Setup
1. Create a new project if you do not have one already
2. On the left menu, click "Database Access", then click "ADD NEW DATABASE USER"
3. Select the Authentication Method as "Password", set a username and password for the user and add the user - make note of the username and password as they will be necessary for the connection string
4. Go back to the clusters from the menu on the left and click "Create a New Cluster"
5. On the cluster you created, click the "CONNECT" button
6. Click "Connect using MongoDB Compass"
7. Copy the string and save this to a notepad - make sure to replace the username and password with the user you created (this is the database URI that we will need for our environment variables file)

Discord Bot Basic Setup
1. Log in to the Discord developer portal (https://discord.com/developers/applications)
2. Create a "New Application" and assign the application a name
3. Copy the Client ID to a notepad - we'll need it to invite the bot to your server
4. In the menu on the left, click the "Bot" tab, and click "Add Bot"
5. Copy down the bot's token from this page to a notepad - we'll need to add it to the environment variables later
6. In the following link, replace BOT_CLIENT_ID with the client ID you copied earlier (https://discordapp.com/oauth2/authorize?client_id=BOT_CLIENT_ID&scope=bot)
7. Invite the bot to your server
8. Assign the bot administrator privileges
9. Create any necessary Discord channels - here's an example layout of a server
```
# reddit-posts-and-comments    // Post stream of posts and comments go here
# reddit-filter-pings          // Anything caught by filters you specify will be sent here
# secondary-review             // Any posts that other moderators request secondary review for can be found here
```
10. If you do not already have Discord developer mode on, enable it
`User Settings > Appearance > Developer Mode`
11. Right click the channels you will be using and click "Copy ID" - store these IDs (along with what channel they refer to) for later (we'll need it for the user preferences file later)


Bot Setup Tutorial
1. Verify you have Python 3.7.x installed, the required MongoDB information, and the Discord Bot credentials (see above). Later versions of Python may not work.
2. Clone the repository
3. Navigate to the repository and install the required dependencies
`pip install -r requirements.txt`
4. Set the required information in environment_variables.py and user_preferences.py
```python
# environment_variables.py
DATABASE_URI - Your MongoDB database URI
REDDIT_CLIENT_ID - Reddit app client ID
REDDIT_CLIENT_SECRET - Reddit app secret
REDDIT_USER_AGENT - String describing the use for your Reddit app (e.g. "Reddit Discord Bot")
REDDIT_USER_USERNAME - Bot account username
REDDIT_USER_PASSWORD - Bot account password
LIVE_DISCORD_BOT_TOKEN - Discord bot token
DEV_DISCORD_BOT_TOKEN - You can ignore this unless you need a separate bot instance for development
PRIORITY_SUBREDDIT - Currently, only one subreddit can support filter sync. Since this is an advanced feature, most users can leave this string empty
HAS_MOD - Set this to True if your bot has moderator privileges in the subreddit (this is redundant to user_preferences and will hopefully be removed in a future commit)
DEV_MODE - Leave this as False unless you are using the bot for development purposes
```
```python
# user_preferences.py
ProdSubredditsAndChannels - Create instances of SubredditAndChannels - this is where you will need to insert the Discord channel IDs acquired from earlier (if you have difficulty with this, see below)
RegexFilters - Any filters that contain regex matches should have their filter names added here - any filters in this array will ensure regex phrases are valid and won't crash your bot instance
Settings.BOT_PREFIX - Specify the prefix for your bot to use
Settings.BOT_SECONDARY_REVIEW_ROLE - Specify the name of the Discord role to ping when a secondary review is requested - ensure your role name has no spaces
BotConsts.POLL_TIMER - The interval (in minutes) between subsequent polls for new posts/comments
```
5. Run the setup script (setup.py)
6. If the setup runs successfully, the bot should be ready to use.

</details>

## How and Why
With Reddit's new web design, moderation has become slow, clunky, and inconsistent. Additionally, our moderation teams communicate through Discord, and having our discussions in the same place as new post feeds creates a centralized location for moderation. It also allows for a live shared moderator queue where moderators can collaborate and work simultaneously to ensure actions aren't overlapped.

<details><summary>My rant about Reddit's current system</summary>

### Problems with Reddit's Moderator Functionality:
- **No Archiving:** If users delete their posts or comments, no history of what they said can be found. If bans are not extensively documented, users can delete their posts and feign innocence, and moderators will be forced to rely on themselves to remember why users were banned. Furthermore, edits on content are not documented and users can also conceal their actions by editing previous comments or posts.
- **No User Comments:** If moderators find troublesome users, there is no ability to tag users so other moderators know to watch out for them.
- **Clunky Interface:** Especially with new Reddit, posts can take several seconds to load. While this may seem trivial, it builds up, especially with large moderation queues.
- **Poor Moderator Action UX/UI:** Also trivial, moderator actions such as post removal/approval are not easily distinguishable among other actions (e.g. saving posts, hiding posts, etc.).
- **New Chat System Rushed:** Reddit also rolled out a new chat system to appeal to newer users, but there were plenty of shortcomings with its implementation. For one, there is no way to dismiss the new chat notification icon unless you either accept or deny the request. On paper this seems fine, but if you choose to deny the request, it automatically deletes the message logs the user has sent. For moderators, this is terrible because if a moderator chooses to ignore a message, they lose all message history. Furthermore, chat rooms are expected to be moderated, yet do not support automoderator filters, a significant issue making moderation very difficult.

### Stopgap Solutions to the above:
- **ceddit and removeddit:** There are sites that archive deleted posts and comments (assuming they have adequate time to archive them), but you cannot query by username, which is often useful for disputing ban appeals.
- **Reddit Enhancement Suite (RES):** RES is a fantastic browser extension that adds lots of helpful tools, including user comments. Unfortunately these only appear if other moderators have the 'Wiki' permission (which in my use case, one of ours didn't).
- **Old Reddit:** Old Reddit can still be used opposed to new Reddit, which has significantly faster loading times. However, the overall interface may be more intimidating to casual users.
</details>

## Features:
- **Live Feed:** Posts are periodically fetched and sent to the Discord channels that you specify.
- **Database Integration:** All posts and comments are stored in an external database. If users try to cover their tracks and delete their posts from Reddit, the copy remains within the database.
- **Custom Filter System:** RMA boasts a custom modular filter system. Select the type of content to catch, such as a use of inappropriate language, or posts from specific users, and an action to take upon finding a match. Incriminating content will be sent to a separate channel and will ping any roles that you specify for the filter along with a copy of the post and the details of the match.
- **User Report System:** View a Redditor's past posts and comments, add moderator comments to their profile, and more with a single command.
- **Intuitive Interface:** Click reacts on the messages sent by a bot to activate bot features. Generate user reports, get a list of negative comments from a post, flag a post or comment for secondary review, and more.
- **Secondary Review:** Flag a post for secondary review - it will be sent to a separate channel and ping anyone with the reviewer role. Upon the post being approved or rejected, the requester will be notified to know when they can proceed.
- **Automoderator Synchronization:** Watchlist and pseudo-shadowban lists implemented through automoderator can be synchronized with the bot. Add or remove users from such lislts through simple bot commands.
- **Database Catchup:** If the bot or any associated APIs go down, when the bot is able to reconnect, it will pull and store all posts missed during the downtime to ensure your database is complete and accurate.
- **Reddit Moderator Actions:** If RMA is provided with moderator privileges, you can remove, lock, and approve posts, using reacts on posts that show up through the live feed.

## Requirements:
- **MongoDB Database:** A MongoDB URI must be provided to store posts and conduct database commands.
- **Reddit API Credentials:** In order to query for posts, Reddit API credentials are required. If moderator functinos are also desired, you must also provide login credentials for an account with moderator privileges.
- **Discord Bot Credentials:** To host the Discord bot, you need a bot account set up with the appropriate credentials.
