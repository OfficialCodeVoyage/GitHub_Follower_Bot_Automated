import os
import asyncio
import aiohttp
import aiofiles
import logging
from aiohttp import ClientSession
from aiohttp import ClientResponseError
from aiohttp.client_exceptions import ClientError

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Constants and Configuration
GITHUB_USER = "OfficialCodeVoyage"
PERSONAL_GITHUB_TOKEN = os.getenv('personal_github_token')
FOLLOWER_URL = f'https://api.github.com/users/{GITHUB_USER}/followers'
FOLLOW_URL_TEMPLATE = 'https://api.github.com/user/following/{}'
LAST_CHECKED_FOLLOWER_FILE = './last_checked_follower.txt'
FOLLOWER_COUNTER_FILE = './follower_counter.txt'
FOLLOWED_USERS_FILE = './followers.txt'

# GitHub API Headers
HEADERS = {
    'Authorization': f'token {PERSONAL_GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': 'OfficialCodeVoyage-Bot'
}

# Concurrency limit
CONCURRENT_REQUESTS = 5

async def fetch_followers(session: ClientSession, url: str, page: int):
    params = {'page': page, 'per_page': 100}
    try:
        async with session.get(url, headers=HEADERS, params=params) as response:
            response.raise_for_status()
            followers = await response.json()
            logging.info(f"Fetched {len(followers)} followers from page {page}.")
            return followers
    except ClientResponseError as e:
        logging.error(f"HTTP error while fetching followers from page {page}: {e.status} {e.message}")
    except ClientError as e:
        logging.error(f"Client error while fetching followers from page {page}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error while fetching followers from page {page}: {e}")
    return []

async def follow_user(session: ClientSession, user: str, semaphore: asyncio.Semaphore):
    follow_url = FOLLOW_URL_TEMPLATE.format(user)
    async with semaphore:
        try:
            async with session.put(follow_url, headers=HEADERS) as response:
                if response.status == 204:
                    logging.info(f"Successfully followed user: {user}")
                    return True
                elif response.status == 404:
                    logging.warning(f"User not found: {user}")
                elif response.status == 403:
                    logging.error(f"Forbidden to follow user: {user}. Possibly rate limited.")
                else:
                    text = await response.text()
                    logging.warning(f"Failed to follow {user}: {response.status} {text}")
        except ClientResponseError as e:
            logging.error(f"HTTP error while following {user}: {e.status} {e.message}")
        except ClientError as e:
            logging.error(f"Client error while following {user}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error while following {user}: {e}")
    return False

async def read_file(file_path: str) -> str:
    try:
        async with aiofiles.open(file_path, 'r') as f:
            content = await f.read()
            logging.info(f"Read from {file_path}: {content.strip()}")
            return content.strip()
    except FileNotFoundError:
        logging.warning(f"{file_path} not found. Returning empty string.")
        return ''
    except Exception as e:
        logging.error(f"Error reading {file_path}: {e}")
        return ''

async def write_file(file_path: str, content: str):
    try:
        async with aiofiles.open(file_path, 'w') as f:
            await f.write(content)
            logging.info(f"Wrote to {file_path}: {content}")
    except Exception as e:
        logging.error(f"Error writing to {file_path}: {e}")

async def append_to_file(file_path: str, content: str):
    try:
        async with aiofiles.open(file_path, 'a') as f:
            await f.write(content + '\n')
            logging.info(f"Appended to {file_path}: {content}")
    except Exception as e:
        logging.error(f"Error appending to {file_path}: {e}")

async def increment_counter(file_path: str):
    try:
        async with aiofiles.open(file_path, 'r+') as f:
            content = await f.read()
            counter = int(content.strip()) if content.strip().isdigit() else 0
            counter += 1
            await f.seek(0)
            await f.write(str(counter))
            await f.truncate()
            logging.info(f"Updated follower counter to: {counter}")
            return counter
    except FileNotFoundError:
        await write_file(file_path, '1')
        logging.info(f"Initialized follower counter to: 1")
        return 1
    except Exception as e:
        logging.error(f"Error updating follower counter: {e}")
        return 0

async def get_new_followers(session: ClientSession, last_checked: str) -> list:
    page = 1
    new_followers = []
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    while True:
        followers = await fetch_followers(session, FOLLOWER_URL, page)
        if not followers:
            break

        for follower in followers:
            user = follower.get('login')
            if not user:
                continue
            if user == last_checked:
                logging.info(f"Reached last checked follower: {user}. Stopping fetch.")
                return new_followers
            new_followers.append(user)
            logging.info(f"New follower found: {user}")

        if len(followers) < 100:
            # Assuming less than 100 means last page
            break
        page += 1

    return new_followers

async def process_new_followers(session: ClientSession, new_followers: list):
    if not new_followers:
        logging.info("No new followers to process.")
        return

    logging.info(f"Total new followers to process: {len(new_followers)}")
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
    tasks = [follow_user(session, user, semaphore) for user in reversed(new_followers)]
    results = await asyncio.gather(*tasks)

    followed_users = [user for user, success in zip(reversed(new_followers), results) if success]

    for user in followed_users:
        await append_to_file(FOLLOWED_USERS_FILE, user)
        await increment_counter(FOLLOWER_COUNTER_FILE)

    if followed_users:
        # Update the last checked follower to the most recent one processed
        await write_file(LAST_CHECKED_FOLLOWER_FILE, followed_users[0])
        logging.info(f"Last checked follower updated to: {followed_users[0]}")

async def main():
    logging.info("Starting the GitHub follow-back bot...")

    async with aiohttp.ClientSession() as session:
        last_checked_follower = await read_file(LAST_CHECKED_FOLLOWER_FILE)
        new_followers = await get_new_followers(session, last_checked_follower)
        await process_new_followers(session, new_followers)

    logging.info("Bot execution completed.")

if __name__ == "__main__":
    asyncio.run(main())
