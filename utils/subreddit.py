import json
import time
from os.path import exists

from utils import settings
from utils.ai_methods import sort_by_similarity
from utils.console import print_substep


def get_subreddit_undone(submissions: list, subreddit, times_checked=0, similarity_scores=None):
    """_summary_

    Args:
        submissions (list): List of posts that are going to potentially be generated into a video
        subreddit (praw.Reddit.SubredditHelper): Chosen subreddit

    Returns:
        Any: The submission that has not been done
    """
    # Second try of getting a valid Submission
    if times_checked and settings.config["ai"]["ai_similarity_enabled"]:
        print("Sorting based on similarity for a different date filter and thread limit..")
        submissions = sort_by_similarity(
            submissions, keywords=settings.config["ai"]["ai_similarity_enabled"]
        )

    # recursively checks if the top submission in the list was already done.
    if not exists("./video_creation/data/videos.json"):
        with open("./video_creation/data/videos.json", "w+") as f:
            json.dump([], f)
    with open("./video_creation/data/videos.json", "r", encoding="utf-8") as done_vids_raw:
        done_videos = json.load(done_vids_raw)
    
    print_substep("Checking submissions...")
    suitable_count = 0
    checked_count = 0
    for i, submission in enumerate(submissions):
        checked_count += 1
        if already_done(done_videos, submission):
            continue
        suitable_count += 1
        if submission.over_18:
            try:
                if not settings.config["settings"]["allow_nsfw"]:
                    print_substep("NSFW Post Detected. Skipping...")
                    continue
            except AttributeError:
                print_substep("NSFW settings not defined. Skipping NSFW post...")
        if submission.stickied:
            print_substep("This post was pinned by moderators. Skipping...")
            continue
        
        # Handle comment count requirements differently for different modes
        if settings.config["settings"].get("hybrid_mode", False):
            # For hybrid mode, use hybrid_comments_count but be more lenient
            min_comments_required = settings.config["settings"].get("hybrid_comments_count", 1)
            if submission.num_comments < min_comments_required:
                print_substep(f'Post has less than {min_comments_required} comments required for hybrid mode. Skipping...')
                continue
        elif not settings.config["settings"]["storymode"]:
            # For regular comment mode, use min_comments
            min_comments_required = int(settings.config["reddit"]["thread"]["min_comments"])
            if submission.num_comments < min_comments_required:
                print_substep(f'This post has under the specified minimum of comments ({min_comments_required}). Skipping...')
                continue
        # Story mode doesn't need comments, so no check needed
        if settings.config["settings"]["storymode"] or settings.config["settings"].get("hybrid_mode", False):
            # Check if there's text content - either in selftext or as a comment from OP
            has_text_content = bool(submission.selftext and len(submission.selftext.strip()) >= 30)
            
            if not has_text_content:
                # For non-self posts, check if OP made a comment explaining the post
                if not submission.is_self and submission.num_comments > 0:
                    try:
                        # Look for a comment from the original poster
                        for comment in submission.comments.list()[:5]:  # Check first 5 comments
                            if hasattr(comment, 'author') and comment.author and str(comment.author) == str(submission.author):
                                if len(comment.body.strip()) >= 30:
                                    print_substep(f"Found OP comment with content: '{submission.title[:50]}...'")
                                    has_text_content = True
                                    break
                    except:
                        pass  # Skip if we can't access comments
            
            if not has_text_content:
                print_substep(f"Skipping post '{submission.title[:50]}...' - no sufficient text content")
                # Mark posts without text as done so they don't get picked up again  
                with open("./video_creation/data/videos.json", "r+", encoding="utf-8") as raw_vids:
                    done_videos = json.load(raw_vids)
                    payload = {
                        "subreddit": str(submission.subreddit),
                        "id": str(submission.id),
                        "time": str(int(time.time())),
                        "background_credit": "SKIPPED_NO_TEXT",
                        "reddit_title": submission.title,
                        "filename": "SKIPPED_NO_TEXT",
                    }
                    done_videos.append(payload)
                    raw_vids.seek(0)
                    json.dump(done_videos, raw_vids, ensure_ascii=False, indent=4)
                continue
            else:
                # Check for the length of the post text (if it's selftext)
                if submission.selftext and len(submission.selftext) > (
                    settings.config["settings"]["storymode_max_length"] or 2000
                ):
                    print_substep(
                        f"Post is too long ({len(submission.selftext)}), try with a different post. ({settings.config['settings']['storymode_max_length']} character limit)"
                    )
                    continue
        
        # If we've reached this point, the post passed all filters!
        print_substep(f"Found suitable post: '{submission.title[:50]}...' with {submission.num_comments} comments")
        if similarity_scores is not None:
            return submission, similarity_scores[i].item()
        return submission
    
    # No suitable submissions found in current filter
    print_substep(f"Checked {checked_count} posts, found {suitable_count} new posts, but none were suitable for hybrid mode.")
    VALID_TIME_FILTERS = [
        "day",
        "hour", 
        "month",
        "week",
        "year",
        "all",
    ]
    index = times_checked + 1
    if index >= len(VALID_TIME_FILTERS):
        print("All submissions have been processed. No suitable posts found.")
        return None

    # Try next time filter
    print_substep(f"Trying {VALID_TIME_FILTERS[index]} time filter...")
    return get_subreddit_undone(
        subreddit.top(
            time_filter=VALID_TIME_FILTERS[index],
            limit=(50 if int(index) == 0 else index + 1 * 50),
        ),
        subreddit,
        times_checked=index,
    )


def already_done(done_videos: list, submission) -> bool:
    """Checks to see if the given submission is in the list of videos

    Args:
        done_videos (list): Finished videos
        submission (Any): The submission

    Returns:
        Boolean: Whether the video was found in the list
    """

    for video in done_videos:
        if video["id"] == str(submission):
            return True
    return False
