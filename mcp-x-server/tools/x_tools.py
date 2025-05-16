from fastmcp import FastMCP
from typing import Dict, Any, List, Optional, Tuple, Literal
import traceback
import time

# Type aliases for clarity
TweetType = Literal['Tweets', 'Replies', 'Media', 'Likes']
ProductType = Literal['Top', 'Latest', 'Media']
TrendType = Literal['trending', 'for-you', 'news', 'sports', 'entertainment']

# Create a MCP server instance
mcp = FastMCP("X MCP Server")

# ---- Shared Validators and Helpers ----

def validate_text(text: str, max_length: int = 280) -> Tuple[bool, Dict]:
    """Validate text input for tweets and messages."""
    if not text or not isinstance(text, str) or len(text.strip()) == 0:
        return False, {"status": "error", "message": "Text cannot be empty"}
    
    text = text.strip()
    return True, {"text": text[:max_length] if len(text) > max_length else text}

def validate_id(id_str: str, name: str = "ID") -> Tuple[bool, Dict]:
    """Validate an ID string."""
    if not id_str or not isinstance(id_str, str) or len(id_str.strip()) == 0:
        return False, {"status": "error", "message": f"{name} cannot be empty"}
    return True, {}

def validate_count(count: int, min_count: int = 1, max_count: int = 100) -> int:
    """Validate and normalize count parameter."""
    try:
        count = int(count)
    except (ValueError, TypeError):
        count = 20  # Default
    
    return max(min_count, min(max_count, count))

def validate_mode(mode: str, valid_modes: List[str]) -> Tuple[bool, Dict]:
    """Validate mode parameter against valid options."""
    if mode not in valid_modes:
        return False, {"status": "error", "message": f"Invalid mode. Must be one of: {', '.join(valid_modes)}"}
    return True, {}

def log_debug(prefix: str, message: str, *args):
    """Consistent debug logging."""
    formatted_args = ', '.join(f"{arg}" for arg in args)
    if args:
        print(f"[DEBUG] {prefix}: {message} ({formatted_args})")
    else:
        print(f"[DEBUG] {prefix}: {message}")

def log_error(prefix: str, message: str, err=None):
    """Consistent error logging with optional exception details."""
    print(f"[ERROR] {prefix}: {message}")
    if err:
        traceback.print_exc()

def check_x_service(x_service) -> tuple[bool, dict]:
    """Check if the X service is properly initialized and authenticated."""
    if not x_service:
        return False, {"status": "error", "message": "X service not initialized. Please check the server logs."}
    if not hasattr(x_service, 'authenticated') or not x_service.authenticated:
        return False, {"status": "error", "message": "X service not authenticated. Please log in first."}
    return True, {}

def format_user(user) -> Dict[str, Any]:
    """Format user object into a standard dictionary."""
    return {
        "id": user.id,
        "name": user.name,
        "screen_name": user.screen_name,
        "description": user.description,
        "profile_image_url": user.profile_image_url,
        "followers_count": user.followers_count,
        "following_count": user.following_count,
        "statuses_count": user.statuses_count,
        "created_at": user.created_at,
        "verified": user.verified,
        "location": user.location if hasattr(user, 'location') else None,
        "url": user.url if hasattr(user, 'url') else None,
        "protected": user.protected if hasattr(user, 'protected') else False
    }

def format_tweet(tweet) -> Dict[str, Any]:
    """Format tweet object into a standard dictionary."""
    tweet_data = {
        "id": tweet.id,
        "text": tweet.text,
        "created_at": tweet.created_at,
        "favorite_count": tweet.favorite_count,
        "retweet_count": tweet.retweet_count,
        "reply_count": tweet.reply_count
    }
    
    if hasattr(tweet, 'quote_count'):
        tweet_data["quote_count"] = tweet.quote_count
        
    if hasattr(tweet, 'view_count') and tweet.view_count:
        tweet_data["view_count"] = tweet.view_count
    
    if hasattr(tweet, 'user') and tweet.user:
        tweet_data["user"] = {
            "id": tweet.user.id,
            "name": tweet.user.name,
            "screen_name": tweet.user.screen_name,
            "profile_image_url": tweet.user.profile_image_url
        }
    
    if hasattr(tweet, 'media') and tweet.media:
        tweet_data["media"] = [{
            "type": media.type, 
            "url": media.media_url,
            "width": media.width,
            "height": media.height
        } for media in tweet.media]
    
    return tweet_data

