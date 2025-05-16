import asyncio
import os
import sys
import json
import traceback
import functools
from pathlib import Path
from typing import Dict, Optional, Any
from fastmcp import FastMCP
from urllib.parse import urlparse

# Add the python_bridge directory to the path
python_bridge_dir = str(Path(__file__).parent / "python_bridge")
if python_bridge_dir not in sys.path:
    sys.path.append(python_bridge_dir)

# Import TwitterAuthenticator and other necessary components
from playwright_login_and_export import TwitterAuthenticator
from twikit import Client
from twikit.x_client_transaction import ClientTransaction as TwikitClientTransactionInternal
from x_client_transaction import ClientTransaction as YourCustomClientTransaction
import bs4

# Initialize the FastMCP server
mcp = FastMCP("Twikit MCP Server")

# Global variable for headers injection as in the reference implementation
HEADERS_TO_INJECT = {}

class TwitterService:
    def __init__(self, data_dir: str = None):
        global HEADERS_TO_INJECT
        self.authenticated = False
        self.username = None
        self.client = None
        self.data_dir = Path(data_dir) if data_dir else Path("python_bridge/twitter_data")
        self.original_twikit_ct_init = None
        self.original_twikit_ct_generate_id = None
        self.original_http_request_method = None
        
        # Initialize the TwitterAuthenticator
        self.auth = TwitterAuthenticator(data_dir=str(self.data_dir))
        print(f"Initialized TwitterAuthenticator with data_dir: {self.data_dir}")
    
    async def initialize_client(self):
        """Initialize the Twitter client with authentication"""
        global HEADERS_TO_INJECT
        try:
            print("Loading Playwright data...")
            common_headers = self.auth.get_common_headers()
            cookies_dict = self.auth.get_cookies_dict()
            home_html_str, ondemand_js_str = self.auth.get_public_transaction_generator_data()
            print("Playwright data loaded successfully")

            # Parse HTML/JS for transaction ID generation
            home_soup = bs4.BeautifulSoup(home_html_str, 'lxml')
            ondemand_soup = bs4.BeautifulSoup(ondemand_js_str, 'lxml')
            print("Parsed HTML/JS for transaction ID generation")

            # Initialize the client
            self.client = Client('en-US')
            print("Initialized twikit.Client")

            # Patch twikit's ClientTransaction class
            self.original_twikit_ct_init = TwikitClientTransactionInternal.init
            TwikitClientTransactionInternal.init = self.no_op_twikit_ct_init
            
            self.original_twikit_ct_generate_id = TwikitClientTransactionInternal.generate_transaction_id
            TwikitClientTransactionInternal.generate_transaction_id = self.no_op_twikit_ct_generate_id
            print("Patched twikit's ClientTransaction class")

            # Patch the HTTP client
            if hasattr(self.client, 'http') and hasattr(self.client.http, 'request'):
                self.original_http_request_method = self.client.http.request
                self.client.http.request = functools.partial(
                    self.patched_http_client_request, 
                    self.original_http_request_method
                )
                print("Patched client.http.request method")
            else:
                print("Error: client.http.request not available for patching")
                return {"status": "error", "message": "Failed to patch HTTP client"}
            
            self.client.enable_ui_metrics = False
            print(f"Set client.enable_ui_metrics to {self.client.enable_ui_metrics}")

            # Initialize custom ClientTransaction
            self.client_transaction = YourCustomClientTransaction(
                home_page_response=home_soup, 
                ondemand_file_response=ondemand_soup
            )
            print("Initialized custom ClientTransaction")

            # Set up headers for requests - matching the reference implementation
            cookie_header_value = "; ".join([f"{name}={value}" for name, value in cookies_dict.items()])
            ct0_token = cookies_dict.get('ct0')
            
            if not ct0_token:
                raise ValueError("No 'ct0' token found in cookies. Please log in first.")

            # Generate initial transaction ID for the create tweet endpoint
            gql_create_tweet_path = "/i/api/graphql/SiM_cAu83R0wnrpmKQQSEw/CreateTweet"
            transaction_id = self.client_transaction.generate_transaction_id(
                method="POST", 
                path=gql_create_tweet_path
            )
            print(f"Generated initial transaction ID: {transaction_id}")

            # Set up headers exactly as in the reference implementation
            HEADERS_TO_INJECT.update({
                "Cookie": cookie_header_value,
                "x-csrf-token": ct0_token,
                "x-client-transaction-id": transaction_id,
            })
            HEADERS_TO_INJECT.update(common_headers)
            print("Set up request headers")

            self.authenticated = True
            return {"status": "success", "message": "Twitter client initialized successfully"}

        except Exception as e:
            error_msg = f"Error initializing Twitter client: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            return {"status": "error", "message": error_msg}
    
    async def cleanup(self):
        """Clean up patches and resources"""
        try:
            if self.original_twikit_ct_init is not None:
                TwikitClientTransactionInternal.init = self.original_twikit_ct_init
            if self.original_twikit_ct_generate_id is not None:
                TwikitClientTransactionInternal.generate_transaction_id = self.original_twikit_ct_generate_id
            if hasattr(self, 'client') and self.client:
                await self.client.http.close()
            print("Cleaned up Twitter client resources")
        except Exception as e:
            print(f"Error during cleanup: {e}")
    
    async def patched_http_client_request(self, original_http_request_method, method, url, **kwargs):
        """Patch for the HTTP client to inject headers and handle transaction IDs
        
        This matches the implementation from post_tweet_with_playwright_session.py
        """
        global HEADERS_TO_INJECT
        try:
            # Log the request for debugging
            print(f"--- Patched http.request called for: {method} {url} ---")
            
            # Get headers from the caller
            headers_from_caller = kwargs.pop('headers', {})
            
            # Start with the global headers to inject
            final_headers = HEADERS_TO_INJECT.copy()
            
            # Merge with caller's headers, preserving content-type
            for key, value in headers_from_caller.items():
                if key.lower() == 'content-type':
                    final_headers[key] = value
                elif key not in final_headers:
                    final_headers[key] = value
            
            # Log the headers for debugging
            print(f"Original headers passed to http.request: {headers_from_caller}")
            print(f"Headers to Inject (from global): {HEADERS_TO_INJECT}")
            
            # For GraphQL endpoints, ensure we have a fresh transaction ID
            if '/i/api/graphql/' in url:
                path = urlparse(url).path
                transaction_id = self.client_transaction.generate_transaction_id(
                    method=method.upper(), 
                    path=path
                )
                final_headers['x-client-transaction-id'] = transaction_id
                print(f"Generated new transaction ID for {method} {path}: {transaction_id}")
            
            # Update the global headers with the final set
            kwargs['headers'] = final_headers
            print(f"Final headers for HTTP call: {final_headers}")
            
            # Make the actual request
            return await original_http_request_method(method, url, **kwargs)
            
        except Exception as e:
            error_msg = f"Error in patched_http_client_request: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            raise

    @staticmethod
    async def no_op_twikit_ct_init(self_ct, http_client, headers_arg):
        """No-op replacement for twikit's ClientTransaction.init"""
        if not hasattr(self_ct, 'home_page_response'):
            self_ct.home_page_response = True
        if not hasattr(self_ct, 'DEFAULT_KEY_BYTES_INDICES'):
            self_ct.DEFAULT_KEY_BYTES_INDICES = []
        if not hasattr(self_ct, 'DEFAULT_ROW_INDEX'):
            self_ct.DEFAULT_ROW_INDEX = 0
        return
    
    @staticmethod
    def no_op_twikit_ct_generate_id(self_ct, method, path, response=None, key=None, animation_key=None, time_now=None):
        """No-op replacement for twikit's ClientTransaction.generate_transaction_id"""
        return "dummy_transaction_id_from_twikit_patch"
    
    async def post_tweet(self, text: str) -> dict:
        """Post a tweet using the authenticated client"""
        if not self.authenticated or not self.client:
            return {"status": "error", "message": "Not authenticated. Please log in first."}
        
        try:
            print(f"Attempting to post tweet: '{text}'")
            tweet = await self.client.create_tweet(text=text)
            print(f"Successfully posted tweet with ID: {tweet.id}")
            return {
                "status": "success", 
                "message": "Successfully posted tweet",
                "tweet_id": tweet.id,
                "text": text
            }
        except Exception as e:
            error_msg = f"Failed to post tweet: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            return {"status": "error", "message": error_msg}
            
    async def search_tweets(self, query: str, count: int = 10, mode: str = 'Latest') -> dict:
        """
        Search for tweets matching the given query.
        
        Args:
            query (str): The search query string
            count (int): Number of tweets to return (1-20)
            mode (str): Search mode. One of: 'Top', 'Latest', 'People', 'Photos', 'Videos'
            
        Returns:
            dict: Dictionary with status, message, and tweets list
        """
        if not self.authenticated or not self.client:
            return {"status": "error", "message": "Not authenticated. Please log in first."}
            
        try:
            print(f"Searching for tweets with query: '{query}' (count: {count}, mode: {mode})")
            
            # Use the client to search for tweets
            # The second parameter is the search mode (e.g., 'Latest', 'Top', 'People', etc.)
            tweets = await self.client.search_tweet(query, mode, count=count)
            
            # Format the results
            formatted_tweets = []
            for tweet in tweets:
                # Handle created_at field (could be string or datetime)
                created_at = None
                if hasattr(tweet, 'created_at'):
                    if hasattr(tweet.created_at, 'isoformat'):
                        created_at = tweet.created_at.isoformat()
                    elif isinstance(tweet.created_at, str):
                        created_at = tweet.created_at
                
                formatted_tweets.append({
                    "id": getattr(tweet, 'id', None),
                    "text": getattr(tweet, 'text', ''),
                    "created_at": created_at,
                    "user": {
                        "id": tweet.user.id if hasattr(tweet, 'user') and tweet.user else None,
                        "name": tweet.user.name if hasattr(tweet, 'user') and tweet.user else None,
                        "screen_name": tweet.user.screen_name if hasattr(tweet, 'user') and tweet.user else None
                    },
                    "favorite_count": getattr(tweet, 'favorite_count', 0),
                    "retweet_count": getattr(tweet, 'retweet_count', 0),
                    "reply_count": getattr(tweet, 'reply_count', 0),
                    "quote_count": getattr(tweet, 'quote_count', 0),
                    "is_quote_status": getattr(tweet, 'is_quote_status', False),
                    "lang": getattr(tweet, 'lang', None)
                })
                
            return {
                "status": "success",
                "message": f"Successfully found {len(formatted_tweets)} tweets",
                "tweets": formatted_tweets,
                "count": len(formatted_tweets)
            }
            
        except Exception as e:
            error_msg = f"Error searching tweets: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            return {"status": "error", "message": error_msg}

