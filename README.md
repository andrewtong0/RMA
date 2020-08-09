# RMA
Reddit Moderation Assistant, a Discord bot that provides a plethora of moderation functionality through Discord's interface.

## How and Why
With Reddit's new web design, moderation has become slow, clunky, and inconsistent. Additionally, our moderation teams communicate through Discord, and having our discussions in the same place as new post feeds creates a centralized location for moderation. It also allows for a live shared moderator queue where moderators can collaborate and work simultaneously to ensure actions aren't overlapped.

### Problems with Reddit's Moderator Functionality:
- **No Archiving:** If users delete their posts or comments, no history of what they said can be found. If bans are not extensively documented, users can delete their posts and feign innocence, and moderators will be forced to rely on themselves to remember why users were banned. Furthermore, edits on content are not documented and users can also conceal their actions by editing previous comments or posts.
- **No User Comments:** If moderators find troublesome users, there is no ability to tag users so other moderators know to watch out for them.
- **Clunky Interface:** Especially with new Reddit, posts can take several seconds to load. While this may seem trivial, it builds up, especially with large moderation queues.
- **Poor Moderator Action UX/UI:** Also trivial, moderator actions such as post removal/approval are not easily distinguishable among other actions (e.g. saving posts, hiding posts, etc.).

### Stopgap Solutions to the above:
- **ceddit and removeddit:** There are sites that archive deleted posts and comments (assuming they have adequate time to archive them), but you cannot query by username, which is often useful for disputing ban appeals.
- **Reddit Enhancement Suite (RES):** RES is a fantastic browser extension that adds lots of helpful tools, including user comments. Unfortunately these only appear if other moderators have the 'Wiki' permission (which in my use case, one of ours didn't).
- **Old Reddit:** Old Reddit can still be used opposed to new Reddit, which has significantly faster loading times. However, the overall interface may be more intimidating to casual users.

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

## Roadmap:
- **Standalone Client?** Potential for a standalone client to manage this, external from Discord.