# ---- Tweet Management Tools ----

@mcp.tool()
async def post_tweet(x_service, text: str) -> dict:
    """
    Post a tweet to the authenticated user's X timeline.
    
    This tool allows you to post a tweet with the specified text content.
    The text will be truncated if it exceeds 280 characters.
    
    Args:
        text (str): The text content of the tweet (1-280 characters).
            - Can include hashtags, mentions, and links.
            - Emojis and most Unicode characters are supported.
            - Will be automatically trimmed to 280 characters if longer.
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
            - tweet_id (str, optional): The ID of the posted tweet on success
            - text (str, optional): The actual text that was posted
    
    Example:
        Post a simple tweet: "Hello, world! #testing"
        
        Post an announcement: "We just launched our new product! Check it out at https://example.com"
    """
    # Input validation
    if not text or not isinstance(text, str) or len(text.strip()) == 0:
        return {"status": "error", "message": "Tweet text cannot be empty"}
    
    # Truncate text to 280 characters if needed
    text = text.strip()
    if len(text) > 280:
        text = text[:280]
    
    # Check service status
    is_ready, error_response = check_x_service(x_service)
    if not is_ready:
        return error_response
    
    # Post the tweet
    try:
        print(f"[DEBUG] Attempting to post tweet: {text[:50]}...")
        result = await x_service.post_tweet(text)
        print(f"[DEBUG] Tweet posted successfully: {result.get('tweet_id', 'unknown')}")
        return result
    except Exception as e:
        error_msg = f"Failed to post tweet: {str(e)}"
        print(f"[ERROR] {error_msg}")
        traceback.print_exc()
        return {"status": "error", "message": error_msg}

@mcp.tool()
async def search_tweets(x_service, query: str, count: int = 10, mode: str = 'Latest') -> dict:
    """
    Search for tweets matching a specific query.
    
    This tool searches X for tweets matching the given query string.
    Results are returned based on the specified mode (default: newest first).
    
    Args:
        query (str): The search query string.
            - Can include keywords, hashtags, and operators like "from:username".
            - Supports advanced search operators (see X's search documentation).
        count (int, optional): Number of tweets to return. Defaults to 10.
            - Must be between 1 and 20 (inclusive).
            - Values outside this range will be clamped.
        mode (str, optional): Search mode. Defaults to 'Latest'.
            - 'Latest': Most recent tweets
            - 'Top': Most relevant tweets
            - 'People': User accounts
            - 'Photos': Tweets with photos
            - 'Videos': Tweets with videos
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
            - tweets (list): List of matching tweets on success
            - count (int): Number of tweets returned
    
    Example:
        Search for latest tweets about Python: "python"
        
        Find the top tweets about AI: "artificial intelligence" mode=Top
        
        Search for tweets with photos about nature: "nature photography" mode=Photos
    """
    # Input validation
    if not query or not isinstance(query, str) or len(query.strip()) == 0:
        return {"status": "error", "message": "Search query cannot be empty"}
    
    # Validate mode
    valid_modes = ['Latest', 'Top', 'People', 'Photos', 'Videos']
    if mode not in valid_modes:
        return {"status": "error", "message": f"Invalid mode. Must be one of: {', '.join(valid_modes)}"}
    
    # Clamp count between 1 and 20
    count = max(1, min(20, int(count) if str(count).isdigit() else 10))
    
    # Check service status
    is_ready, error_response = check_x_service(x_service)
    if not is_ready:
        return error_response
    
    # Perform the search
    try:
        print(f"[DEBUG] Searching for tweets with query: '{query}' (count: {count}, mode: {mode})")
        results = await x_service.search_tweets(query, count=count, mode=mode)
        print(f"[DEBUG] Found {len(results.get('tweets', []))} tweets")
        return results
    except Exception as e:
        error_msg = f"Error searching tweets: {str(e)}"
        print(f"[ERROR] {error_msg}")
        traceback.print_exc()
        return {"status": "error", "message": error_msg}

# ---- Additional Tweet Tools ----

