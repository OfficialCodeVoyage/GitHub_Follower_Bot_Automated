import os
import logging
import requests
from dotenv import load_dotenv
from requests.exceptions import RequestException
from logging.handlers import RotatingFileHandler
import time


# ===========================
# Configuration Section
# ===========================

# Load environment variables from .env file
load_dotenv()

# Retrieve GitHub credentials from environment variables
GITHUB_USER = os.getenv('GITHUB_USER')
PERSONAL_GITHUB_TOKEN = os.getenv('PERSONAL_GITHUB_TOKEN')

if not GITHUB_USER or not PERSONAL_GITHUB_TOKEN:
    raise EnvironmentError("Please set both 'GITHUB_USER' and 'PERSONAL_GITHUB_TOKEN' in your .env file.")

# GitHub API endpoints
API_BASE_URL = 'https://api.github.com'
FOLLOWERS_ENDPOINT = f'{API_BASE_URL}/users/{GITHUB_USER}/followers'
RATE_LIMIT_ENDPOINT = f'{API_BASE_URL}/rate_limit'
UPDATE_FOLLOWED_USER_ENDPOINT = f'{API_BASE_URL}/user/following/{{}}'  # Not used in this script

# File paths
FOLLOWERS_FILE_PATH = 'followers.txt'  # Stores already followed users
FOLLOWER_COUNTER_PATH = 'follower_counter.txt'  # Stores total followed count

# Rate limiting settings
RATE_LIMIT_THRESHOLD = 100  # Threshold to start being cautious

# ===========================
# Logging Configuration
# ===========================
logger = logging.getLogger('CheckAllFollowers')
logger.setLevel(logging.INFO)

# Rotating File Handler
file_handler = RotatingFileHandler('check_all_followers.log', maxBytes=5 * 1024 * 1024,
                                   backupCount=2)  # 5 MB per file, keep 2 backups
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Console Handler (optional: can be removed if only logs are desired)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)


# ===========================
# Utility Functions
# ===========================

def load_followed_users(file_path):
    """
    Loads followed users from a file into a set.
    If the file does not exist, returns an empty set.
    """
    if not os.path.exists(file_path):
        logger.info(f"No '{file_path}' found. Assuming no users have been followed yet.")
        return set()
    try:
        with open(file_path, 'r') as f:
            followed = set(line.strip() for line in f if line.strip())
        logger.info(f"Loaded {len(followed)} already followed users from '{file_path}'.")
        return followed
    except Exception as e:
        logger.error(f"Error reading '{file_path}': {e}")
        return set()


def load_follower_counter(file_path):
    """
    Loads the follower counter from a file.
    If the file does not exist or contains invalid data, returns 0.
    """
    if not os.path.exists(file_path):
        logger.info(f"No '{file_path}' found. Starting follower counter at 0.")
        return 0
    try:
        with open(file_path, 'r') as f:
            count = f.read().strip()
            follower_count = int(count) if count.isdigit() else 0
        logger.info(f"Current follower counter: {follower_count}")
        return follower_count
    except Exception as e:
        logger.error(f"Error reading '{file_path}': {e}")
        return 0


def check_rate_limit():
    """
    Checks the current rate limit status.
    Returns a tuple of (remaining_requests, reset_timestamp).
    """
    headers = {
        'Authorization': f'token {PERSONAL_GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    try:
        response = requests.get(RATE_LIMIT_ENDPOINT, headers=headers)
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


def get_total_followers():
    """
    Retrieves the total number of followers.
    Uses the 'per_page=1' parameter to minimize data transfer.
    """
    headers = {
        'Authorization': f'token {PERSONAL_GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    params = {
        'per_page': 1,
        'page': 1
    }
    try:
        response = requests.get(FOLLOWERS_ENDPOINT, headers=headers, params=params)
        response.raise_for_status()
        # Extract total count from the 'Link' header
        if 'Link' in response.headers:
            links = response.headers['Link']
            # Example of Link header:
            # <https://api.github.com/user/12345/followers?per_page=1&page=2>; rel="next", <https://api.github.com/user/12345/followers?per_page=1&page=50>; rel="last"
            for link in links.split(','):
                if 'rel="last"' in link:
                    last_url = link.split(';')[0].strip('<> ')
                    last_page = int(last_url.split('page=')[1].split('&')[0])
                    total_followers = last_page  # Since per_page=1
                    logger.info(f"Total followers: {total_followers}")
                    return total_followers
        # If Link header is not present, it means there is only one page
        total_followers = len(response.json())
        logger.info(f"Total followers: {total_followers}")
        return total_followers
    except RequestException as e:
        logger.error(f"Failed to retrieve total followers: {e}")
        return 0


def main():
    """
    Main function to check total followers and available followers to follow.
    """
    logger.info("Starting 'check_all_followers.py' script.")

    # Step 1: Get total number of followers
    total_followers = get_total_followers()

    # Step 2: Load already followed users
    followed_users = load_followed_users(FOLLOWERS_FILE_PATH)
    already_followed_count = len(followed_users)

    # Step 3: Calculate followers left to follow
    followers_left = total_followers - already_followed_count
    if followers_left < 0:
        followers_left = 0  # Prevent negative numbers

    # Step 4: Check current rate limit
    remaining_requests, reset_timestamp = check_rate_limit()
    if remaining_requests is None:
        logger.warning("Unable to retrieve rate limit information. Assuming 0 remaining requests.")
        remaining_requests = 0

    # Step 5: Calculate how many followers can be followed now
    can_follow_now = min(followers_left, remaining_requests)

    # Step 6: Load follower counter
    follower_counter = load_follower_counter(FOLLOWER_COUNTER_PATH)

    # Step 7: Log the information
    logger.info("=========================================")
    logger.info(f"Total Followers: {total_followers}")
    logger.info(f"Already Followed: {already_followed_count}")
    logger.info(f"Followers Left to Follow: {followers_left}")
    logger.info(f"API Requests Remaining: {remaining_requests}")
    logger.info(f"Can Follow Now: {can_follow_now}")
    logger.info("=========================================")


if __name__ == '__main__':
    main()