# Initialize the Twitter service
twitter_service = None

def check_twitter_service() -> tuple[bool, dict]:
    """Check if the Twitter service is properly initialized and authenticated."""
    if not twitter_service:
        return False, {"status": "error", "message": "Twitter service not initialized. Please check the server logs."}
    if not hasattr(twitter_service, 'authenticated') or not twitter_service.authenticated:
        return False, {"status": "error", "message": "Twitter service not authenticated. Please log in first."}
    return True, {}

@mcp.tool()
async def post_tweet(text: str) -> dict:
    """
    Post a tweet to the authenticated user's Twitter timeline.
    
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
    
    Raises:
        Exception: If there's an error posting the tweet
    
    Example:
        ```python
        result = await post_tweet("Hello, Twitter! #testing")
        if result["status"] == "success":
            print(f"Posted tweet: {result['text']}")
        ```
    """
    # Input validation
    if not text or not isinstance(text, str) or len(text.strip()) == 0:
        return {"status": "error", "message": "Tweet text cannot be empty"}
    
    # Truncate text to 280 characters if needed
    text = text.strip()
    if len(text) > 280:
        text = text[:280]
    
    # Check service status
    is_ready, error_response = check_twitter_service()
    if not is_ready:
        return error_response
    
    # Post the tweet
    try:
        print(f"[DEBUG] Attempting to post tweet: {text[:50]}...")
        result = await twitter_service.post_tweet(text)
        print(f"[DEBUG] Tweet posted successfully: {result.get('tweet_id', 'unknown')}")
        return result
    except Exception as e:
        error_msg = f"Failed to post tweet: {str(e)}"
        print(f"[ERROR] {error_msg}")
        traceback.print_exc()
        return {"status": "error", "message": error_msg}