@mcp.tool()
async def delete_tweet(x_service, tweet_id: str) -> dict:
    """
    Delete a tweet from the authenticated user's timeline.
    
    Args:
        tweet_id (str): The ID of the tweet to delete.
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
    
    Example:
        Delete a specific tweet: "1234567890"
    """
    # Validate input
    is_valid, error = validate_id(tweet_id, "Tweet ID")
    if not is_valid:
        return error
    
    # Check service status
    is_ready, error_response = check_x_service(x_service)
    if not is_ready:
        return error_response
    
    # Delete the tweet
    try:
        log_debug("delete_tweet", f"Attempting to delete tweet with ID: {tweet_id}")
        response = await x_service._client.delete_tweet(tweet_id)
        return {"status": "success", "message": "Tweet successfully deleted"}
    except Exception as e:
        error_msg = f"Failed to delete tweet: {str(e)}"
        log_error("delete_tweet", error_msg, e)
        return {"status": "error", "message": error_msg}

@mcp.tool()
async def get_tweet_by_id(x_service, tweet_id: str) -> dict:
    """
    Retrieve a specific tweet by its ID.
    
    Args:
        tweet_id (str): The ID of the tweet to retrieve.
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
            - tweet (dict, optional): Details of the retrieved tweet
    
    Example:
        Get details of a specific tweet: "1234567890"
    """
    # Validate input
    is_valid, error = validate_id(tweet_id, "Tweet ID")
    if not is_valid:
        return error
    
    # Check service status
    is_ready, error_response = check_x_service(x_service)
    if not is_ready:
        return error_response
    
    # Get the tweet
    try:
        log_debug("get_tweet_by_id", f"Retrieving tweet with ID: {tweet_id}")
        tweet = await x_service._client.get_tweet_by_id(tweet_id)
        
        # Format the tweet data using helper function
        formatted_tweet = format_tweet(tweet)
        
        return {
            "status": "success",
            "message": "Successfully retrieved tweet",
            "tweet": formatted_tweet
        }
    except Exception as e:
        error_msg = f"Failed to retrieve tweet: {str(e)}"
        log_error("get_tweet_by_id", error_msg, e)
        return {"status": "error", "message": error_msg}

@mcp.tool()
async def create_tweet_with_poll(x_service, text: str, choices: List[str], duration_minutes: int = 1440) -> dict:
    """
    Create a tweet with a poll.
    
    Args:
        text (str): The text content of the tweet.
        choices (List[str]): List of poll options (2-4 choices).
        duration_minutes (int, optional): How long the poll should remain open in minutes.
            Default is 1440 (24 hours). Maximum is 10080 (7 days).
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
            - tweet_id (str, optional): The ID of the posted tweet on success
    
    Example:
        Ask about programming preferences: "What's your favorite programming language?" 
        choices=["Python", "JavaScript", "Rust", "Go"] duration_minutes=4320
        
        Create a customer survey: "How would you rate our service?" 
        choices=["Excellent", "Good", "Average", "Poor"]
    """
    # Validate text
    is_valid, result = validate_text(text)
    if not is_valid:
        return result
    text = result["text"]
    
    # Validate choices
    if not choices or not isinstance(choices, list):
        return {"status": "error", "message": "Poll choices must be a non-empty list"}
    
    if len(choices) < 2 or len(choices) > 4:
        return {"status": "error", "message": "Poll must have between 2 and 4 choices"}
    
    # Validate duration
    try:
        duration_minutes = int(duration_minutes)
        if duration_minutes < 5 or duration_minutes > 10080:
            return {"status": "error", "message": "Poll duration must be between 5 minutes and 7 days (10080 minutes)"}
    except (ValueError, TypeError):
        return {"status": "error", "message": "Poll duration must be a valid number"}
    
    # Check service status
    is_ready, error_response = check_x_service(x_service)
    if not is_ready:
        return error_response
    
    # Create poll and tweet
    try:
        log_debug("create_tweet_with_poll", f"Creating poll with {len(choices)} choices and duration {duration_minutes} minutes")
        poll_uri = await x_service._client.create_poll(choices, duration_minutes)
        
        log_debug("create_tweet_with_poll", f"Creating tweet with poll_uri: {poll_uri}")
        tweet = await x_service._client.create_tweet(text=text, poll_uri=poll_uri)
        
        return {
            "status": "success",
            "message": "Successfully created tweet with poll",
            "tweet_id": tweet.id
        }
    except Exception as e:
        error_msg = f"Failed to create tweet with poll: {str(e)}"
        log_error("create_tweet_with_poll", error_msg, e)
        return {"status": "error", "message": error_msg}

