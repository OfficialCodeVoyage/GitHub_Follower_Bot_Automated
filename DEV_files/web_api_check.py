import os
import asyncio
import aiohttp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration Constants
GITHUB_USER = os.getenv('GITHUB_USER')  # Your GitHub username
PERSONAL_GITHUB_TOKEN = os.getenv('PERSONAL_GITHUB_TOKEN')  # Your personal access token

# Validate configuration
if not GITHUB_USER or not PERSONAL_GITHUB_TOKEN:
    raise EnvironmentError("GITHUB_USER or PERSONAL_GITHUB_TOKEN is not set in the .env file.")

FOLLOWER_URL = f'https://api.github.com/users/{GITHUB_USER}/followers'

# GitHub API Headers
HEADERS = {
    'Authorization': f'token {PERSONAL_GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': f'{GITHUB_USER}-FollowBack-Bot-WebAPI'
}

app = FastAPI(title="GitHub Followers API", description="API to fetch GitHub followers.", version="1.0")

class Follower(BaseModel):
    login: str
    id: int
    avatar_url: str
    html_url: str

@app.get("/followers", response_model=List[Follower])
async def get_followers():
    """
    Fetches all followers of the specified GitHub user.
    """
    followers = []
    page = 1
    per_page = 100  # Maximum allowed by GitHub API

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        while True:
            params = {'page': page, 'per_page': per_page}
            try:
                async with session.get(FOLLOWER_URL, params=params) as response:
                    if response.status != 200:
                        raise HTTPException(status_code=response.status, detail=f"GitHub API error: {response.reason}")
                    data = await response.json()
                    if not data:
                        break  # No more followers to fetch
                    for follower in data:
                        followers.append(Follower(
                            login=follower.get('login'),
                            id=follower.get('id'),
                            avatar_url=follower.get('avatar_url'),
                            html_url=follower.get('html_url')
                        ))
                    page += 1
            except aiohttp.ClientError as e:
                raise HTTPException(status_code=500, detail=f"HTTP Client Error: {e}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Unexpected Error: {e}")

    return followers
