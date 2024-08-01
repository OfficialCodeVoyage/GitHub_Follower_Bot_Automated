import os
import json
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import logging
import time

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

GITHUB_USER = os.getenv('GITHUB_USER')
PERSONAL_GITHUB_TOKEN = os.getenv('PERSONAL_GITHUB_TOKEN')
FOLLOWER_URL = f'https://api.github.com/users/{GITHUB_USER}/followers?page='
UPDATE_FOLLOWED_USER = 'https://api.github.com/user/following/{}'


def fetch_followers(page):
    try:
        response = requests.get(FOLLOWER_URL + str(page))
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching followers: {e}")
        return []


def follow_user(user):
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36'
    }
    try:
        response = requests.put(UPDATE_FOLLOWED_USER.format(user),
                                auth=HTTPBasicAuth(GITHUB_USER, PERSONAL_GITHUB_TOKEN), headers=headers)
        if response.status_code == 204:
            logging.info(f'User: {user} has been followed!')
            return True
        else:
            logging.warning(f"Failed to follow {user}: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        logging.error(f"Error following user {user}: {e}")
        return False


def read_followed_users(file_path):
    try:
        with open(file_path, 'r') as file:
            return set(file.read().splitlines())
    except FileNotFoundError:
        return set()


def append_followed_user(file_path, user):
    with open(file_path, 'a') as file:
        file.write(user + '\n')


def save_follower_count(file_path, count):
    with open(file_path, 'w') as file:
        file.write(str(count) + '\n')


def main():
    logging.info('Starting to fetch your follower lists...')

    follower_counter = 0
    page = 1
    followed_users = read_followed_users('./followers.txt')

    while True:
        follower_lists = fetch_followers(page)
        if not follower_lists:
            break

        follower_counter += len(follower_lists)
        for follower_info in follower_lists:
            user = follower_info['login']
            if user in followed_users:
                continue

            if follow_user(user):
                append_followed_user('./followers.txt', user)

        page += 1
        time.sleep(3)

    save_follower_count('follower_counter.txt', follower_counter)
    logging.info(f'Following users from your followers list is done!')


if __name__ == "__main__":
    main()