# More tools will be implemented here...

# ---- Schedule and Engagement Tools ----

@mcp.tool()
async def get_scheduled_tweets(x_service) -> dict:
    """
    Retrieve all scheduled tweets for the authenticated user.
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
            - tweets (list, optional): List of scheduled tweets with their details
    
    Example:
        View all scheduled tweets: (no parameters needed)
    """
    # Check service status
    is_ready, error_response = check_x_service(x_service)
    if not is_ready:
        return error_response
    
    # Get scheduled tweets
    try:
        log_debug("get_scheduled_tweets", "Retrieving scheduled tweets")
        scheduled_tweets = await x_service._client.get_scheduled_tweets()
        
        # Format the results
        formatted_tweets = []
        for tweet in scheduled_tweets:
            formatted_tweets.append({
                "id": tweet.id,
                "text": tweet.text,
                "scheduled_at": tweet.scheduled_at,
                "media_ids": tweet.media_ids if hasattr(tweet, 'media_ids') else []
            })
        
        return {
            "status": "success",
            "message": f"Successfully retrieved {len(formatted_tweets)} scheduled tweets",
            "tweets": formatted_tweets
        }
    except Exception as e:
        error_msg = f"Failed to retrieve scheduled tweets: {str(e)}"
        log_error("get_scheduled_tweets", error_msg, e)
        return {"status": "error", "message": error_msg}

@mcp.tool()
async def create_scheduled_tweet(x_service, text: str, scheduled_at: int, media_ids: List[str] = None) -> dict:
    """
    Schedule a tweet to be posted at a specific time.
    
    Args:
        text (str): The text content of the tweet.
        scheduled_at (int): Unix timestamp (in seconds) for when the tweet should be posted.
        media_ids (List[str], optional): List of media IDs to attach to the tweet.
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
            - tweet_id (str, optional): The ID of the scheduled tweet on success
    
    Example:
        Schedule an announcement: "We're going live tomorrow!" scheduled_at=1717527600
        
        Schedule a reminder: "Don't forget to register for the event" scheduled_at=1716523200
    """
    # Validate text
    is_valid, result = validate_text(text)
    if not is_valid:
        return result
    text = result["text"]
    
    # Validate scheduled_at
    try:
        scheduled_at = int(scheduled_at)
        current_time = int(time.time())
        
        # Ensure scheduled time is in the future
        if scheduled_at <= current_time:
            return {"status": "error", "message": "Scheduled time must be in the future"}
    except (ValueError, TypeError):
        return {"status": "error", "message": "Scheduled time must be a valid Unix timestamp (in seconds)"}
    
    # Validate media_ids if provided
    if media_ids and not isinstance(media_ids, list):
        return {"status": "error", "message": "Media IDs must be a list"}
    
    # Check service status
    is_ready, error_response = check_x_service(x_service)
    if not is_ready:
        return error_response
    
    # Create scheduled tweet
    try:
        log_debug("create_scheduled_tweet", f"Scheduling tweet for timestamp {scheduled_at}")
        tweet_id = await x_service._client.create_scheduled_tweet(
            scheduled_at=scheduled_at,
            text=text,
            media_ids=media_ids
        )
        
        return {
            "status": "success",
            "message": "Successfully scheduled tweet",
            "tweet_id": tweet_id
        }
    except Exception as e:
        error_msg = f"Failed to schedule tweet: {str(e)}"
        log_error("create_scheduled_tweet", error_msg, e)
        return {"status": "error", "message": error_msg}

@mcp.tool()
async def unfavorite_tweet(x_service, tweet_id: str) -> dict:
    """
    Unlike/unfavorite a tweet.
    
    Args:
        tweet_id (str): The ID of the tweet to unlike.
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
    
    Example:
        Unlike a previously liked tweet: "1234567890"
    """
    # Validate input
    is_valid, error = validate_id(tweet_id, "Tweet ID")
    if not is_valid:
        return error
    
    # Check service status
    is_ready, error_response = check_x_service(x_service)
    if not is_ready:
        return error_response
    
    # Unlike the tweet
    try:
        log_debug("unfavorite_tweet", f"Unliking tweet with ID: {tweet_id}")
        await x_service._client.unfavorite_tweet(tweet_id)
        return {"status": "success", "message": "Successfully unliked tweet"}
    except Exception as e:
        error_msg = f"Failed to unlike tweet: {str(e)}"
        log_error("unfavorite_tweet", error_msg, e)
        return {"status": "error", "message": error_msg}

