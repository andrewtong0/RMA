# This file runs the initial setup for the bot

# Ensure that the necessary information has been filled out in environment_variables.py and user_preferences.py
# If there are any issues running this setup script, verify your provided information in the above files is valid

import environment_variables
import pymongo
import praw

# MONGODB INITIALIZATION
client = pymongo.MongoClient(environment_variables.DATABASE_URI)
db = client["reddit"]
metadata = db["metadata"]
comments = db["comments"]
filters = db["filters"]
submissions = db["submissions"]
users = db["users"]

null_object = {
    "name": "Initialization Object",
    "description": "Object to create collection. Once at least one entry exists in this collection, you can delete this object."
}
base_filter = {
    "platform": "reddit",
    "type": "users",
    "action": "monitor",
    "name": "Sample Filter",
    "parent": "",
    "description": "Sample filter to create collection. You can delete this filter once you have at least one in the collection.",
    "matches": [],
    "roles_to_ping": []
}
comments.insert_one(null_object)
filters.insert_one(base_filter)
submissions.insert_one(null_object)
users.insert_one(null_object)

metadata_object = {
    "name": "Ignore Buffer",
    "description": "Temporary buffer of manually fetched posts that should be ignored on periodic content queries.",
    "items": []
}
metadata.insert_one(metadata_object)
print("PyMongo Connection Successful")


# PRAW INITIALIZATION CHECK
reddit = praw.Reddit(client_id=environment_variables.REDDIT_CLIENT_ID,
                     client_secret=environment_variables.REDDIT_CLIENT_SECRET,
                     user_agent=environment_variables.REDDIT_USER_AGENT,
                     username=environment_variables.REDDIT_USER_USERNAME,
                     password=environment_variables.REDDIT_USER_PASSWORD,
                     redirect_uri="http://localhost:8080")
print("PRAW Logged in as: " + str(reddit.user.me()))
print("Initialization Complete - If PyMongo connected successfully and PRAW logged in, RMA should be ready to use.")
