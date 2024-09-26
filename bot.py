import os
import asyncio
import aiohttp
import aiofiles
import logging
from aiohttp import ClientSession, ClientResponseError
from aiohttp.client_exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# -- logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

# config
GITHUB_USER = os.getenv('USERNAME')  # Your GitHub username
PERSONAL_GITHUB_TOKEN = os.getenv('PERSONAL_GITHUB_TOKEN')  # Your personal access token


if not GITHUB_USER or not PERSONAL_GITHUB_TOKEN:
    logging.error("GITHUB_USER or PERSONAL_GITHUB_TOKEN is not set. Please set them in the .env file.")
    exit(1)

FOLLOWER_URL = f'https://api.github.com/users/{GITHUB_USER}/followers'
FOLLOW_URL_TEMPLATE = 'https://api.github.com/user/following/{{}}'
LAST_CHECKED_FOLLOWER_FILE = './last_checked_follower.txt'
FOLLOWER_COUNTER_FILE = './follower_counter.txt'
FOLLOWED_USERS_FILE = './followers.txt'
LOG_FILE = './bot.log'

# GitHub API Headers
HEADERS = {
    'Authorization': f'token {PERSONAL_GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': f'{GITHUB_USER}-FollowBack-Bot'
}

# Rate Limiting Configuration
API_RATE_LIMIT = 30  # Max API requests per minute
BATCH_SIZE = 30      # Number of users to process per batch
BATCH_INTERVAL = 60  # Seconds to wait between batches (1 minute)

class GitHubFollowBackBot:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(API_RATE_LIMIT)
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=HEADERS)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.session.close()

    async def fetch_followers(self, url: str, page: int) -> list:
        """
        Fetches a list of followers from a specific page.
        """
        params = {'page': page, 'per_page': 100}
        try:
            async with self.session.get(url, params=params) as response:
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

    async def follow_user(self, user: str) -> bool:
        """
        Attempts to follow a specified user.
        """
        follow_url = FOLLOW_URL_TEMPLATE.format(user)
        async with self.semaphore:
            try:
                async with self.session.put(follow_url) as response:
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

    async def read_file(self, file_path: str) -> str:
        """
        Reads content from a file asynchronously.
        """
        try:
            async with aiofiles.open(file_path, 'r') as f:
                content = await f.read()
                logging.debug(f"Read from {file_path}: {content.strip()}")
                return content.strip()
        except FileNotFoundError:
            logging.warning(f"{file_path} not found. Returning empty string.")
            return ''
        except Exception as e:
            logging.error(f"Error reading {file_path}: {e}")
            return ''

    async def write_file(self, file_path: str, content: str):
        """
        Writes content to a file asynchronously.
        """
        try:
            async with aiofiles.open(file_path, 'w') as f:
                await f.write(content)
                logging.debug(f"Wrote to {file_path}: {content}")
        except Exception as e:
            logging.error(f"Error writing to {file_path}: {e}")

    async def append_to_file(self, file_path: str, content: str):
        """
        Appends a line to a file asynchronously.
        """
        try:
            async with aiofiles.open(file_path, 'a') as f:
                await f.write(content + '\n')
                logging.debug(f"Appended to {file_path}: {content}")
        except Exception as e:
            logging.error(f"Error appending to {file_path}: {e}")

    async def increment_counter(self, file_path: str) -> int:
        """
        Increments a numerical counter stored in a file asynchronously.
        """
        try:
            async with aiofiles.open(file_path, 'r+') as f:
                content = await f.read()
                counter = int(content.strip()) if content.strip().isdigit() else 0
                counter += 1
                await f.seek(0)
                await f.write(str(counter))
                await f.truncate()
                logging.debug(f"Updated follower counter to: {counter}")
                return counter
        except FileNotFoundError:
            await self.write_file(file_path, '1')
            logging.debug(f"Initialized follower counter to: 1")
            return 1
        except Exception as e:
            logging.error(f"Error updating follower counter: {e}")
            return 0

    def split_into_batches(self, lst: list, batch_size: int) -> list:
        """
        Splits a list into smaller batches.
        """
        return [lst[i:i + batch_size] for i in range(0, len(lst), batch_size)]

    async def get_new_followers(self, last_checked: str) -> list:
        """
        Retrieves all new followers since the last checked follower.
        """
        page = 1
        new_followers = []
        found_last_checked = False

        while True:
            followers = await self.fetch_followers(FOLLOWER_URL, page)
            if not followers:
                break  # No more followers to fetch

            logging.info(f"Processing page {page} with {len(followers)} followers.")

            for follower in followers:
                user = follower.get('login')
                if not user:
                    continue
                if user == last_checked:
                    logging.info(f"Reached last checked follower: {user}. Stopping fetch.")
                    found_last_checked = True
                    break
                new_followers.append(user)
                logging.info(f"New follower found: {user}")

            if found_last_checked:
                break

            if len(followers) < 100:
                # If fewer than 100 followers are returned, it indicates the last page
                logging.info("Last page of followers reached.")
                break


            page += 1  # Move to the next page

        if not found_last_checked and last_checked:
            logging.warning("Last checked follower not found. Processing all fetched followers.")

        logging.info(f"Total new followers fetched: {len(new_followers)}")
        return new_followers

    async def process_batch(self, batch: list):
        """
        Processes a single batch of followers.
        """
        tasks = [asyncio.create_task(self.follow_user(user)) for user in batch]
        results = await asyncio.gather(*tasks)

        followed_users = [user for user, success in zip(batch, results) if success]

        # Handle file operations sequentially to prevent race conditions
        for user in followed_users:
            await self.append_to_file(FOLLOWED_USERS_FILE, user)
            await self.increment_counter(FOLLOWER_COUNTER_FILE)

        if followed_users:
            # Update the last checked follower to the most recent one processed
            await self.write_file(LAST_CHECKED_FOLLOWER_FILE, followed_users[0])
            logging.info(f"Last checked follower updated to: {followed_users[0]}")
        else:
            logging.info("No users were successfully followed in this batch.")

    async def process_followers_in_batches(self, new_followers: list):
        """
        Processes all new followers in batches to respect rate limits.
        """
        if not new_followers:
            logging.info("No new followers to process.")
            return

        logging.info(f"Total new followers to process: {len(new_followers)}")

        batches = self.split_into_batches(new_followers, BATCH_SIZE)
        total_batches = len(batches)

        for idx, batch in enumerate(batches, start=1):
            logging.info(f"Processing batch {idx}/{total_batches} with {len(batch)} users.")
            await self.process_batch(batch)
            if idx < total_batches:
                logging.info(f"Waiting for {BATCH_INTERVAL} seconds before processing the next batch.")
                await asyncio.sleep(BATCH_INTERVAL)  # Wait before processing the next batch

    async def run(self):
        """
        Main entry point for the bot.
        """
        logging.info("Starting the GitHub follow-back bot...")

        last_checked_follower = await self.read_file(LAST_CHECKED_FOLLOWER_FILE)
        new_followers = await self.get_new_followers(last_checked_follower)
        await self.process_followers_in_batches(new_followers)

        logging.info("Bot execution completed.")

async def main():
    async with GitHubFollowBackBot() as bot:
        await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