@mcp.tool()
async def search_tweets(query: str, count: int = 10, mode: str = 'Latest') -> dict:
    """
    Search for tweets matching a specific query.
    
    This tool searches Twitter for tweets matching the given query string.
    Results are returned based on the specified mode (default: newest first).
    
    Args:
        query (str): The search query string.
            - Can include keywords, hashtags, and operators like "from:username".
            - Supports advanced search operators (see Twitter's search documentation).
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
    
    Raises:
        Exception: If there's an error performing the search
    
    Example:
        ```python
        # Get latest tweets
        results = await search_tweets("#python", count=5, mode="Latest")
        
        # Get top tweets
        top_results = await search_tweets("#python", count=5, mode="Top")
        
        if results["status"] == "success":
            for tweet in results["tweets"]:
                print(f"{tweet['user']['name']}: {tweet['text']}")
        ```
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
    is_ready, error_response = check_twitter_service()
    if not is_ready:
        return error_response
    
    # Perform the search
    try:
        print(f"[DEBUG] Searching for tweets with query: '{query}' (count: {count}, mode: {mode})")
        results = await twitter_service.search_tweets(query, count=count, mode=mode)
        print(f"[DEBUG] Found {len(results.get('tweets', []))} tweets")
        return results
    except Exception as e:
        error_msg = f"Error searching tweets: {str(e)}"
        print(f"[ERROR] {error_msg}")
        traceback.print_exc()
        return {"status": "error", "message": error_msg}

# Run the server if this file is executed directly
if __name__ == "__main__":
    import asyncio
    
    async def main():
        global twitter_service
        try:
            # Initialize the Twitter service
            print("Initializing Twitter service...")
            twitter_service = TwitterService(data_dir=os.path.join(os.path.dirname(__file__), "python_bridge", "twitter_data"))
            init_result = await twitter_service.initialize_client()
            print("Twitter service initialization result:", init_result)
            
            if init_result["status"] != "success":
                print("Failed to initialize Twitter service")
                return
                
            # Run the MCP server
            print("Starting MCP server...")
            await mcp.run_async()
            
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
        finally:
            # Clean up resources
            if twitter_service is not None:
                await twitter_service.cleanup()
    
    # Run the main coroutine
    asyncio.run(main())