@mcp.tool()
async def retweet(x_service, tweet_id: str) -> dict:
    """
    Retweet a tweet.
    
    Args:
        tweet_id (str): The ID of the tweet to retweet.
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
    
    Example:
        Retweet an interesting post: "1234567890"
    """
    # Validate input
    is_valid, error = validate_id(tweet_id, "Tweet ID")
    if not is_valid:
        return error
    
    # Check service status
    is_ready, error_response = check_x_service(x_service)
    if not is_ready:
        return error_response
    
    # Retweet the tweet
    try:
        log_debug("retweet", f"Retweeting tweet with ID: {tweet_id}")
        await x_service._client.retweet(tweet_id)
        return {"status": "success", "message": "Successfully retweeted tweet"}
    except Exception as e:
        error_msg = f"Failed to retweet: {str(e)}"
        log_error("retweet", error_msg, e)
        return {"status": "error", "message": error_msg}

@mcp.tool()
async def get_retweeters(x_service, tweet_id: str, count: int = 20) -> dict:
    """
    Get a list of users who retweeted a specific tweet.
    
    Args:
        tweet_id (str): The ID of the tweet.
        count (int, optional): The number of retweeters to retrieve. Default is 20.
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
            - users (list, optional): List of users who retweeted the tweet
    
    Example:
        Find who retweeted a viral post: "1234567890" count=30
    """
    # Validate input
    is_valid, error = validate_id(tweet_id, "Tweet ID")
    if not is_valid:
        return error
    
    # Normalize count
    count = validate_count(count, 1, 40)
    
    # Check service status
    is_ready, error_response = check_x_service(x_service)
    if not is_ready:
        return error_response
    
    # Get retweeters
    try:
        log_debug("get_retweeters", f"Getting retweeters for tweet ID: {tweet_id}, count: {count}")
        users_result = await x_service._client.get_retweeters(tweet_id, count)
        
        # Format the users
        formatted_users = []
        for user in users_result:
            formatted_users.append({
                "id": user.id,
                "name": user.name,
                "screen_name": user.screen_name,
                "profile_image_url": user.profile_image_url,
                "followers_count": user.followers_count,
                "following_count": user.following_count
            })
            
        return {
            "status": "success", 
            "message": f"Successfully retrieved {len(formatted_users)} retweeters",
            "users": formatted_users
        }
    except Exception as e:
        error_msg = f"Failed to get retweeters: {str(e)}"
        log_error("get_retweeters", error_msg, e)
        return {"status": "error", "message": error_msg}

# ---- User Tools ----

@mcp.tool()
async def get_user_by_screen_name(x_service, screen_name: str) -> dict:
    """
    Get user information by their screen name (handle).
    
    Args:
        screen_name (str): The screen name/handle of the user (without the @ symbol).
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
            - user (dict, optional): Details of the user
    
    Example:
        Get profile information for Elon Musk: "elonmusk"
        
        Get information about NASA: "NASA"
    """
    # Validate input
    if not screen_name or not isinstance(screen_name, str) or len(screen_name.strip()) == 0:
        return {"status": "error", "message": "Screen name cannot be empty"}
    
    # Remove @ if present
    screen_name = screen_name.strip()
    if screen_name.startswith('@'):
        screen_name = screen_name[1:]
    
    # Check service status
    is_ready, error_response = check_x_service(x_service)
    if not is_ready:
        return error_response
    
    # Get user
    try:
        log_debug("get_user_by_screen_name", f"Getting user with screen name: {screen_name}")
        user = await x_service._client.get_user_by_screen_name(screen_name)
        
        # Format user data using helper function
        formatted_user = format_user(user)
        
        return {
            "status": "success",
            "message": "Successfully retrieved user",
            "user": formatted_user
        }
    except Exception as e:
        error_msg = f"Failed to get user: {str(e)}"
        log_error("get_user_by_screen_name", error_msg, e)
        return {"status": "error", "message": error_msg}

