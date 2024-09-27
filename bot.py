import os
import json
import requests
import logging
import time
import random
from dotenv import load_dotenv
from requests.exceptions import RequestException, HTTPError
from logging.handlers import RotatingFileHandler

# ===========================
# Configuration Section
# ===========================
load_dotenv()

# Load environment variables
github_user = os.getenv('GITHUB_USER')
personal_github_token = os.getenv('PERSONAL_GITHUB_TOKEN')

if not github_user or not personal_github_token:
    raise EnvironmentError("Please set both 'GITHUB_USER' and 'PERSONAL_GITHUB_TOKEN' in your environment variables.")

# GitHub API endpoints
per_page = 100  # Maximum number of followers per page
follower_url_template = f'https://api.github.com/users/{github_user}/followers?per_page={per_page}&page={{}}'
update_followed_user = 'https://api.github.com/user/following/{}'

# File paths
followers_file_path = 'followers.txt'
follower_counter_path = 'follower_counter.txt'
last_checked_follower_path = 'last_checked_follower.txt'
current_page_path = 'current_page.txt'  # For persisting current page number

# Rate limiting and retry settings
MAX_RETRIES = 5
RETRY_BACKOFF_FACTOR = 2  # Exponential backoff
RATE_LIMIT_THRESHOLD = 100  # Remaining requests to start being cautious

# Delay settings (in seconds)
DELAY_BETWEEN_FETCH_AND_FOLLOW = 5   # Increased from 3 to 5 seconds
DELAY_BETWEEN_FOLLOWS = 10           # Increased from 5 to 10 seconds
DELAY_ON_RATE_LIMIT = 300            # seconds (5 minutes)

# ===========================
# Logging Configuration
# ===========================
logger = logging.getLogger('GitHubFollowerBot')
logger.setLevel(logging.INFO)

# Rotating File Handler
file_handler = RotatingFileHandler('bot.log', maxBytes=5*1024*1024, backupCount=5)  # 5 MB per file, keep 5 backups
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# ===========================
# Utility Functions
# ===========================

def load_followed_users(file_path):
    """Loads followed users from a file into a set."""
    if not os.path.exists(file_path):
        return set()
    with open(file_path, 'r') as f:
        return set(line.strip() for line in f if line.strip())

def append_followed_user(file_path, user):
    """Appends a followed user to the file."""
    with open(file_path, 'a') as f:
        f.write(f"{user}\n")

def load_follower_counter(file_path):
    """Loads the follower counter from a file."""
    if not os.path.exists(file_path):
        return 0
    with open(file_path, 'r') as f:
        count = f.read().strip()
        return int(count) if count.isdigit() else 0

def update_follower_counter(file_path, count):
    """Writes the follower count to a file."""
    try:
        with open(file_path, 'w') as f:
            f.write(f"{count}\n")
        logger.info(f"Follower counter updated: {count}")
    except Exception as e:
        logger.error(f"Failed to update follower counter: {e}")

def get_last_checked_follower(file_path):
    """Retrieves the last checked follower from the file."""
    if not os.path.exists(file_path):
        return None
    with open(file_path, 'r') as f:
        last_follower = f.read().strip()
        return last_follower if last_follower else None

def set_last_checked_follower(file_path, user):
    """Updates the last checked follower in the file."""
    try:
        with open(file_path, 'w') as f:
            f.write(user)
        logger.debug(f"Last checked follower set to: {user}")
    except Exception as e:
        logger.error(f"Failed to set last checked follower: {e}")

def get_current_page(file_path):
    """Retrieves the current page number from the file."""
    if not os.path.exists(file_path):
        return 1
    with open(file_path, 'r') as f:
        page = f.read().strip()
        return int(page) if page.isdigit() else 1

def set_current_page(file_path, page):
    """Updates the current page number in the file."""
    try:
        with open(file_path, 'w') as f:
            f.write(str(page))
        logger.debug(f"Current page set to: {page}")
    except Exception as e:
        logger.error(f"Failed to set current page: {e}")

