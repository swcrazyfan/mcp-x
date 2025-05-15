import asyncio
from twikit import Client
# Import twikit's own ClientTransaction to patch its prototype
from twikit.x_client_transaction import ClientTransaction as TwikitClientTransactionInternal
from playwright_login_and_export import TwitterAuthenticator
from x_client_transaction import ClientTransaction as YourCustomClientTransaction # Your custom one
import bs4
from urllib.parse import urlparse
import functools

HEADERS_TO_INJECT_FOR_PATCH = {}

async def patched_http_client_request(original_http_request_method, method, url, **kwargs):
    # (Patch function remains the same as before)
    global HEADERS_TO_INJECT_FOR_PATCH
    print(f"--- Patched http.request called for: {method} {url} ---")
    headers_from_caller = kwargs.pop('headers', {})
    final_headers = HEADERS_TO_INJECT_FOR_PATCH.copy()
    for key, value in headers_from_caller.items():
        if key.lower() == 'content-type':
            final_headers[key] = value
        elif key not in final_headers:
            final_headers[key] = value
    print(f"Original headers passed to http.request: {headers_from_caller}")
    print(f"Headers to Inject (from global): {HEADERS_TO_INJECT_FOR_PATCH}")
    print(f"Final headers for HTTP actual call: {final_headers}")
    kwargs['headers'] = final_headers
    return await original_http_request_method(method, url, **kwargs)

# --- Dummy/No-op functions for patching twikit's internal ClientTransaction ---
async def no_op_twikit_ct_init(self_ct, http_client, headers_arg):
    print("--- Skipped twikit's internal ClientTransaction.init() due to patch ---")
    # We need to ensure critical attributes that might be checked exist, even if empty.
    if not hasattr(self_ct, 'home_page_response'):
        self_ct.home_page_response = True # Or some dummy truthy value
    if not hasattr(self_ct, 'DEFAULT_KEY_BYTES_INDICES'):
        self_ct.DEFAULT_KEY_BYTES_INDICES = []
    if not hasattr(self_ct, 'DEFAULT_ROW_INDEX'):
        self_ct.DEFAULT_ROW_INDEX = 0
    return

def no_op_twikit_ct_generate_id(self_ct, method, path, response=None, key=None, animation_key=None, time_now=None):
    print("--- Skipped twikit's internal ClientTransaction.generate_transaction_id() due to patch ---")
    return "dummy_transaction_id_from_twikit_patch" # Return a dummy value

async def main():
    global HEADERS_TO_INJECT_FOR_PATCH

    # --- Patch twikit's ClientTransaction class *before* Client is initialized ---
    # This affects any ClientTransaction instance twikit might create.
    original_twikit_ct_init = TwikitClientTransactionInternal.init
    TwikitClientTransactionInternal.init = no_op_twikit_ct_init
    
    original_twikit_ct_generate_id = TwikitClientTransactionInternal.generate_transaction_id
    TwikitClientTransactionInternal.generate_transaction_id = no_op_twikit_ct_generate_id
    print("Applied no-op patches to twikit.x_client_transaction.ClientTransaction prototype.")

    print("Loading Playwright data...")
    auth = TwitterAuthenticator(data_dir="./twitter_data")
    common_headers_from_playwright = auth.get_common_headers()
    cookies_dict_from_playwright = auth.get_cookies_dict()
    home_html_str, ondemand_js_str = auth.get_public_transaction_generator_data()
    print("Playwright data loaded.")

    client = Client('en-US')
    print(f"Initialized twikit.Client. Type of client.http: {type(client.http)}")

    if hasattr(client, 'http') and hasattr(client.http, 'request'):
        original_http_request_method_bound = client.http.request
        client.http.request = functools.partial(patched_http_client_request, original_http_request_method_bound)
        print("Successfully monkey-patched client.http.request method.")
    else:
        print("Error: client.http.request not available for patching. Aborting.")
        # Restore original CT methods if main fails early
        TwikitClientTransactionInternal.init = original_twikit_ct_init
        TwikitClientTransactionInternal.generate_transaction_id = original_twikit_ct_generate_id
        return
            
    client.enable_ui_metrics = False
    # client.client_transaction = None # This might not be strictly necessary if the prototype patch works
    print(f"client.enable_ui_metrics set to: {client.enable_ui_metrics}")

    print("Parsing HTML/JS for your custom transaction ID generation...")
    home_soup = bs4.BeautifulSoup(home_html_str, 'lxml')
    ondemand_soup_or_str = bs4.BeautifulSoup(ondemand_js_str, 'lxml') 
    
    gql_create_tweet_path = "/i/api/graphql/SiM_cAu83R0wnrpmKQQSEw/CreateTweet"
    
    print("Initializing your custom ClientTransaction (YourCustomClientTransaction)...")
    your_ct_instance = YourCustomClientTransaction(home_page_response=home_soup, ondemand_file_response=ondemand_soup_or_str)
    print("Generating x-client-transaction-id using your_ct_instance...")
    manual_transaction_id = your_ct_instance.generate_transaction_id(method="POST", path=gql_create_tweet_path)
    print(f"Manually generated x-client-transaction-id: {manual_transaction_id}")

    cookie_header_value = "; ".join([f"{name}={value}" for name, value in cookies_dict_from_playwright.items()])
    ct0_token = cookies_dict_from_playwright.get('ct0')
    if not ct0_token:
        print("Error: 'ct0' cookie not found!")
        TwikitClientTransactionInternal.init = original_twikit_ct_init
        TwikitClientTransactionInternal.generate_transaction_id = original_twikit_ct_generate_id
        return

    HEADERS_TO_INJECT_FOR_PATCH = {
        "Cookie": cookie_header_value,
        "x-csrf-token": ct0_token,
        "x-client-transaction-id": manual_transaction_id, 
    }
    HEADERS_TO_INJECT_FOR_PATCH.update(common_headers_from_playwright) 
    
    print(f"Populated HEADERS_TO_INJECT_FOR_PATCH for the upcoming request: {HEADERS_TO_INJECT_FOR_PATCH}")

    try:
        tweet_text = "One more tweet!"
        print(f"\nAttempting to post tweet: '{tweet_text}' using client.create_tweet()...")
        
        posted_tweet = await client.create_tweet(text=tweet_text)
        
        print(f"\nTweet posted successfully using client.create_tweet!")
        print(f"Tweet ID: {posted_tweet.id}")
        # ... (rest of print statements)

    except Exception as e:
        print(f"\nError posting tweet with client.create_tweet: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Restore original ClientTransaction methods
        TwikitClientTransactionInternal.init = original_twikit_ct_init
        TwikitClientTransactionInternal.generate_transaction_id = original_twikit_ct_generate_id
        print("Restored original twikit.x_client_transaction.ClientTransaction methods.")


if __name__ == "__main__":
    asyncio.run(main())