@mcp.tool()
async def get_user_tweets(x_service, user_id: str, tweet_type: TweetType = 'Tweets', count: int = 20) -> dict:
    """
    Get tweets from a specific user.
    
    Args:
        user_id (str): The ID of the user.
        tweet_type (str, optional): The type of tweets to retrieve. Options:
            - 'Tweets': Standard tweets (default)
            - 'Replies': Tweets that are replies to other tweets
            - 'Media': Tweets containing media
            - 'Likes': Tweets the user has liked
        count (int, optional): The number of tweets to retrieve. Default is 20.
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
            - tweets (list, optional): List of retrieved tweets
    
    Example:
        Get latest tweets from a user: "44196397" count=15
        
        Get media posts from a user: "783214" tweet_type=Media count=10
        
        Get liked tweets from a user: "44196397" tweet_type=Likes
    """
    # Validate input
    is_valid, error = validate_id(user_id, "User ID")
    if not is_valid:
        return error
    
    # Validate tweet_type
    valid_types = ['Tweets', 'Replies', 'Media', 'Likes']
    is_valid, error = validate_mode(tweet_type, valid_types)
    if not is_valid:
        return error
    
    # Normalize count
    count = validate_count(count, 1, 100)
    
    # Check service status
    is_ready, error_response = check_x_service(x_service)
    if not is_ready:
        return error_response
    
    # Get tweets
    try:
        log_debug("get_user_tweets", f"Getting {tweet_type} for user: {user_id}, count: {count}")
        tweets_result = await x_service._client.get_user_tweets(user_id, tweet_type, count)
        
        # Format tweets
        formatted_tweets = []
        for tweet in tweets_result:
            formatted_tweets.append(format_tweet(tweet))
        
        return {
            "status": "success",
            "message": f"Successfully retrieved {len(formatted_tweets)} {tweet_type.lower()}",
            "tweets": formatted_tweets,
            "cursor": tweets_result.next_cursor if hasattr(tweets_result, 'next_cursor') else None
        }
    except Exception as e:
        error_msg = f"Failed to get user tweets: {str(e)}"
        log_error("get_user_tweets", error_msg, e)
        return {"status": "error", "message": error_msg}

@mcp.tool()
async def get_user_media(x_service, user_id: str, count: int = 20) -> dict:
    """
    Get media tweets from a specific user.
    
    Args:
        user_id (str): The ID of the user.
        count (int, optional): The number of media tweets to retrieve. Default is 20.
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
            - tweets (list, optional): List of media tweets
    
    Example:
        Get photos and videos from NASA: "11348282" count=30
    """
    # This is a convenience wrapper around get_user_tweets with tweet_type='Media'
    return await get_user_tweets(x_service, user_id, 'Media', count)

@mcp.tool()
async def get_user_likes(x_service, user_id: str, count: int = 20) -> dict:
    """
    Get tweets liked by a specific user.
    
    Args:
        user_id (str): The ID of the user.
        count (int, optional): The number of liked tweets to retrieve. Default is 20.
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
            - tweets (list, optional): List of liked tweets
    
    Example:
        See what tweets a user has liked recently: "783214" count=25
    """
    # This is a convenience wrapper around get_user_tweets with tweet_type='Likes'
    return await get_user_tweets(x_service, user_id, 'Likes', count)

# ---- User Interaction Tools ----

@mcp.tool()
async def follow_user(x_service, user_id: str) -> dict:
    """
    Follow a user on X.
    
    Args:
        user_id (str): The ID of the user to follow.
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
            - user (dict, optional): Details of the followed user
    
    Example:
        Follow a specific account: "11348282"
    """
    # Validate input
    is_valid, error = validate_id(user_id, "User ID")
    if not is_valid:
        return error
    
    # Check service status
    is_ready, error_response = check_x_service(x_service)
    if not is_ready:
        return error_response
    
    # Follow the user
    try:
        log_debug("follow_user", f"Following user with ID: {user_id}")
        user = await x_service._client.follow_user(user_id)
        
        # Format the user data
        formatted_user = format_user(user)
        
        return {
            "status": "success",
            "message": f"Successfully followed @{user.screen_name}",
            "user": formatted_user
        }
    except Exception as e:
        error_msg = f"Failed to follow user: {str(e)}"
        log_error("follow_user", error_msg, e)
        return {"status": "error", "message": error_msg}

