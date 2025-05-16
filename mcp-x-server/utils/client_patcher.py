import functools
import traceback
from typing import Callable, Dict, Any
from urllib.parse import urlparse
from x_client_transaction import ClientTransaction as XClientTransaction
from twikit.x_client_transaction import ClientTransaction as TwikitClientTransaction

# Global variable for headers injection
HEADERS_TO_INJECT = {}

class ClientPatcher:
    """
    Utility class for patching the twikit client to use our custom authentication
    """
    
    def __init__(self, client_transaction: XClientTransaction):
        """
        Initialize the client patcher
        
        Args:
            client_transaction: The XClientTransaction instance to use for transaction ID generation
        """
        self.client_transaction = client_transaction
        self.original_twikit_ct_init = None
        self.original_twikit_ct_generate_id = None
        self.original_http_request_method = None
    
    def patch_client(self, client):
        """
        Apply all necessary patches to the twikit client
        
        Args:
            client: The twikit client instance to patch
        """
        # Patch twikit's ClientTransaction class
        self.original_twikit_ct_init = TwikitClientTransaction.init
        TwikitClientTransaction.init = self.no_op_twikit_ct_init
        
        self.original_twikit_ct_generate_id = TwikitClientTransaction.generate_transaction_id
        TwikitClientTransaction.generate_transaction_id = self.no_op_twikit_ct_generate_id
        
        # Patch the HTTP client
        if hasattr(client, 'http') and hasattr(client.http, 'request'):
            self.original_http_request_method = client.http.request
            client.http.request = functools.partial(
                self.patched_http_client_request, 
                self.original_http_request_method
            )
            print("Patched client.http.request method")
        else:
            print("Error: client.http.request not available for patching")
            raise AttributeError("client.http.request not available for patching")
        
        # Disable UI metrics
        client.enable_ui_metrics = False
        print(f"Set client.enable_ui_metrics to {client.enable_ui_metrics}")
        
        return client
    
    def setup_headers(self, cookie_header: str, ct0_token: str):
        """
        Set up the global headers for injection
        
        Args:
            cookie_header: The Cookie header value
            ct0_token: The ct0 token (CSRF token)
        """
        global HEADERS_TO_INJECT
        
        # Generate initial transaction ID for the create tweet endpoint
        gql_create_tweet_path = "/i/api/graphql/SiM_cAu83R0wnrpmKQQSEw/CreateTweet"
        transaction_id = self.client_transaction.generate_transaction_id(
            method="POST", 
            path=gql_create_tweet_path
        )
        print(f"Generated initial transaction ID: {transaction_id}")
        
        # Set up initial headers
        HEADERS_TO_INJECT.update({
            "Cookie": cookie_header,
            "x-csrf-token": ct0_token,
            "x-client-transaction-id": transaction_id,
        })
    
    def update_headers(self, headers: Dict[str, str]):
        """
        Update the global headers with additional values
        
        Args:
            headers: Dictionary of headers to add/update
        """
        global HEADERS_TO_INJECT
        HEADERS_TO_INJECT.update(headers)
    
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
    
    async def patched_http_client_request(self, original_http_request_method, method, url, **kwargs):
        """
        Patch for the HTTP client to inject headers and handle transaction IDs
        
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
    
    def cleanup(self):
        """Clean up patches and resources"""
        try:
            if self.original_twikit_ct_init is not None:
                TwikitClientTransaction.init = self.original_twikit_ct_init
            if self.original_twikit_ct_generate_id is not None:
                TwikitClientTransaction.generate_transaction_id = self.original_twikit_ct_generate_id
            print("Cleaned up client patcher resources")
        except Exception as e:
            print(f"Error during cleanup: {e}")
