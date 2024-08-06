import os
import json
import requests
from requests.auth import HTTPBasicAuth
import logging
import time

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

GITHUB_USER = "OfficialCodeVoyage"
personal_github_token = "#" ###
FOLLOWER_URL = f'https://api.github.com/users/{GITHUB_USER}/followers?page='
UPDATE_FOLLOWED_USER = 'https://api.github.com/user/following/{}'
LAST_CHECKED_FOLLOWER_FILE = './last_checked_follower.txt'
FOLLOWER_COUNTER_FILE = './follower_counter.txt'
FOLLOWERS_FILE = './followers.txt'

def fetch_users(url, page):
    try:
        response = requests.get(url + str(page))
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching users from {url}: {e}")
        return []

def follow_user(user):
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36'
    }
    try:
        response = requests.put(UPDATE_FOLLOWED_USER.format(user),
                                auth=HTTPBasicAuth(GITHUB_USER, personal_github_token), headers=headers)
        if response.status_code == 204:
            logging.info(f'User: {user} has been followed!')
            return True
        else:
            logging.warning(f"Failed to follow {user}: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        logging.error(f"Error following user {user}: {e}")
        return False

def read_last_checked_follower(file_path):
    try:
        with open(file_path, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        return None

def save_last_checked_follower(file_path, user):
    with open(file_path, 'w') as file:
        file.write(user)

def read_followed_users(file_path):
    try:
        with open(file_path, 'r') as file:
            return set(file.read().splitlines())
    except FileNotFoundError:
        return set()

def save_followed_user(file_path, user):
    with open(file_path, 'a') as file:
        file.write(user + '\n')

def update_follower_counter(file_path):
    try:
        with open(file_path, 'r+') as file:
            counter = int(file.read().strip() or 0)
            counter += 1
            file.seek(0)
            file.write(str(counter))
            return counter
    except FileNotFoundError:
        with open(file_path, 'w') as file:
            file.write('1')
            return 1

def main():
    logging.info('Starting to fetch your new followers...')

    page = 1
    last_checked_follower = read_last_checked_follower(LAST_CHECKED_FOLLOWER_FILE)
    followed_users = read_followed_users(FOLLOWERS_FILE)
    new_followers = []

    # Fetch new followers
    while True:
        follower_lists = fetch_users(FOLLOWER_URL, page)
        time.sleep(5)
        if not follower_lists:
            break

        for follower_info in follower_lists:
            user = follower_info['login']
            if user == last_checked_follower:
                break
            if user not in followed_users:  # Check if the user has already been followed
                new_followers.append(user)

        if new_followers and new_followers[-1] == last_checked_follower:
            break

        page += 1

    if new_followers:
        for user in reversed(new_followers):  # Start from the most recent follower
            if follow_user(user):
                save_followed_user(FOLLOWERS_FILE, user)
                update_follower_counter(FOLLOWER_COUNTER_FILE)
            time.sleep(5)
        save_last_checked_follower(LAST_CHECKED_FOLLOWER_FILE, new_followers[0])

    logging.info('Processed new followers.')

if __name__ == "__main__":
    main()
