import re


def strip_tags(text):
    clean = re.compile("<.*?>")
    return re.sub(clean, "", text)