def handle_rate_limit(response):
    """Handles GitHub API rate limiting with exponential backoff and jitter."""
    if response.status_code == 403:
        # Check if it's a rate limit issue
        if 'rate limit' in response.text.lower() or 'abuse detection' in response.text.lower():
            reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + DELAY_ON_RATE_LIMIT))
            sleep_duration = max(reset_time - int(time.time()), DELAY_ON_RATE_LIMIT)
            logger.warning(f"Rate limit reached. Sleeping for {sleep_duration} seconds until reset.")
            time.sleep(sleep_duration)
            return True  # Indicate that the request should be retried
    elif response.status_code == 429:
        # Handle Too Many Requests
        retry_after = int(response.headers.get('Retry-After', DELAY_ON_RATE_LIMIT))
        logger.warning(f"Received 429 Too Many Requests. Sleeping for {retry_after} seconds.")
        time.sleep(retry_after)
        return True  # Indicate that the request should be retried
    return False  # No rate limit issue

def check_rate_limit():
    """Checks the current rate limit status and logs it."""
    rate_limit_url = 'https://api.github.com/rate_limit'
    headers = {
        'User-Agent': 'GitHubFollowerBot/1.0',
        'Authorization': f'token {personal_github_token}'
    }
    try:
        response = requests.get(rate_limit_url, headers=headers)
        response.raise_for_status()
        rate_info = response.json()
        remaining = rate_info['resources']['core']['remaining']
        reset_time = rate_info['resources']['core']['reset']
        reset_time_formatted = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(reset_time))
        logger.info(f"Rate Limit - Remaining: {remaining}, Reset at: {reset_time_formatted}")
        return remaining, reset_time
    except RequestException as e:
        logger.error(f"Failed to check rate limit: {e}")
        return None, None

