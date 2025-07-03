import re

import praw
from praw.models import MoreComments
from prawcore.exceptions import ResponseException

from utils import settings
from utils.ai_methods import sort_by_similarity
from utils.console import print_step, print_substep
from utils.posttextparser import posttextparser
from utils.subreddit import get_subreddit_undone
from utils.videos import check_done
from utils.voice import sanitize_text


def get_subreddit_threads(POST_ID: str):
    """
    Returns a list of threads from the AskReddit subreddit.
    """

    print_substep("Logging into Reddit.")

    content = {}
    if settings.config["reddit"]["creds"]["2fa"]:
        print("\nEnter your two-factor authentication code from your authenticator app.\n")
        code = input("> ")
        print()
        pw = settings.config["reddit"]["creds"]["password"]
        passkey = f"{pw}:{code}"
    else:
        passkey = settings.config["reddit"]["creds"]["password"]
    username = settings.config["reddit"]["creds"]["username"]
    if str(username).casefold().startswith("u/"):
        username = username[2:]
    reddit = None
    try:
        reddit = praw.Reddit(
            client_id=settings.config["reddit"]["creds"]["client_id"],
            client_secret=settings.config["reddit"]["creds"]["client_secret"],
            user_agent="Accessing Reddit threads",
            username=username,
            passkey=passkey,
            check_for_async=False,
        )
    except ResponseException as e:
        if e.response.status_code == 401:
            print("Invalid credentials - please check them in config.toml")
        exit()
    except Exception as e:
        print(f"Something went wrong: {e}")
        exit()

    if not reddit:
        print("Failed to initialize Reddit instance. Exiting.")
        exit()

    # Ask user for subreddit input
    print_step("Getting subreddit threads...")
    similarity_score = 0
    if not settings.config["reddit"]["thread"][
        "subreddit"
    ]:  # note to user. you can have multiple subreddits via reddit.subreddit("redditdev+learnpython")
        try:
            subreddit = reddit.subreddit(
                re.sub(r"r\/", "", input("What subreddit would you like to pull from? "))
                # removes the r/ from the input
            )
        except ValueError:
            subreddit = reddit.subreddit("askreddit")
            print_substep("Subreddit not defined. Using AskReddit.")
    else:
        sub = settings.config["reddit"]["thread"]["subreddit"]
        print_substep(f"Using subreddit: r/{sub} from TOML config")
        subreddit_choice = sub
        if str(subreddit_choice).casefold().startswith("r/"):  # removes the r/ from the input
            subreddit_choice = subreddit_choice[2:]
        subreddit = reddit.subreddit(subreddit_choice)

    while True:
        submission_obj = None

        # Get a submission
        if POST_ID:  # would only be called if there are multiple queued posts
            submission_obj = reddit.submission(id=POST_ID)

        elif (
            settings.config["reddit"]["thread"]["post_id"]
            and len(str(settings.config["reddit"]["thread"]["post_id"]).split("+")) == 1
        ):
            submission_obj = reddit.submission(id=settings.config["reddit"]["thread"]["post_id"])
        elif settings.config["ai"]["ai_similarity_enabled"]:  # ai sorting based on comparison
            threads = subreddit.hot(limit=50)
            keywords = settings.config["ai"]["ai_similarity_keywords"].split(",")
            keywords = [keyword.strip() for keyword in keywords]
            # Reformat the keywords for printing
            keywords_print = ", ".join(keywords)
            print(f"Sorting threads by similarity to the given keywords: {keywords_print}")
            threads, similarity_scores = sort_by_similarity(threads, keywords)
            submission_obj, similarity_score = get_subreddit_undone(
                threads, subreddit, similarity_scores=similarity_scores
            )
        else:
            threads = subreddit.hot(limit=25)
            submission_obj = get_subreddit_undone(threads, subreddit)

        if submission_obj is None:
            print_substep("No more suitable posts found in this subreddit.")
            print_substep("This might be because:")
            print_substep("- All posts have been processed already")
            print_substep("- No posts have enough text for hybrid mode")
            print_substep("- No posts meet the minimum comment requirements")
            print_substep("Consider:")
            print_substep("- Clearing the video history: Delete video_creation/data/videos.json")
            print_substep("- Using a different subreddit")
            print_substep("- Lowering hybrid_comments_count in config.toml")
            return None

        if isinstance(submission_obj, tuple):
            submission, similarity_score = submission_obj
        else:
            submission = submission_obj
        
        if submission is None:
             continue

        # `check_done` now returns None if the post is done, or the submission object if not.
        if not check_done(submission):
            continue

        if not submission.selftext and (
            settings.config["settings"]["storymode"] or settings.config["settings"].get("hybrid_mode", False)
        ):
            print_substep("Post has no text, which is required for story mode or hybrid mode. Skipping post.", style="bold red")
            check_done(submission, mark_as_done=True)
            continue

        if (
            submission.num_comments == 0
            and not settings.config["settings"]["storymode"]
            and not settings.config["settings"].get("hybrid_mode", False)
        ):
            print_substep("Post has no comments. Skipping.")
            check_done(submission, mark_as_done=True)
            continue

        max_comments = settings.config["settings"].get("hybrid_comments_count", 3)
        if settings.config["settings"].get("hybrid_mode", False) and submission.num_comments < max_comments:
            print_substep(f"Post has less than {max_comments} comments, which is the minimum required for hybrid mode. Skipping post.")
            check_done(submission, mark_as_done=True)
            continue

        # If we've reached this point, the submission is valid.
        break

    upvotes = submission.score
    ratio = submission.upvote_ratio * 100
    num_comments = submission.num_comments
    threadurl = f"https://new.reddit.com/{submission.permalink}"

    print_substep(f"Video will be: {submission.title} :thumbsup:", style="bold green")
    print_substep(f"Thread url is: {threadurl} :thumbsup:", style="bold green")
    print_substep(f"Thread has {upvotes} upvotes", style="bold blue")
    print_substep(f"Thread has a upvote ratio of {ratio}%", style="bold blue")
    print_substep(f"Thread has {num_comments} comments", style="bold blue")
    if similarity_score:
        print_substep(
            f"Thread has a similarity score up to {round(similarity_score * 100)}%",
            style="bold blue",
        )

    content["thread_url"] = threadurl
    content["thread_title"] = submission.title
    content["thread_id"] = submission.id
    content["is_nsfw"] = submission.over_18
    content["comments"] = []
    
    # Handle hybrid mode - includes both post text and comments
    if settings.config["settings"].get("hybrid_mode", False):
        max_comments = settings.config["settings"].get("hybrid_comments_count", 1)
        
        # Add post content for hybrid mode - prefer selftext, fallback to OP comment
        post_content = submission.selftext
        if not post_content or len(post_content.strip()) < 30:
            # Try to find OP comment as content
            try:
                for comment in submission.comments.list()[:5]:
                    if (hasattr(comment, 'author') and comment.author and 
                        str(comment.author) == str(submission.author) and 
                        len(comment.body.strip()) >= 30):
                        post_content = comment.body
                        print_substep("Using OP comment as post content")
                        break
            except:
                pass
        
        if settings.config["settings"]["storymodemethod"] == 1:
            content["thread_post"] = posttextparser(post_content) if post_content else submission.title
        else:
            content["thread_post"] = post_content if post_content else submission.title
            
        # Also collect top comments for hybrid mode
        comment_count = 0
        
        for top_level_comment in submission.comments:
            if comment_count >= max_comments:
                break
                
            if isinstance(top_level_comment, MoreComments):
                continue

            if top_level_comment.body in ["[removed]", "[deleted]"]:
                continue
                
            if not top_level_comment.stickied:
                sanitised = sanitize_text(top_level_comment.body)
                if not sanitised or sanitised == " ":
                    continue
                    
                if len(top_level_comment.body) <= int(
                    settings.config["reddit"]["thread"]["max_comment_length"]
                ):
                    if len(top_level_comment.body) >= int(
                        settings.config["reddit"]["thread"]["min_comment_length"]
                    ):
                        if (
                            top_level_comment.author is not None
                            and sanitize_text(top_level_comment.body) is not None
                        ):
                            content["comments"].append(
                                {
                                    "comment_body": top_level_comment.body,
                                    "comment_url": top_level_comment.permalink,
                                    "comment_id": top_level_comment.id,
                                }
                            )
                            comment_count += 1
                            
    elif settings.config["settings"]["storymode"]:
        if settings.config["settings"]["storymodemethod"] == 1:
            content["thread_post"] = posttextparser(submission.selftext)
        else:
            content["thread_post"] = submission.selftext
    else:
        for top_level_comment in submission.comments:
            if isinstance(top_level_comment, MoreComments):
                continue

            if top_level_comment.body in ["[removed]", "[deleted]"]:
                continue  # # see https://github.com/JasonLovesDoggo/RedditVideoMakerBot/issues/78
            if not top_level_comment.stickied:
                sanitised = sanitize_text(top_level_comment.body)
                if not sanitised or sanitised == " ":
                    continue
                if len(top_level_comment.body) <= int(
                    settings.config["reddit"]["thread"]["max_comment_length"]
                ):
                    if len(top_level_comment.body) >= int(
                        settings.config["reddit"]["thread"]["min_comment_length"]
                    ):
                        if (
                            top_level_comment.author is not None
                            and sanitize_text(top_level_comment.body) is not None
                        ):  # if errors occur with this change to if not.
                            content["comments"].append(
                                {
                                    "comment_body": top_level_comment.body,
                                    "comment_url": top_level_comment.permalink,
                                    "comment_id": top_level_comment.id,
                                }
                            )

    print_substep("Received subreddit threads Successfully.", style="bold green")
    return content
