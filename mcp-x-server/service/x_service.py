import os
import sys
import traceback
from pathlib import Path
from typing import Dict, Optional, Any
import bs4

from twikit import Client
from x_client_transaction import ClientTransaction

from auth.x_authenticator import XAuthenticator
from utils.client_patcher import ClientPatcher

class XService:
    """
    Service for interacting with the X API
    """
    def __init__(self, data_dir: str = None):
        """
        Initialize the X service with optional data directory
        
        Args:
            data_dir: Directory where X auth data is stored
        """
        # Use environment variable for data directory if set
        env_data_dir = os.environ.get("X_DATA_DIR")
        if env_data_dir:
            self.data_dir = Path(env_data_dir)
        elif data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "../auth/x_data"
            
        self.authenticated = False
        self.username = None
        self.client = None
        self.client_patcher = None
        self.client_transaction = None
        
        # Initialize the XAuthenticator
        self.auth = XAuthenticator(data_dir=str(self.data_dir))
        print(f"Initialized XAuthenticator with data_dir: {self.data_dir}")
    
    async def initialize_client(self):
        """Initialize the X client with authentication"""
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

            # Initialize custom ClientTransaction
            self.client_transaction = ClientTransaction(
                home_page_response=home_soup, 
                ondemand_file_response=ondemand_soup
            )
            print("Initialized custom ClientTransaction")
            
            # Initialize and apply the client patcher
            self.client_patcher = ClientPatcher(self.client_transaction)
            self.client_patcher.patch_client(self.client)
            print("Applied client patches")

            # Set up headers for requests
            cookie_header_value = "; ".join([f"{name}={value}" for name, value in cookies_dict.items()])
            ct0_token = cookies_dict.get('ct0')
            
            if not ct0_token:
                raise ValueError("No 'ct0' token found in cookies. Please log in first.")

            # Set up the headers
            self.client_patcher.setup_headers(cookie_header_value, ct0_token)
            self.client_patcher.update_headers(common_headers)
            print("Set up request headers")

            self.authenticated = True
            return {"status": "success", "message": "X client initialized successfully"}

        except Exception as e:
            error_msg = f"Error initializing X client: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            return {"status": "error", "message": error_msg}
    
    async def cleanup(self):
        """Clean up patches and resources"""
        try:
            if self.client_patcher:
                self.client_patcher.cleanup()
                
            if hasattr(self, 'client') and self.client:
                await self.client.http.close()
                
            print("Cleaned up X service resources")
        except Exception as e:
            print(f"Error during cleanup: {e}")
    
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
