from typing import Optional

import json
import time

from praw.models import Submission

from utils import settings
from utils.console import print_step


def check_done(
    redditobj: Submission, mark_as_done: bool = False
) -> Optional[Submission]:
    # don't set this to be run anyplace that isn't subreddit.py bc of inspect stack
    """Checks if the chosen post has already been generated

    Args:
        redditobj (Submission): Reddit object gotten from reddit/subreddit.py
        mark_as_done (bool): If true, the post will be marked as done and skipped

    Returns:
        Submission|None: Reddit object in args
    """
    with open("./video_creation/data/videos.json", "r+", encoding="utf-8") as raw_vids:
        done_videos = json.load(raw_vids)
        for video in done_videos:
            if video["id"] == str(redditobj.id):
                if settings.config["reddit"]["thread"]["post_id"]:
                    print_step(
                        "You already have done this video but since it was declared specifically in the config file the program will continue"
                    )
                    return redditobj
                print_step("Getting new post as the current one has already been done")
                return None

        if mark_as_done:
            payload = {
                "subreddit": str(redditobj.subreddit),
                "id": str(redditobj.id),
                "time": str(int(time.time())),
                "background_credit": "SKIPPED",
                "reddit_title": redditobj.title,
                "filename": "SKIPPED",
            }
            done_videos.append(payload)
            raw_vids.seek(0)
            json.dump(done_videos, raw_vids, ensure_ascii=False, indent=4)
            return None

    return redditobj


def save_data(subreddit: str, filename: str, reddit_title: str, reddit_id: str, credit: str):
    """Saves the videos that have already been generated to a JSON file in video_creation/data/videos.json

    Args:
        filename (str): The finished video title name
        @param subreddit:
        @param filename:
        @param reddit_id:
        @param reddit_title:
    """
    with open("./video_creation/data/videos.json", "r+", encoding="utf-8") as raw_vids:
        done_vids = json.load(raw_vids)
        if reddit_id in [video["id"] for video in done_vids]:
            return  # video already done but was specified to continue anyway in the config file
        payload = {
            "subreddit": subreddit,
            "id": reddit_id,
            "time": str(int(time.time())),
            "background_credit": credit,
            "reddit_title": reddit_title,
            "filename": filename,
        }
        done_vids.append(payload)
        raw_vids.seek(0)
        json.dump(done_vids, raw_vids, ensure_ascii=False, indent=4)
