import os
import sys
import time
import logging
import pytest
from unittest.mock import patch, MagicMock, mock_open

# ---------------------------------------------------------------------------
# Bootstrap: stub dotenv and RotatingFileHandler BEFORE importing bot
# ---------------------------------------------------------------------------

os.environ.setdefault('GITHUB_USER', 'testuser')
os.environ.setdefault('PERSONAL_GITHUB_TOKEN', 'test-token')

# Ensure project root is on sys.path so bot and bot_exceptions can be imported
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Stub dotenv if not installed
import types as _types
if 'dotenv' not in sys.modules:
    _dotenv_stub = _types.ModuleType('dotenv')
    _dotenv_stub.load_dotenv = lambda *a, **kw: None
    sys.modules['dotenv'] = _dotenv_stub

# Use a real NullHandler so logger.callHandlers never compares MagicMock.level
_null_handler = logging.NullHandler()

with patch('logging.handlers.RotatingFileHandler', return_value=_null_handler):
    import bot
    from bot_exceptions import (
        FileOperationError,
        GitHubAuthError,
        GitHubRateLimitError,
    )

# Strip all handlers from the bot logger and disable propagation so no log
# call can reach the root logger or any file-based handler.
_bot_logger = logging.getLogger('GitHubFollowerBot')
_bot_logger.handlers.clear()
_bot_logger.propagate = False
_bot_logger.addHandler(logging.NullHandler())


# ---------------------------------------------------------------------------
# load_followed_users
# ---------------------------------------------------------------------------

class TestLoadFollowedUsers:
    def test_returns_empty_set_when_file_missing(self, tmp_path):
        result = bot.load_followed_users(str(tmp_path / 'nonexistent.txt'))
        assert result == set()

    def test_returns_set_of_usernames(self, tmp_path):
        f = tmp_path / 'followers.txt'
        f.write_text('alice\nbob\ncharlie\n')
        result = bot.load_followed_users(str(f))
        assert result == {'alice', 'bob', 'charlie'}

    def test_ignores_blank_lines(self, tmp_path):
        f = tmp_path / 'followers.txt'
        f.write_text('alice\n\nbob\n\n')
        result = bot.load_followed_users(str(f))
        assert result == {'alice', 'bob'}

    def test_strips_whitespace(self, tmp_path):
        f = tmp_path / 'followers.txt'
        f.write_text('  alice  \n  bob\n')
        result = bot.load_followed_users(str(f))
        assert result == {'alice', 'bob'}

    def test_empty_file_returns_empty_set(self, tmp_path):
        f = tmp_path / 'followers.txt'
        f.write_text('')
        result = bot.load_followed_users(str(f))
        assert result == set()


# ---------------------------------------------------------------------------
# append_followed_user
# ---------------------------------------------------------------------------

class TestAppendFollowedUser:
    def test_appends_user_to_file(self, tmp_path):
        f = tmp_path / 'followers.txt'
        bot.append_followed_user(str(f), 'alice')
        assert f.read_text() == 'alice\n'

    def test_appends_multiple_users(self, tmp_path):
        f = tmp_path / 'followers.txt'
        bot.append_followed_user(str(f), 'alice')
        bot.append_followed_user(str(f), 'bob')
        assert f.read_text() == 'alice\nbob\n'

    def test_raises_file_operation_error_on_write_failure(self, tmp_path):
        # bot re-raises OSError as FileOperationError
        bad_path = str(tmp_path / 'no_such_dir' / 'followers.txt')
        with pytest.raises(FileOperationError):
            bot.append_followed_user(bad_path, 'alice')


# ---------------------------------------------------------------------------
# load_follower_counter
# ---------------------------------------------------------------------------

