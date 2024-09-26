# tests/test_bot.py

import pytest
from unittest.mock import patch, mock_open, MagicMock
import requests
from bot import fetch_followers, follow_user, get_new_followers, process_batch, process_followers_in_batches
from utils import read_file, write_file, append_to_file, increment_counter

# Constants for testing
TEST_URL = 'https://api.github.com/users/test_user/followers'
TEST_USERNAME = 'testuser'
LAST_CHECKED = 'existing_user'
ALL_FOLLOWERS = ['new_user1', 'new_user2', 'existing_user', 'old_user1']

def test_fetch_followers_success():
    mock_response = [
        {'login': 'user1'},
        {'login': 'user2'}
    ]

    with patch('requests.get') as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_response)
        followers = fetch_followers(TEST_URL, page=1)
        assert followers == mock_response
        mock_get.assert_called_once_with(
            TEST_URL,
            headers={'Authorization': 'token None', 'Accept': 'application/vnd.github.v3+json'},
            params={'page': 1, 'per_page': 100}
        )

def test_fetch_followers_http_error():
    with patch('requests.get') as mock_get:
        mock_get.return_value.raise_for_status.side_effect = requests.HTTPError("404 Client Error: Not Found for url")
        followers = fetch_followers(TEST_URL, page=1)
        assert followers == []
        mock_get.assert_called_once()

def test_follow_user_success():
    username = 'user1'
    with patch('requests.put') as mock_put:
        mock_put.return_value.status_code = 204
        success = follow_user(username)
        assert success is True
        mock_put.assert_called_once_with(
            f'https://api.github.com/user/following/{username}',
            headers={'Authorization': 'token None', 'Accept': 'application/vnd.github.v3+json'}
        )

def test_follow_user_not_found():
    username = 'nonexistent_user'
    with patch('requests.put') as mock_put:
        mock_put.return_value.status_code = 404
        success = follow_user(username)
        assert success is False
        mock_put.assert_called_once()

def test_follow_user_forbidden():
    username = 'user1'
    with patch('requests.put') as mock_put:
        mock_put.return_value.status_code = 403
        success = follow_user(username)
        assert success is False
        mock_put.assert_called_once()

def test_read_file_exists():
    mock = mock_open(read_data='user1')
    with patch('builtins.open', mock):
        content = read_file('some_file.txt')
        assert content == 'user1'
        mock.assert_called_once_with('some_file.txt', 'r')

def test_read_file_not_found():
    with patch('builtins.open', side_effect=FileNotFoundError):
        content = read_file('nonexistent_file.txt')
        assert content == ''

def test_write_file():
    mock = mock_open()
    with patch('builtins.open', mock):
        write_file('some_file.txt', 'content')
        mock.assert_called_once_with('some_file.txt', 'w')
        mock().write.assert_called_once_with('content')


def test_append_to_file():
    mock = mock_open()
    with patch('builtins.open', mock):
        append_to_file('some_file.txt', 'new_user')
        mock.assert_called_once_with('some_file.txt', 'a')
        mock().write.assert_called_once_with('new_user\n')

def test_increment_counter_exists():
    mock = mock_open(read_data='5')
    with patch('builtins.open', mock):
        counter = increment_counter('counter.txt')
        assert counter == 6
        mock.assert_called_once_with('counter.txt', 'r+')
        handle = mock()
        handle.seek.assert_called_once_with(0)
        handle.write.assert_called_once_with('6')
        handle.truncate.assert_called_once()

def test_increment_counter_not_found():
    with patch('builtins.open', side_effect=FileNotFoundError):
        with patch('utils.write_file') as mock_write:
            counter = increment_counter('nonexistent_counter.txt')
            assert counter == 1
            mock_write.assert_called_once_with('nonexistent_counter.txt', '1')

def test_get_new_followers():
    new_followers = get_new_followers(LAST_CHECKED, ALL_FOLLOWERS)
    assert new_followers == ['new_user1', 'new_user2']

def test_get_new_followers_not_found():
    new_followers = get_new_followers('unknown_user', ALL_FOLLOWERS)
    assert new_followers == ALL_FOLLOWERS


def test_process_batch():
    usernames = ['user1', 'user2', 'user3']
    with patch('bot.follow_user') as mock_follow_user, \
            patch('bot.append_to_file') as mock_append, \
            patch('bot.write_file') as mock_write, \
            patch('bot.increment_counter') as mock_increment:
        mock_follow_user.side_effect = [True, False, True]

        process_batch(usernames)

        # Assert that follow_user was called three times
        assert mock_follow_user.call_count == 3
        mock_follow_user.assert_any_call('user1')
        mock_follow_user.assert_any_call('user2')
        mock_follow_user.assert_any_call('user3')

        # Assert that append_to_file was called correctly
        mock_append.assert_any_call('followers.txt', 'user1')
        mock_append.assert_any_call('followers.txt', 'user3')
        assert mock_append.call_count == 2  # Only two successful follows

        # Assert that write_file was called correctly
        mock_write.assert_any_call('last_checked_follower.txt', 'user1')
        mock_write.assert_any_call('last_checked_follower.txt', 'user3')
        assert mock_write.call_count == 2

        # Assert that increment_counter was called correctly
        mock_increment.assert_any_call('counter.txt')
        assert mock_increment.call_count == 2


def test_process_followers_in_batches():
    new_followers = [f'user{i}' for i in range(1, 31)]  # 30 users

    with patch('bot.process_batch') as mock_process_batch, \
         patch('time.sleep') as mock_sleep:
        process_followers_in_batches(new_followers, batch_size=30, sleep_interval=0)
        mock_process_batch.assert_called_once_with(new_followers)
        mock_sleep.assert_not_called()

    new_followers = [f'user{i}' for i in range(1, 61)]  # 60 users
    with patch('bot.process_batch') as mock_process_batch, \
         patch('time.sleep') as mock_sleep:
        process_followers_in_batches(new_followers, batch_size=30, sleep_interval=0)
        assert mock_process_batch.call_count == 2
        mock_sleep.assert_called_once_with(0)