def follow_user(user):
    """Attempts to follow a user with retry logic, including exponential backoff with jitter."""
    url = update_followed_user.format(user)
    headers = {
        'User-Agent': 'GitHubFollowerBot/1.0',
        'Accept': 'application/vnd.github.v3+json',
        'Authorization': f'token {personal_github_token}'
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.put(url, headers=headers)
            if response.status_code == 204:
                logger.info(f"Successfully followed user: {user}")
                return True
            elif response.status_code == 401:
                logger.error("Unauthorized. Check your 'PERSONAL_GITHUB_TOKEN'.")
                return False
            elif response.status_code == 403 and handle_rate_limit(response):
                continue  # Retry after sleeping
            elif response.status_code == 429:
                # Handle Too Many Requests
                retry_after = int(response.headers.get('Retry-After', DELAY_ON_RATE_LIMIT))
                logger.warning(f"Received 429 Too Many Requests. Sleeping for {retry_after} seconds.")
                time.sleep(retry_after)
                continue  # Retry after sleeping
            else:
                logger.warning(f"Failed to follow user {user}. Status Code: {response.status_code}. Response: {response.text}")
                return False
        except RequestException as e:
            logger.error(f"RequestException while following user {user}: {e}")
            # Exponential backoff with jitter
            sleep_duration = (RETRY_BACKOFF_FACTOR ** attempt) + random.uniform(0, 1)
            logger.info(f"Retrying in {sleep_duration:.2f} seconds...")
            time.sleep(sleep_duration)
    logger.error(f"Max retries exceeded for user {user}. Skipping.")
    return False

# ===========================
# Main Functionality
# ===========================

def main():
    logger.info('Hi! I am GitHub Follower Bot.')
    logger.info('Letting you follow all your followers!')
    logger.info('Starting to fetch your follower lists...\n')

    # Load already followed users
    followed_users = load_followed_users(followers_file_path)
    logger.info(f"Loaded {len(followed_users)} already followed users.")

    # Retrieve the last checked follower
    last_checked_follower = get_last_checked_follower(last_checked_follower_path)
    if last_checked_follower:
        logger.info(f"Resuming from last checked follower: {last_checked_follower}")
    else:
        logger.info("No last checked follower found. Starting from the beginning.")

    # Retrieve the current page
    current_page = get_current_page(current_page_path)
    logger.info(f"Starting from page: {current_page}")

    # Load the follower counter
    total_followers_followed = load_follower_counter(follower_counter_path)
    logger.info(f"Current follower counter: {total_followers_followed}")

    # Initialize counters
    total_followers_fetched = 0

    # Initial rate limit check
    remaining, reset_time = check_rate_limit()
    if remaining is not None and remaining < RATE_LIMIT_THRESHOLD:
        sleep_duration = max(reset_time - int(time.time()), DELAY_ON_RATE_LIMIT)
        logger.warning(f"Low rate limit remaining: {remaining}. Sleeping for {sleep_duration} seconds until reset.")
        time.sleep(sleep_duration)

    resume = False if last_checked_follower else True  # If there's a last checked follower, start skipping until after it

    while True:
        current_follower_url = follower_url_template.format(current_page)
        logger.info(f"Fetching followers from: {current_follower_url}")
        try:
            response = requests.get(current_follower_url, headers={
                'User-Agent': 'GitHubFollowerBot/1.0',
                'Authorization': f'token {personal_github_token}'
            })
            response.raise_for_status()
            followers = response.json()
            num_followers = len(followers)

            # Inspect headers to verify per_page
            link_header = response.headers.get('Link', '')
            logger.debug(f"Link header: {link_header}")

            # Log and verify per_page
            logger.debug(f"Number of followers fetched: {num_followers}")

            if num_followers == 0:
                logger.info("No more followers to process. Exiting.")
                break
            total_followers_fetched += num_followers
            logger.info(f"Fetched {num_followers} followers on page {current_page}.")

            # Sleep before starting to follow users
            logger.info(f"Sleeping for {DELAY_BETWEEN_FETCH_AND_FOLLOW} seconds before following users.")
            time.sleep(DELAY_BETWEEN_FETCH_AND_FOLLOW)

            for follower in followers:
                user = follower.get('login')
                if not user:
                    continue  # Skip if 'login' not present

                # If resuming, skip until after the last checked follower
                if not resume:
                    if user == last_checked_follower:
                        resume = True
                        continue
                    else:
                        continue  # Still skipping
                # Now, processing followers after the last checked follower

                if user in followed_users:
                    logger.debug(f"Already followed user: {user}. Skipping.")
                    continue

                success = follow_user(user)
                # Update last checked follower regardless of success
                set_last_checked_follower(last_checked_follower_path, user)

                if success:
                    append_followed_user(followers_file_path, user)
                    followed_users.add(user)
                    total_followers_followed += 1
                    update_follower_counter(follower_counter_path, total_followers_followed)

                # Delay between follows to prevent triggering rate limits or abuse detection
                # Adding jitter to make delays less predictable
                jitter = random.uniform(0, 2)  # Random float between 0 and 2
                sleep_duration = DELAY_BETWEEN_FOLLOWS + jitter
                logger.info(f"Sleeping for {sleep_duration:.2f} seconds before the next follow.")
                time.sleep(sleep_duration)

            # After processing each page, persist the current page number
            set_current_page(current_page_path, current_page)

            # After processing each page, check rate limits
            remaining, reset_time = check_rate_limit()
            if remaining is not None and remaining < RATE_LIMIT_THRESHOLD:
                sleep_duration = max(reset_time - int(time.time()), DELAY_ON_RATE_LIMIT)
                logger.warning(f"Low rate limit remaining: {remaining}. Sleeping for {sleep_duration} seconds until reset.")
                time.sleep(sleep_duration)

            current_page += 1
        except HTTPError as http_err:
            logger.error(f"HTTP error occurred while fetching followers: {http_err}")
            if handle_rate_limit(response):
                continue  # Retry after handling rate limit
            else:
                break  # Exit loop on other HTTP errors
        except RequestException as req_err:
            logger.error(f"RequestException occurred: {req_err}")
            sleep_duration = RETRY_BACKOFF_FACTOR ** 1
            logger.info(f"Retrying in {sleep_duration} seconds...")
            time.sleep(sleep_duration)
            continue  # Retry the same page
        except json.JSONDecodeError as json_err:
            logger.error(f"JSONDecodeError: {json_err}")
            break  # Exit loop on JSON errors
        except KeyboardInterrupt:
            logger.warning("Script interrupted by user. Saving progress and exiting.")
            break  # Gracefully handle user interruption

    # Update follower counter at the end (redundant if updated after each follow)
    update_follower_counter(follower_counter_path, total_followers_followed)
    logger.info(f"\nFollowing users from your follower list is done! Total followers fetched: {total_followers_fetched}, Total followers followed: {total_followers_followed}")

if __name__ == '__main__':
    main()