class TestLoadFollowerCounter:
    def test_returns_zero_when_file_missing(self, tmp_path):
        result = bot.load_follower_counter(str(tmp_path / 'counter.txt'))
        assert result == 0

    def test_returns_integer_from_file(self, tmp_path):
        f = tmp_path / 'counter.txt'
        f.write_text('42\n')
        assert bot.load_follower_counter(str(f)) == 42

    def test_returns_zero_for_non_digit_content(self, tmp_path):
        f = tmp_path / 'counter.txt'
        f.write_text('not-a-number\n')
        assert bot.load_follower_counter(str(f)) == 0

    def test_returns_zero_for_empty_file(self, tmp_path):
        f = tmp_path / 'counter.txt'
        f.write_text('')
        assert bot.load_follower_counter(str(f)) == 0

    def test_returns_zero_for_float_string(self, tmp_path):
        # '3.14'.isdigit() is False
        f = tmp_path / 'counter.txt'
        f.write_text('3.14\n')
        assert bot.load_follower_counter(str(f)) == 0

    def test_returns_zero_for_negative_string(self, tmp_path):
        # '-5'.isdigit() is False
        f = tmp_path / 'counter.txt'
        f.write_text('-5\n')
        assert bot.load_follower_counter(str(f)) == 0


# ---------------------------------------------------------------------------
# update_follower_counter
# ---------------------------------------------------------------------------

class TestUpdateFollowerCounter:
    def test_writes_count_to_file(self, tmp_path):
        f = tmp_path / 'counter.txt'
        bot.update_follower_counter(str(f), 99)
        assert f.read_text() == '99\n'

    def test_overwrites_existing_value(self, tmp_path):
        f = tmp_path / 'counter.txt'
        f.write_text('5\n')
        bot.update_follower_counter(str(f), 10)
        assert f.read_text() == '10\n'

    def test_raises_file_operation_error_on_write_failure(self, tmp_path):
        # bot re-raises OSError as FileOperationError
        bad_path = str(tmp_path / 'no_such_dir' / 'counter.txt')
        with pytest.raises(FileOperationError):
            bot.update_follower_counter(bad_path, 1)


# ---------------------------------------------------------------------------
# handle_rate_limit
# ---------------------------------------------------------------------------