@mcp.tool()
async def get_user_followers(x_service, user_id: str, count: int = 20) -> dict:
    """
    Get a list of followers for a specific user.
    
    Args:
        user_id (str): The ID of the user.
        count (int, optional): The number of followers to retrieve. Default is 20.
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
            - users (list, optional): List of follower users
    
    Example:
        See who follows a specific account: "783214" count=40
    """
    # Validate input
    is_valid, error = validate_id(user_id, "User ID")
    if not is_valid:
        return error
    
    # Normalize count
    count = validate_count(count, 1, 50)
    
    # Check service status
    is_ready, error_response = check_x_service(x_service)
    if not is_ready:
        return error_response
    
    # Get followers
    try:
        log_debug("get_user_followers", f"Getting followers for user: {user_id}, count: {count}")
        users_result = await x_service._client.get_user_followers(user_id, count)
        
        # Format the users
        formatted_users = []
        for user in users_result:
            formatted_users.append(format_user(user))
        
        return {
            "status": "success",
            "message": f"Successfully retrieved {len(formatted_users)} followers",
            "users": formatted_users
        }
    except Exception as e:
        error_msg = f"Failed to get followers: {str(e)}"
        log_error("get_user_followers", error_msg, e)
        return {"status": "error", "message": error_msg}

@mcp.tool()
async def get_user_following(x_service, user_id: str, count: int = 20) -> dict:
    """
    Get a list of users that a specific user is following.
    
    Args:
        user_id (str): The ID of the user.
        count (int, optional): The number of following users to retrieve. Default is 20.
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
            - users (list, optional): List of users being followed
    
    Example:
        See who a specific account follows: "783214" count=30
    """
    # Validate input
    is_valid, error = validate_id(user_id, "User ID")
    if not is_valid:
        return error
    
    # Normalize count
    count = validate_count(count, 1, 50)
    
    # Check service status
    is_ready, error_response = check_x_service(x_service)
    if not is_ready:
        return error_response
    
    # Get following
    try:
        log_debug("get_user_following", f"Getting following for user: {user_id}, count: {count}")
        users_result = await x_service._client.get_user_following(user_id, count)
        
        # Format the users
        formatted_users = []
        for user in users_result:
            formatted_users.append(format_user(user))
        
        return {
            "status": "success",
            "message": f"Successfully retrieved {len(formatted_users)} following",
            "users": formatted_users
        }
    except Exception as e:
        error_msg = f"Failed to get following: {str(e)}"
        log_error("get_user_following", error_msg, e)
        return {"status": "error", "message": error_msg}

# ---- Direct Message Tools ----

@mcp.tool()
async def send_dm(x_service, user_id: str, text: str, media_id: str = None) -> dict:
    """
    Send a direct message to a user.
    
    Args:
        user_id (str): The ID of the user to whom the direct message will be sent.
        text (str): The text content of the direct message.
        media_id (str, optional): The media ID associated with any media content to be included.
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
            - dm_id (str, optional): The ID of the sent message
    
    Example:
        Send a simple message: "783214" text="Hello, how are you?"
        
        Send a message with an image: "44196397" text="Check out this photo!" media_id="1234567890"
    """
    # Validate input
    is_valid, error = validate_id(user_id, "User ID")
    if not is_valid:
        return error
    
    # Validate text
    is_valid, result = validate_text(text, max_length=10000)  # DMs can be longer than tweets
    if not is_valid:
        return result
    text = result["text"]
    
    # Validate media_id if provided
    if media_id and not isinstance(media_id, str):
        return {"status": "error", "message": "Media ID must be a string"}
    
    # Check service status
    is_ready, error_response = check_x_service(x_service)
    if not is_ready:
        return error_response
    
    # Send the DM
    try:
        log_debug("send_dm", f"Sending DM to user: {user_id}")
        message = await x_service._client.send_dm(user_id, text, media_id)
        
        return {
            "status": "success",
            "message": "Successfully sent direct message",
            "dm_id": message.id
        }
    except Exception as e:
        error_msg = f"Failed to send direct message: {str(e)}"
        log_error("send_dm", error_msg, e)
        return {"status": "error", "message": error_msg}

