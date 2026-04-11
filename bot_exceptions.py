class GitHubBotError(Exception):
    """Base exception for all GitHub bot errors."""
    pass


class GitHubAPIError(GitHubBotError):
    """Raised when a GitHub API call fails."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class GitHubRateLimitError(GitHubAPIError):
    """Raised when the GitHub API rate limit is hit."""
    pass


class GitHubAuthError(GitHubAPIError):
    """Raised when authentication fails (HTTP 401)."""
    pass


class FileOperationError(GitHubBotError):
    """Raised when a file read or write operation fails."""
    pass
