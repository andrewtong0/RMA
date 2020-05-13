import re
import constants
from enum import Enum

string = " https://preview.redd.it/0xa34e5iuwj41.jpg?auto=webp&s=0c92b4b2ca5c3d85155ccd9a5d8b51781c943330 "
# matching_strings = ["external-{1}preview.{1}redd.{1}it", "preview.{1}redd.{1}it"]
# matching_strings = ["external\\-preview\\.redd\\.it", "preview\\.redd\\.it"]

class Constants(Enum):
    regex_matchers = {
        "image": ["external\\-preview\\.redd\\.it", "preview\\.redd\\.it"]
    }


image_match = constants.create_regex_string(Constants.regex_matchers.value["image"])
match = re.match(image_match, string)
if match:
    print("Match found")
else:
    print("No match found")
print(image_match)