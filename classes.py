# Class constructor for a subreddit and its associated channels to send messages to
class SubredditAndChannels:
    def __init__(self, subreddit, main_channel_ids=None, post_channel_ids=None, comment_channel_ids=None,
                 ping_channel_ids=None, secondary_review_channel_ids=None, status_channel_ids=None,
                 report_channel_ids=None, embed_colour=0xc77d00, has_mod=False):
        if status_channel_ids is None:
            status_channel_ids = []
        if secondary_review_channel_ids is None:
            secondary_review_channel_ids = []
        if ping_channel_ids is None:
            ping_channel_ids = []
        if comment_channel_ids is None:
            comment_channel_ids = []
        if main_channel_ids is None:
            main_channel_ids = []
        if post_channel_ids is None:
            post_channel_ids = []
        if report_channel_ids is None:
            report_channel_ids = []
        self.subreddit = subreddit
        self.main_channel_ids = main_channel_ids
        self.post_channel_ids = post_channel_ids
        self.comment_channel_ids = comment_channel_ids
        self.report_channel_ids = report_channel_ids
        self.ping_channel_ids = ping_channel_ids
        self.secondary_review_channel_ids = secondary_review_channel_ids
        self.status_channel_ids = status_channel_ids
        self.embed_colour = embed_colour
        self.has_mod = has_mod
