# MCP-X Server

A powerful FastMCP server for interacting with the X (formerly Twitter) API without requiring official API keys.

## Overview

MCP-X Server provides a set of tools for interacting with X platform, allowing you to post tweets, search for content, interact with users, and more. This server leverages the unofficial X API and custom authentication methods to access the platform's features.

## Features

- No official API keys required
- Comprehensive set of tools for X interaction
- Built on FastMCP architecture for seamless integration
- Structured, maintainable codebase

## Directory Structure

```
mcp-x-server/
├── auth/
│   └── x_authenticator.py    # X platform authentication
├── service/
│   └── x_service.py          # Core X service functionality
├── tools/
│   └── x_tools.py            # FastMCP tools definition
├── utils/
│   └── client_patcher.py     # Utility for patching the X client
├── main.py                   # Server internal entry point
└── server.py                 # Server executable entry point
```

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/mcp-x-server.git
   cd mcp-x-server
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the server:
   ```
   python server.py
   ```

4. Set up your X authentication:
   When first running the server, you'll need to authenticate by logging into your X account. The server will save your authentication data for future sessions.

## Configuration

You can configure the data directory for storing authentication information by setting the `X_DATA_DIR` environment variable:

```
export X_DATA_DIR=/path/to/data/directory
```

If not set, the default path under `auth/x_data` will be used.

## Integration with FastMCP clients

To integrate with FastMCP clients, add an entry like this to your configuration:

```json
"x": {
  "command": "/path/to/python",
  "args": ["/path/to/mcp-x-server/server.py"],
  "cwd": "/path/to/mcp-x-server"
}
```

## Available Tools

### Tweet Management

- **post_tweet**: Post a tweet to your timeline
- **delete_tweet**: Delete a tweet from your timeline
- **create_tweet_with_poll**: Create a tweet with a poll
- **get_scheduled_tweets**: View all scheduled tweets
- **create_scheduled_tweet**: Schedule a tweet for later

### Tweet Interaction

- **search_tweets**: Search for tweets matching a query
- **get_tweet_by_id**: Retrieve a specific tweet
- **favorite_tweet**: Like a tweet
- **unfavorite_tweet**: Unlike a tweet
- **retweet**: Retweet a tweet
- **delete_retweet**: Remove a retweet
- **get_retweeters**: Get users who retweeted a tweet

### User Management

- **get_user_by_screen_name**: Find user by screen name
- **get_user_by_id**: Find user by ID
- **get_user_tweets**: Get tweets from a user
- **get_user_media**: Get media tweets from a user
- **get_user_likes**: Get tweets liked by a user

### User Interaction

- **follow_user**: Follow a user
- **unfollow_user**: Unfollow a user
- **get_user_followers**: View a user's followers
- **get_user_following**: View accounts a user follows

### Direct Messages

- **send_dm**: Send a direct message
- **get_dm_history**: View conversation history
- **delete_dm**: Delete a direct message

### Trending

- **get_trends**: Get trending topics in various categories

## Usage Examples

Here are some examples of how to use the tools:

### Posting a Tweet

```
post_tweet "Just tried the new MCP-X Server - it's amazing! #MCP #FastMCP"
```

### Searching for Tweets

```
search_tweets "artificial intelligence" mode=Latest count=15
```

### Getting User Information

```
get_user_by_screen_name "elonmusk"
```

## Security and Rate Limiting

To maintain account security and avoid detection:

1. Avoid sending too many requests in a short time
2. Reuse login information by saving authentication data 
3. Be mindful of X's rate limits (detailed in the code)
4. Don't use the server for spamming or abusive purposes

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This project is not affiliated with X or Twitter, Inc. Use at your own risk.
