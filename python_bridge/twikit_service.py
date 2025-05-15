import asyncio
import json
import sys
import os
from pathlib import Path
from urllib.parse import urlparse
import importlib.util
import bs4
import functools
from twikit import Client
from twikit.x_client_transaction import ClientTransaction as TwikitClientTransactionInternal
from twikit.client.gql import Endpoint
from x_client_transaction import ClientTransaction as YourCustomClientTransaction
import traceback

# Import TwitterAuthenticator from playwright_login_and_export.py
from playwright_login_and_export import TwitterAuthenticator

# Global store for headers to inject into every HTTP request
HEADERS_TO_INJECT = {}

# Save the original print function before redefining it
_original_print = print

# Ensure all print statements go to stderr by default
def print_stderr(*args, **kwargs):
    """Print to stderr instead of stdout"""
    kwargs['file'] = sys.stderr
    _original_print(*args, **kwargs)

# Redirect standard print to stderr
print = print_stderr

# When sending JSON responses, use a dedicated function
def send_json_response(response_obj):
    """Send a JSON response to stdout for the Node.js process to read"""
    json_str = json.dumps(response_obj)
    sys.stdout.write(json_str + '\n')
    sys.stdout.flush()

async def patched_http_client_request(original_http_request_method, method, url, **kwargs):
    global HEADERS_TO_INJECT
    # Merge caller headers with our injected headers
    headers_from_caller = kwargs.pop('headers', {})
    final_headers = HEADERS_TO_INJECT.copy()
    for key, value in headers_from_caller.items():
        if key.lower() == 'content-type':
            final_headers[key] = value
        elif key not in final_headers:
            final_headers[key] = value
    kwargs['headers'] = final_headers
    return await original_http_request_method(method, url, **kwargs)

async def no_op_twikit_ct_init(self_ct, http_client, headers_arg):
    # Skip Twikit's internal ClientTransaction initialization
    if not hasattr(self_ct, 'home_page_response'):
        self_ct.home_page_response = True
    if not hasattr(self_ct, 'DEFAULT_KEY_BYTES_INDICES'):
        self_ct.DEFAULT_KEY_BYTES_INDICES = []
    if not hasattr(self_ct, 'DEFAULT_ROW_INDEX'):
        self_ct.DEFAULT_ROW_INDEX = 0
    return

def no_op_twikit_ct_generate_id(self_ct, method, path, response=None, key=None, animation_key=None, time_now=None):
    # We will generate our own transaction IDs via transaction_generator
    return "dummy"