@mcp.tool()
async def get_dm_history(x_service, user_id: str, max_id: str = None) -> dict:
    """
    Retrieve the direct message conversation history with a specific user.
    
    Args:
        user_id (str): The ID of the user with whom the DM conversation history will be retrieved.
        max_id (str, optional): If specified, retrieves messages older than the specified max_id.
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
            - messages (list, optional): List of direct messages
    
    Example:
        Get conversation history: "783214"
        
        Get older messages: "44196397" max_id="1234567890"
    """
    # Validate input
    is_valid, error = validate_id(user_id, "User ID")
    if not is_valid:
        return error
    
    # Check service status
    is_ready, error_response = check_x_service(x_service)
    if not is_ready:
        return error_response
    
    # Get DM history
    try:
        log_debug("get_dm_history", f"Getting DM history with user: {user_id}")
        messages_result = await x_service._client.get_dm_history(user_id, max_id)
        
        # Format the messages
        formatted_messages = []
        for msg in messages_result:
            formatted_messages.append({
                "id": msg.id,
                "text": msg.text,
                "time": msg.time,
                "sender_id": msg.sender_id if hasattr(msg, 'sender_id') else None,
                "attachment": msg.attachment if hasattr(msg, 'attachment') else None
            })
        
        return {
            "status": "success",
            "message": f"Successfully retrieved {len(formatted_messages)} messages",
            "messages": formatted_messages,
            "cursor": messages_result.next_cursor if hasattr(messages_result, 'next_cursor') else None
        }
    except Exception as e:
        error_msg = f"Failed to get DM history: {str(e)}"
        log_error("get_dm_history", error_msg, e)
        return {"status": "error", "message": error_msg}

@mcp.tool()
async def delete_dm(x_service, message_id: str) -> dict:
    """
    Delete a direct message.
    
    Args:
        message_id (str): The ID of the direct message to delete.
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
    
    Example:
        Delete a specific direct message: "1234567890"
    """
    # Validate input
    is_valid, error = validate_id(message_id, "Message ID")
    if not is_valid:
        return error
    
    # Check service status
    is_ready, error_response = check_x_service(x_service)
    if not is_ready:
        return error_response
    
    # Delete the DM
    try:
        log_debug("delete_dm", f"Deleting DM with ID: {message_id}")
        await x_service._client.delete_dm(message_id)
        
        return {
            "status": "success",
            "message": "Successfully deleted direct message"
        }
    except Exception as e:
        error_msg = f"Failed to delete direct message: {str(e)}"
        log_error("delete_dm", error_msg, e)
        return {"status": "error", "message": error_msg}

# ---- Trending Tools ----

@mcp.tool()
async def get_trends(x_service, category: TrendType = 'trending') -> dict:
    """
    Get trending topics on X.
    
    Args:
        category (str, optional): The category of trends to retrieve. Valid options:
            - 'trending': General trending topics (default)
            - 'for-you': Trends personalized for the user
            - 'news': News-related trends
            - 'sports': Sports-related trends
            - 'entertainment': Entertainment-related trends
    
    Returns:
        dict: A dictionary containing:
            - status (str): "success" or "error"
            - message (str): Description of the result
            - trends (list, optional): List of trending topics
    
    Example:
        Get general trending topics: category="trending"
        
        Get news trends: category="news"
        
        Get entertainment trends: category="entertainment"
    """
    # Validate category
    valid_categories = ['trending', 'for-you', 'news', 'sports', 'entertainment']
    is_valid, error = validate_mode(category, valid_categories)
    if not is_valid:
        return error
    
    # Check service status
    is_ready, error_response = check_x_service(x_service)
    if not is_ready:
        return error_response
    
    # Get trends
    try:
        log_debug("get_trends", f"Getting trends for category: {category}")
        trends = await x_service._client.get_trends(category)
        
        # Format the trends
        formatted_trends = []
        for trend in trends:
            formatted_trends.append({
                "name": trend.name,
                "tweets_count": trend.tweets_count if hasattr(trend, 'tweets_count') else None,
                "domain_context": trend.domain_context if hasattr(trend, 'domain_context') else None
            })
        
        return {
            "status": "success",
            "message": f"Successfully retrieved {len(formatted_trends)} {category} trends",
            "trends": formatted_trends
        }
    except Exception as e:
        error_msg = f"Failed to get trends: {str(e)}"
        log_error("get_trends", error_msg, e)
        return {"status": "error", "message": error_msg}
