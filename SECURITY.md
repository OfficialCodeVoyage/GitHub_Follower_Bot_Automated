# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| main    | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability, please do **not** open a public issue.

Instead, report it by emailing the maintainer directly (see the GitHub profile for contact details).

Please include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact

You can expect a response within 72 hours.

## Token Security

This bot requires a GitHub Personal Access Token (PAT) with `user:follow` scope.

- **Never commit your token to the repository.** Store it as a GitHub Actions secret (`PERSONAL_GITHUB_TOKEN`) or in a local `.env` file that is gitignored.
- Rotate your token immediately if you suspect it has been exposed.
- Use a fine-grained PAT scoped to only the permissions this bot needs.

## Runtime Data

The bot writes state files (`followers.txt`, `follower_counter.txt`, etc.) to the working directory. These files contain GitHub usernames and should not be committed to the repository. They are listed in `.gitignore`.