async def main():
    env_data_dir_path = os.getenv('TWIKIT_DATA_DIR')

    if env_data_dir_path:
        # If TWIKIT_DATA_DIR is set, use it. Resolve to make it absolute.
        # It's assumed to be an absolute path or resolvable from the project root (Python script's CWD).
        data_dir = Path(env_data_dir_path).resolve()
        print_stderr(f"[twikit_service.py] Using TWIKIT_DATA_DIR: {str(data_dir)}\n")
    else:
        # Default to 'python_bridge/twitter_data' relative to the project root (which is CWD for this script)
        # This aligns with where playwright_login_and_export.py saves by default.
        # os.getcwd() here will be the project root directory.
        data_dir = (Path(os.getcwd()) / 'python_bridge' / 'twitter_data').resolve()
        print_stderr(f"[twikit_service.py] TWIKIT_DATA_DIR not set. Defaulting to: {str(data_dir)}\n")

    # Check if the directory exists
    if not data_dir.is_dir():
        print_stderr(f"[twikit_service.py] ERROR: Twitter data directory not found at the resolved path: {str(data_dir)}\n")
        print_stderr(f"[twikit_service.py] Please ensure the directory exists or set TWIKIT_DATA_DIR to the correct path relative to the project root, or an absolute path.\n")
        if not env_data_dir_path: # Extra hint if using default
             print_stderr(f"[twikit_service.py] The default path expects data in: <project_root>/python_bridge/twitter_data/\n")
        send_json_response({"id": None, "success": False, "error": f"Twitter data directory not found: {str(data_dir)}"})
        return

    username = os.getenv('TWIKIT_USERNAME')
    email = os.getenv('TWIKIT_EMAIL')
    password = os.getenv('TWIKIT_PASSWORD')
    cookies_file = os.getenv('TWIKIT_COOKIES_FILE')

    # Try to use Playwright-captured authentication data
    try:
        auth = TwitterAuthenticator(data_dir=str(data_dir)) # Pass string representation of Path
        common_headers = auth.get_common_headers()
        cookies_dict = auth.get_cookies_dict()
        home_html, ondemand_js = auth.get_public_transaction_generator_data()
        if not (common_headers and cookies_dict and home_html and ondemand_js):
            print_stderr("ERROR: Required authentication or transaction generator data is missing.\n")
            print_stderr("Please run playwright_login_and_export.py first and ensure you are logged in.\n")
            send_json_response({"id": None, "success": False, "error": "Missing authentication or transaction generator data"})
            return
        # Set up transaction generator
        home_soup = bs4.BeautifulSoup(home_html, 'html.parser')
        ondemand_soup = bs4.BeautifulSoup(ondemand_js, 'html.parser')
        transaction_generator = YourCustomClientTransaction(home_page_response=home_soup, ondemand_file_response=ondemand_soup)
        print_stderr("Loaded authentication and transaction generator data from Playwright export.\n")
    except Exception as e:
        print_stderr(f"Error loading Playwright authentication data: {str(e)}\n")
        send_json_response({"id": None, "success": False, "error": str(e)})
        return

    # --- Set up Twikit client with patched HTTP to inject headers and custom transaction IDs ---
    # Patch internal Twikit ClientTransaction methods to no-op
    original_twikit_ct_init = TwikitClientTransactionInternal.init
    TwikitClientTransactionInternal.init = no_op_twikit_ct_init
    original_twikit_ct_generate_id = TwikitClientTransactionInternal.generate_transaction_id
    TwikitClientTransactionInternal.generate_transaction_id = no_op_twikit_ct_generate_id

    # Initialize Twikit client and patch its HTTP request method
    client = Client('en-US')
    if hasattr(client, 'http') and hasattr(client.http, 'request'):
        original_http = client.http.request
        client.http.request = functools.partial(patched_http_client_request, original_http)
    else:
        print_stderr("Error: client.http.request not available for patching. Aborting.\n")
        return
    client.enable_ui_metrics = False

    # Populate static injected headers: cookies, CSRF token, and other common headers
    cookie_header = "; ".join([f"{name}={value}" for name, value in cookies_dict.items()])
    ct0_token = cookies_dict.get('ct0')
    HEADERS_TO_INJECT.update(common_headers)
    if ct0_token:
        HEADERS_TO_INJECT['x-csrf-token'] = ct0_token
    HEADERS_TO_INJECT['Cookie'] = cookie_header

    # Notify Node.js that Python service is ready
    ready_signal = {"status": "ready"}
    send_json_response(ready_signal)

    # Process commands from stdin
    loop = asyncio.get_event_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break # EOF
        request_id = None
        try:
            command_data = json.loads(line)
            request_id = command_data.get('id')
            action = command_data.get('action')
            args = command_data.get('args', {})
            if not action:
                raise ValueError("Missing 'action' in command")
            if action == 'get_transaction_id':
                # Expects 'url' and 'method' in args
                if 'url' not in args or 'method' not in args:
                    raise ValueError("Missing 'url' or 'method' for get_transaction_id action")
                method = args['method']
                url = args['url']
                try:
                    path = urlparse(url).path
                    transaction_id = transaction_generator.generate_transaction_id(method=method, path=path)
                    response_data = {"id": request_id, "success": True, "data": transaction_id}
                except Exception as e:
                    response_data = {"id": request_id, "success": False, "error": f"Failed to generate transaction ID: {str(e)}"}
            elif action == 'postTweet':
                text = args.get('text')
                if text is None:
                    raise ValueError("Missing 'text' for postTweet")
                # Generate transaction ID for CreateTweet GraphQL
                path = urlparse(Endpoint.CREATE_TWEET).path
                HEADERS_TO_INJECT['x-client-transaction-id'] = transaction_generator.generate_transaction_id(method="POST", path=path)
                tweet = await client.create_tweet(text=text)
                response_data = {"id": request_id, "success": True, "data": {"tweetId": tweet.id}}
            elif action == 'postTweetWithMedia':
                text = args.get('text')
                media_path = args.get('mediaPath')
                media_type = args.get('mediaType')
                alt_text = args.get('altText')
                if None in (text, media_path, media_type):
                    raise ValueError("Missing arguments for postTweetWithMedia")
                # Upload media (REST endpoint)
                media_id = await client.upload_media(media_path)
                if alt_text:
                    await client.create_media_metadata(media_id, alt_text=alt_text)
                # Create tweet with media
                path = urlparse(Endpoint.CREATE_TWEET).path
                HEADERS_TO_INJECT['x-client-transaction-id'] = transaction_generator.generate_transaction_id(method="POST", path=path)
                tweet = await client.create_tweet(text=text, media_ids=[media_id])
                response_data = {"id": request_id, "success": True, "data": {"tweetId": tweet.id}}
            elif action == 'likeTweet':
                tweet_id = args.get('tweetId')
                if tweet_id is None:
                    raise ValueError("Missing 'tweetId' for likeTweet")
                path = urlparse(Endpoint.FAVORITE_TWEET).path
                HEADERS_TO_INJECT['x-client-transaction-id'] = transaction_generator.generate_transaction_id(method="POST", path=path)
                await client.favorite_tweet(tweet_id)
                response_data = {"id": request_id, "success": True}
            elif action == 'unlikeTweet':
                tweet_id = args.get('tweetId')
                if tweet_id is None:
                    raise ValueError("Missing 'tweetId' for unlikeTweet")
                path = urlparse(Endpoint.UNFAVORITE_TWEET).path
                HEADERS_TO_INJECT['x-client-transaction-id'] = transaction_generator.generate_transaction_id(method="POST", path=path)
                await client.unfavorite_tweet(tweet_id)
                response_data = {"id": request_id, "success": True}
            elif action == 'getLikedTweets':
                user_id = args.get('userId')
                max_results = args.get('maxResults', 20)
                result = await client.get_user_tweets(user_id, 'Likes', max_results)
                response_data = {"id": request_id, "success": True, "data": [t.id for t in result]}
            elif action == 'searchTweets':
                query = args.get('query')
                max_results = args.get('maxResults', 20)
                tweets = await client.search_tweet(query, 'Top', max_results)
                response_data = {"id": request_id, "success": True, "data": [t.id for t in tweets]}
            elif action == 'replyToTweet':
                tweet_id = args.get('tweetId')
                text = args.get('text')
                if None in (tweet_id, text):
                    raise ValueError("Missing arguments for replyToTweet")
                path = urlparse(Endpoint.CREATE_TWEET).path
                HEADERS_TO_INJECT['x-client-transaction-id'] = transaction_generator.generate_transaction_id(method="POST", path=path)
                reply = await client.create_tweet(text=text, reply_to=tweet_id)
                response_data = {"id": request_id, "success": True, "data": {"tweetId": reply.id}}
            elif action == 'getUserTimeline':
                user_id = args.get('userId')
                max_results = args.get('maxResults', 20)
                timeline = await client.get_user_tweets(user_id, 'Tweets', max_results)
                response_data = {"id": request_id, "success": True, "data": [t.id for t in timeline]}
            elif action == 'getTweetById':
                tweet_id = args.get('tweetId')
                tweet = await client.get_tweet_by_id(tweet_id)
                response_data = {"id": request_id, "success": True, "data": {"tweetId": tweet.id, "text": tweet.text}}
            elif action == 'getUserInfo':
                username = args.get('username')
                user = await client.get_user_by_screen_name(username)
                response_data = {"id": request_id, "success": True, "data": {"userId": user.id, "username": user.screen_name}}
            elif action == 'getTweetsByIds':
                tweet_ids = args.get('tweetIds', [])
                tweets = await client.get_tweets_by_ids(tweet_ids)
                response_data = {"id": request_id, "success": True, "data": [t.id for t in tweets]}
            elif action == 'retweet':
                tweet_id = args.get('tweetId')
                path = urlparse(Endpoint.RETWEET).path
                HEADERS_TO_INJECT['x-client-transaction-id'] = transaction_generator.generate_transaction_id(method="POST", path=path)
                await client.retweet(tweet_id)
                response_data = {"id": request_id, "success": True}
            elif action == 'undoRetweet':
                tweet_id = args.get('tweetId')
                path = urlparse(Endpoint.DELETE_RETWEET).path
                HEADERS_TO_INJECT['x-client-transaction-id'] = transaction_generator.generate_transaction_id(method="POST", path=path)
                await client.delete_retweet(tweet_id)
                response_data = {"id": request_id, "success": True}
            elif action == 'getRetweets':
                tweet_id = args.get('tweetId')
                max_results = args.get('maxResults', 20)
                users = await client.get_retweeters(tweet_id, max_results)
                response_data = {"id": request_id, "success": True, "data": [u.id for u in users]}
            elif action == 'followUser':
                username = args.get('username')
                user = await client.get_user_by_screen_name(username)
                out = await client.follow_user(user.id)
                response_data = {"id": request_id, "success": True, "data": {"userId": out.id}}
            elif action == 'unfollowUser':
                username = args.get('username')
                user = await client.get_user_by_screen_name(username)
                out = await client.unfollow_user(user.id)
                response_data = {"id": request_id, "success": True, "data": {"userId": out.id}}
            elif action == 'deleteTweet':
                tweet_id = args.get('tweetId')
                await client.delete_tweet(tweet_id)
                response_data = {"id": request_id, "success": True}
            else:
                response_data = {"id": request_id, "success": False, "error": f"Unknown action '{action}'"}
        except json.JSONDecodeError as e:
            response_data = {"id": request_id, "success": False, "error": f"Invalid JSON command: {str(e)}"}
        except Exception as e:
            response_data = {"id": request_id, "success": False, "error": str(e)}
        send_json_response(response_data)

async def handle_command(client, command):
    try:
        # ... existing code ...
        
        # When returning a response
        response = {
            "id": command_id,
            "success": True,
            "data": result
        }
        send_json_response(response)
        
    except Exception as e:
        # ... error handling ...
        error_response = {
            "id": command_id,
            "success": False,
            "error": str(e)
        }
        send_json_response(error_response)

if __name__ == "__main__":
    asyncio.run(main())