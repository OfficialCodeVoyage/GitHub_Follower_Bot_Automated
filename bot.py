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
GITHUB_USER = os.getenv('GITHUB_USER')
PERSONAL_GITHUB_TOKEN = os.getenv('PERSONAL_GITHUB_TOKEN')

if not GITHUB_USER or not PERSONAL_GITHUB_TOKEN:
    raise EnvironmentError("Please set both 'GITHUB_USER' and 'PERSONAL_GITHUB_TOKEN' in your environment variables.")

# GitHub API endpoints
PER_PAGE = 100  # Maximum number of followers per page
FOLLOWERS_URL_TEMPLATE = f'https://api.github.com/users/{GITHUB_USER}/followers?per_page={PER_PAGE}&page={{}}'
FOLLOW_USER_URL_TEMPLATE = 'https://api.github.com/user/following/{}'

# File paths
FOLLOWED_USERS_FILE = 'followers.txt'
FOLLOWER_COUNTER_FILE = 'follower_counter.txt'

# Rate limiting and retry settings
MAX_RETRIES = 5
RETRY_BACKOFF_FACTOR = 2  # Exponential backoff
RATE_LIMIT_THRESHOLD = 100  # Remaining requests to start being cautious

# Delay settings (in seconds)
DELAY_BETWEEN_FETCH_AND_FOLLOW = 5
DELAY_BETWEEN_FOLLOWS = 10
DELAY_ON_RATE_LIMIT = 300

# ===========================
# Logging Configuration
# ===========================

logger = logging.getLogger('GitHubFollowerBot')
logger.setLevel(logging.DEBUG)  # Set to DEBUG for detailed logs

# Rotating File Handler
file_handler = RotatingFileHandler('bot.log', maxBytes=5 * 1024 * 1024, backupCount=5)  # 5 MB per file, 5 backups
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)  # Change to DEBUG for more verbosity in console
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# ===========================
# Utility Functions
# ===========================

def load_followed_users(file_path):
    """
    Loads followed users from a file into a set.
    """
    if not os.path.exists(file_path):
        return set()
    with open(file_path, 'r') as f:
        return set(line.strip() for line in f if line.strip())

def append_followed_user(file_path, user):
    """
    Appends a followed user to the file.
    """
    try:
        with open(file_path, 'a') as f:
            f.write(f"{user}\n")
        logger.debug(f"Appended user {user} to {file_path}.")
    except Exception as e:
        logger.error(f"Failed to append user {user} to {file_path}: {e}")

def load_follower_counter(file_path):
    """
    Loads the follower counter from a file.
    """
    if not os.path.exists(file_path):
        return 0
    with open(file_path, 'r') as f:
        count = f.read().strip()
        return int(count) if count.isdigit() else 0

def update_follower_counter(file_path, count):
    """
    Writes the follower count to a file.
    """
    try:
        with open(file_path, 'w') as f:
            f.write(f"{count}\n")
        logger.info(f"Follower counter updated: {count}")
    except Exception as e:
        logger.error(f"Failed to update follower counter: {e}")

def handle_rate_limit(response):
    """
    Handles GitHub API rate limiting with exponential backoff and jitter.
    """
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
    """
    Checks the current rate limit status and logs it.
    """
    rate_limit_url = 'https://api.github.com/rate_limit'
    headers = {
        'User-Agent': 'GitHubFollowerBot/1.0',
        'Authorization': f'token {PERSONAL_GITHUB_TOKEN}'
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
    """
    Attempts to follow a user with retry logic, including exponential backoff with jitter.
    """
    url = FOLLOW_USER_URL_TEMPLATE.format(user)
    headers = {
        'User-Agent': 'GitHubFollowerBot/1.0',
        'Accept': 'application/vnd.github.v3+json',
        'Authorization': f'token {PERSONAL_GITHUB_TOKEN}'
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
    followed_users = load_followed_users(FOLLOWED_USERS_FILE)
    logger.info(f"Loaded {len(followed_users)} already followed users.")

    # Remove resume following logic
    logger.info("Processing all followers without resume.")
    resume_following = True  # Always process from the beginning

    current_page = 1
    logger.info(f"Starting from page: {current_page}")

    # Load the follower counter
    total_followers_followed = load_follower_counter(FOLLOWER_COUNTER_FILE)
    logger.info(f"Current follower counter: {total_followers_followed}")

    # Initialize counters
    total_followers_fetched = 0

    # Initial rate limit check
    remaining, reset_time = check_rate_limit()
    if remaining is not None and remaining < RATE_LIMIT_THRESHOLD:
        sleep_duration = max(reset_time - int(time.time()), DELAY_ON_RATE_LIMIT)
        logger.warning(f"Low rate limit remaining: {remaining}. Sleeping for {sleep_duration} seconds until reset.")
        time.sleep(sleep_duration)

    while True:
        current_follower_url = FOLLOWERS_URL_TEMPLATE.format(current_page)
        logger.info(f"Fetching followers from: {current_follower_url}")
        try:
            response = requests.get(current_follower_url, headers={
                'User-Agent': 'GitHubFollowerBot/1.0',
                'Authorization': f'token {PERSONAL_GITHUB_TOKEN}'
            })
            response.raise_for_status()
            followers = response.json()
            num_followers = len(followers)

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

                if user in followed_users:
                    logger.debug(f"Already followed user: {user}. Skipping.")
                    continue

                logger.info(f"Attempting to follow user: {user}")
                success = follow_user(user)

                if success:
                    append_followed_user(FOLLOWED_USERS_FILE, user)
                    followed_users.add(user)
                    total_followers_followed += 1
                    update_follower_counter(FOLLOWER_COUNTER_FILE, total_followers_followed)
                else:
                    logger.warning(f"Failed to follow user: {user}")

                # Delay between follows to prevent triggering rate limits or abuse detection
                # Adding jitter to make delays less predictable
                jitter = random.uniform(0, 5)  # Increased jitter range for better randomness
                sleep_duration = DELAY_BETWEEN_FOLLOWS + jitter
                logger.info(f"Sleeping for {sleep_duration:.2f} seconds before the next follow.")
                time.sleep(sleep_duration)

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
    update_follower_counter(FOLLOWER_COUNTER_FILE, total_followers_followed)
    logger.info(f"\nFollowing users from your follower list is done! Total followers fetched: {total_followers_fetched}, Total followers followed: {total_followers_followed}")

if __name__ == '__main__':
    main()