class TestHandleRateLimit:
    def _make_response(self, status_code, text='', headers=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.text = text
        resp.headers = headers or {}
        return resp

    def test_returns_false_for_200(self):
        resp = self._make_response(200)
        assert bot.handle_rate_limit(resp) is False

    def test_returns_false_for_401(self):
        resp = self._make_response(401)
        assert bot.handle_rate_limit(resp) is False

    def test_returns_false_for_403_without_triggering_keywords(self):
        # Text must NOT contain 'rate limit' or 'abuse detection'
        resp = self._make_response(403, text='Forbidden access denied')
        assert bot.handle_rate_limit(resp) is False

    @patch('bot.time.sleep')
    def test_returns_true_and_sleeps_for_403_rate_limit(self, mock_sleep):
        future_reset = int(time.time()) + 1000
        resp = self._make_response(
            403,
            text='rate limit exceeded',
            headers={'X-RateLimit-Reset': str(future_reset)}
        )
        result = bot.handle_rate_limit(resp)
        assert result is True
        mock_sleep.assert_called_once()

    @patch('bot.time.sleep')
    def test_returns_true_and_sleeps_for_403_abuse_detection(self, mock_sleep):
        future_reset = int(time.time()) + 500
        resp = self._make_response(
            403,
            text='abuse detection triggered',
            headers={'X-RateLimit-Reset': str(future_reset)}
        )
        result = bot.handle_rate_limit(resp)
        assert result is True
        mock_sleep.assert_called_once()

    @patch('bot.time.sleep')
    def test_returns_true_and_sleeps_for_429(self, mock_sleep):
        resp = self._make_response(429, headers={'Retry-After': '60'})
        result = bot.handle_rate_limit(resp)
        assert result is True
        mock_sleep.assert_called_once_with(60)

    @patch('bot.time.sleep')
    def test_429_uses_default_delay_when_no_retry_after_header(self, mock_sleep):
        resp = self._make_response(429, headers={})
        result = bot.handle_rate_limit(resp)
        assert result is True
        mock_sleep.assert_called_once_with(bot.DELAY_ON_RATE_LIMIT)


# ---------------------------------------------------------------------------
# check_rate_limit
# ---------------------------------------------------------------------------

class TestCheckRateLimit:
    def _rate_limit_payload(self, remaining=1500, reset=9999999999):
        return {
            'resources': {
                'core': {
                    'remaining': remaining,
                    'reset': reset,
                }
            }
        }

    @patch('bot.requests.get')
    def test_returns_remaining_and_reset_on_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = self._rate_limit_payload(remaining=500, reset=1700000000)
        mock_get.return_value = mock_resp

        remaining, reset_time = bot.check_rate_limit()

        assert remaining == 500
        assert reset_time == 1700000000
        mock_get.assert_called_once()

    @patch('bot.requests.get')
    def test_returns_none_none_on_request_exception(self, mock_get):
        from requests.exceptions import RequestException
        mock_get.side_effect = RequestException('connection failed')

        remaining, reset_time = bot.check_rate_limit()

        assert remaining is None
        assert reset_time is None

    @patch('bot.requests.get')
    def test_sends_authorization_header_with_token(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = self._rate_limit_payload()
        mock_get.return_value = mock_resp

        bot.check_rate_limit()

        _, kwargs = mock_get.call_args
        headers = kwargs.get('headers', {})
        assert 'Authorization' in headers
        assert 'test-token' in headers['Authorization']

    @patch('bot.requests.get')
    def test_calls_rate_limit_url(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = self._rate_limit_payload()
        mock_get.return_value = mock_resp

        bot.check_rate_limit()

        args, _ = mock_get.call_args
        assert args[0] == 'https://api.github.com/rate_limit'


# ---------------------------------------------------------------------------
# follow_user
# ---------------------------------------------------------------------------

class TestFollowUser:
    @patch('bot.time.sleep')
    @patch('bot.requests.put')
    def test_returns_true_on_204(self, mock_put, mock_sleep):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_put.return_value = mock_resp

        assert bot.follow_user('alice') is True
        mock_put.assert_called_once()

    @patch('bot.time.sleep')
    @patch('bot.requests.put')
    def test_raises_auth_error_on_401(self, mock_put, mock_sleep):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_put.return_value = mock_resp

        with pytest.raises(GitHubAuthError):
            bot.follow_user('alice')

    @patch('bot.time.sleep')
    @patch('bot.requests.put')
    def test_returns_false_on_404(self, mock_put, mock_sleep):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = 'Not Found'
        mock_put.return_value = mock_resp

        assert bot.follow_user('ghost') is False

    @patch('bot.time.sleep')
    @patch('bot.requests.put')
    def test_raises_rate_limit_error_on_403_rate_limit(self, mock_put, mock_sleep):
        # 403 with rate-limit body triggers handle_rate_limit then raises GitHubRateLimitError
        rate_limit_resp = MagicMock()
        rate_limit_resp.status_code = 403
        rate_limit_resp.text = 'rate limit exceeded'
        rate_limit_resp.headers = {'X-RateLimit-Reset': str(int(time.time()) + 10)}
        mock_put.return_value = rate_limit_resp

        with pytest.raises(GitHubRateLimitError):
            bot.follow_user('alice')

    @patch('bot.time.sleep')
    @patch('bot.requests.put')
    def test_raises_rate_limit_error_on_429(self, mock_put, mock_sleep):
        # 429 sleeps then raises GitHubRateLimitError
        too_many_resp = MagicMock()
        too_many_resp.status_code = 429
        too_many_resp.headers = {'Retry-After': '1'}
        mock_put.return_value = too_many_resp

        with pytest.raises(GitHubRateLimitError):
            bot.follow_user('alice')
        mock_sleep.assert_called_once_with(1)

    @patch('bot.time.sleep')
    @patch('bot.requests.put')
    def test_returns_false_after_max_retries_on_request_exception(self, mock_put, mock_sleep):
        from requests.exceptions import RequestException
        mock_put.side_effect = RequestException('connection error')

        result = bot.follow_user('alice')
        assert result is False
        assert mock_put.call_count == bot.MAX_RETRIES

    @patch('bot.time.sleep')
    @patch('bot.requests.put')
    def test_calls_correct_url(self, mock_put, mock_sleep):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_put.return_value = mock_resp

        bot.follow_user('targetuser')

        args, _ = mock_put.call_args
        assert args[0] == 'https://api.github.com/user/following/targetuser'

    @patch('bot.time.sleep')
    @patch('bot.requests.put')
    def test_sends_authorization_header(self, mock_put, mock_sleep):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_put.return_value = mock_resp

        bot.follow_user('alice')

        _, kwargs = mock_put.call_args
        headers = kwargs.get('headers', {})
        assert 'Authorization' in headers
        assert 'test-token' in headers['Authorization']
