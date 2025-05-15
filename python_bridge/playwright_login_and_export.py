import asyncio
import json
import os
import bs4
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse
from collections import Counter
from playwright.async_api import async_playwright, Page, Browser, BrowserContext, Request
import requests
from x_client_transaction import ClientTransaction
from x_client_transaction.utils import get_ondemand_file_url
import sys

class TwitterAuthenticator:
    def __init__(self, 
                 data_dir: str = None, 
                 headless: bool = False, 
                 cookies_filename: str = "twitter_cookies.json",
                 headers_filename: str = "twitter_headers.json",
                 common_headers_filename: str = "twitter_common_headers.json",
                 home_filename: str = "twitter_home.html",
                 ondemand_filename: str = "twitter_ondemand.js"):
        """
        Initialize the Twitter authenticator
        
        Args:
            data_dir: Directory to save files to, defaults to script directory
            headless: Whether to run the browser in headless mode
        """
        self.data_dir = Path(data_dir) if data_dir else Path(os.path.dirname(os.path.abspath(__file__)))
        self.headless = headless
        
        # File paths
        self.cookies_path = self.data_dir / cookies_filename
        self.headers_path = self.data_dir / headers_filename
        self.common_headers_path = self.data_dir / common_headers_filename
        self.home_path = self.data_dir / home_filename
        self.ondemand_path = self.data_dir / ondemand_filename
        
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Data storage
        self.cookies = None
        self.headers = []
        self.common_headers = {}
        self.home_html = None
        self.ondemand_js = None
        self.ondemand_url = None
        self.auth_token = None
        self.csrf_token = None
        
    async def login(self, force_login: bool = False) -> bool:
        """
        Launch browser and handle Twitter login
        
        Args:
            force_login: If True, will prompt for login even if cookies exist
            
        Returns:
            bool: Whether login was successful
        """
        sys.stderr.write(f"Current working directory: {os.getcwd()}\n")
        sys.stderr.write("Checking for files:\n")
        sys.stderr.write(f"Cookies: {self.cookies_path} {self.cookies_path.exists()}\n")
        sys.stderr.write(f"Common headers: {self.common_headers_path} {self.common_headers_path.exists()}\n")
        sys.stderr.write(f"Home HTML: {self.home_path} {self.home_path.exists()}\n")
        sys.stderr.write(f"Ondemand JS: {self.ondemand_path} {self.ondemand_path.exists()}\n")
        
        if not force_login:
            # Check if all required files exist
            if (self.cookies_path.exists() and 
                self.common_headers_path.exists() and 
                self.home_path.exists() and 
                self.ondemand_path.exists()):
                
                # Load existing data
                self._load_saved_data()
                sys.stderr.write(f"Loaded existing authentication data from {self.data_dir}\n")
                # Test if authentication is still valid
                test_session = requests.Session()
                test_session.headers.update(self.common_headers)
                for name, value in self.get_cookies_dict().items():
                    test_session.cookies.set(name, value, domain='.twitter.com')
                test_url = "https://x.com/i/api/2/badge_count/badge_count.json?supports_ntab_urt=1"
                try:
                    transaction_id = None
                    try:
                        home_html, ondemand_js = self.get_transaction_generator_data()
                        if home_html and ondemand_js:
                            home_soup = bs4.BeautifulSoup(home_html, 'html.parser')
                            ondemand_soup = bs4.BeautifulSoup(ondemand_js, 'html.parser')
                            ct = ClientTransaction(home_page_response=home_soup, ondemand_file_response=ondemand_soup)
                            test_path = urlparse(test_url).path
                            transaction_id = ct.generate_transaction_id(method="GET", path=test_path)
                            sys.stderr.write(f"Generated transaction ID: {transaction_id}\n")
                    except Exception as e:
                        sys.stderr.write(f"Could not generate transaction ID for debug: {str(e)}\n")
                    if transaction_id:
                        test_session.headers["x-client-transaction-id"] = transaction_id
                    sys.stderr.write(f"Request headers: {dict(test_session.headers)}\n")
                    sys.stderr.write(f"Request cookies: {test_session.cookies.get_dict()}\n")
                    response = test_session.get(test_url)
                    if response.status_code == 200:
                        sys.stderr.write("Authentication test SUCCESSFUL! You are still logged in.\n")
                        sys.stderr.write(f"JSON response preview: {response.text[:100]}...\n")
                        # After checking/using saved data, always fetch public home/ondemand (outside Playwright)
                        self.fetch_public_home_and_ondemand()
                        return True
                    else:
                        sys.stderr.write(f"Authentication test FAILED. Status code: {response.status_code}\n")
                        sys.stderr.write(f"Response: {response.text}\n")
                        sys.stderr.write("Your cookies/headers are no longer valid. Please re-run with force_login=True or delete the data files to log in again.\n")
                        return False
                except Exception as e:
                    sys.stderr.write(f"Error during authentication test: {str(e)}\n")
                    sys.stderr.write("Please re-run with force_login=True or delete the data files to log in again.\n")
                    return False
            
        # Start browser for manual login
        sys.stderr.write("Starting browser for Twitter login...\n")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context()
            page = await context.new_page()

            # Monitor all requests (for headers/cookies only)
            captured_headers = []
            seen_headers = set()
            async def on_request(request):
                parsed = urlparse(request.url)
                if parsed.hostname and ("x.com" in parsed.hostname or "twitter.com" in parsed.hostname):
                    header_tuple = tuple(sorted(request.headers.items()))
                    if header_tuple not in seen_headers:
                        seen_headers.add(header_tuple)
                        captured_headers.append({"url": request.url, "headers": dict(request.headers)})
                        sys.stderr.write(f"Captured headers for: {request.url}\n")
            
            page.on("request", on_request)
            
            # Go to login page (for login only)
            await page.goto("https://x.com/login")
            sys.stderr.write("\nPlease log in manually in the browser window (including 2FA if needed).\n")
            input("Press Enter here after you have completed login and see your home feed...")
            
            sys.stderr.write("\nNow browse and interact with Twitter to generate various requests.\n")
            sys.stderr.write("Try different actions like refreshing pages, viewing profiles, etc.\n")
            input("Press Enter when you're done...\n")
            
            # Save cookies and headers only
            self.cookies = await context.cookies()
            self.headers = captured_headers
            
            sys.stderr.write("Processing captured data...\n")
            
            self._extract_tokens_from_cookies()
            self._process_common_headers()
            
            with open(self.headers_path, "w") as f:
                json.dump(self.headers, f, indent=2)
            sys.stderr.write(f"Saved {len(self.headers)} unique header sets to {self.headers_path}\n")
            
            with open(self.cookies_path, "w") as f:
                json.dump(self.cookies, f, indent=2)
            sys.stderr.write(f"Cookies saved to {self.cookies_path}\n")
            
            await browser.close()
            
        # After Playwright login, always fetch public home/ondemand (outside Playwright)
        self.fetch_public_home_and_ondemand()
        
        return True
        
    def _process_common_headers(self) -> None:
        """Process captured headers to find the ones consistently used"""
        if not self.headers:
            sys.stderr.write("No headers to process\n")
            return
            
        # Count frequency of each header and its values
        header_counts = Counter()
        header_values = {}
        
        for entry in self.headers:
            req_headers = entry.get("headers", {})
            for header, value in req_headers.items():
                # Skip transaction ID as we'll generate it dynamically
                if header.lower() == 'x-client-transaction-id':
                    continue
                
                # Count this header
                header_counts[header] += 1
                
                # Track values for this header
                if header not in header_values:
                    header_values[header] = Counter()
                header_values[header][value] += 1
        
        # Find headers used in at least 75% of requests
        common_headers = {}
        min_frequency = int(len(self.headers) * 0.75) if self.headers else 1
        
        for header, count in header_counts.items():
            if count >= min_frequency:
                # Get the most common value for this header
                most_common = header_values[header].most_common(1)
                if most_common:
                    common_headers[header] = most_common[0][0]
        
        # Add auth and csrf tokens if available
        if self.auth_token and 'authorization' not in common_headers:
            common_headers['authorization'] = f"Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
        
        if self.csrf_token and 'x-csrf-token' not in common_headers:
            common_headers['x-csrf-token'] = self.csrf_token
        
        # Save common headers
        self.common_headers = common_headers
        with open(self.common_headers_path, "w") as f:
            json.dump(common_headers, f, indent=2)
        
        sys.stderr.write(f"Processed and saved {len(common_headers)} common headers to {self.common_headers_path}\n")
        
    def _extract_tokens_from_cookies(self) -> None:
        """Extract auth token and CSRF token from cookies"""
        if not self.cookies:
            return
            
        for cookie in self.cookies:
            if cookie['name'] == 'auth_token':
                self.auth_token = cookie['value']
            elif cookie['name'] == 'ct0':
                self.csrf_token = cookie['value']
                
    def _load_saved_data(self) -> None:
        """Load data from saved files"""
        # Load cookies if not already loaded
        if not self.cookies and self.cookies_path.exists():
            with open(self.cookies_path, "r") as f:
                self.cookies = json.load(f)
                
        # Load common headers
        if self.common_headers_path.exists():
            with open(self.common_headers_path, "r") as f:
                self.common_headers = json.load(f)
                
        # Load home page
        if self.home_path.exists():
            with open(self.home_path, "r", encoding="utf-8") as f:
                self.home_html = f.read()
                
        # Load ondemand file
        if self.ondemand_path.exists():
            with open(self.ondemand_path, "r", encoding="utf-8") as f:
                self.ondemand_js = f.read()
                
        # Extract tokens from cookies
        self._extract_tokens_from_cookies()
        
    def get_auth_data(self) -> Dict[str, str]:
        """Get the authentication data needed for API requests"""
        if not self.auth_token or not self.csrf_token:
            self._extract_tokens_from_cookies()
            
        return {
            'auth_token': self.auth_token,
            'csrf_token': self.csrf_token
        }
        
    def get_transaction_generator_data(self) -> Tuple[str, str]:
        """Get the data needed to initialize the transaction ID generator"""
        if not self.home_html or not self.ondemand_js:
            self._load_saved_data()
            
        return self.home_html, self.ondemand_js
        
    def get_common_headers(self) -> Dict[str, str]:
        """Get common headers used in Twitter API requests"""
        if not self.common_headers:
            self._load_saved_data()
            
        return self.common_headers
    
    def get_cookies_dict(self) -> Dict[str, str]:
        """Convert cookies to a dictionary format for requests"""
        if not self.cookies:
            self._load_saved_data()
            
        cookies_dict = {}
        for cookie in self.cookies:
            if 'name' in cookie and 'value' in cookie:
                cookies_dict[cookie['name']] = cookie['value']
                
        return cookies_dict

    def fetch_public_home_and_ondemand(self):
        """Fetch the public (non-authenticated) X.com homepage and ondemand.s JS file, unless they already exist and are non-empty."""
        public_home_path = self.data_dir / "twitter_home.html"
        public_ondemand_path = self.data_dir / "twitter_ondemand.js"
        need_fetch_home = not public_home_path.exists() or public_home_path.stat().st_size == 0
        need_fetch_ondemand = not public_ondemand_path.exists() or public_ondemand_path.stat().st_size == 0
        if not need_fetch_home:
            sys.stderr.write(f"Reusing existing public homepage HTML: {public_home_path}\n")
        if not need_fetch_ondemand:
            sys.stderr.write(f"Reusing existing public ondemand.s JS: {public_ondemand_path}\n")
        if not need_fetch_home and not need_fetch_ondemand:
            return
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
        })
        if need_fetch_home:
            home_page = session.get("https://x.com")
            with open(public_home_path, "w", encoding="utf-8") as f:
                f.write(home_page.text)
            sys.stderr.write(f"Public homepage HTML saved to {public_home_path}\n")
        else:
            with open(public_home_path, "r", encoding="utf-8") as f:
                home_page_text = f.read()
        # Always parse the home HTML to get the ondemand.s URL
        if need_fetch_home:
            home_html = home_page.text
        else:
            home_html = home_page_text
        home_soup = bs4.BeautifulSoup(home_html, 'html.parser')
        ondemand_file_url = get_ondemand_file_url(response=home_soup)
        if not ondemand_file_url:
            sys.stderr.write("ERROR: Could not extract ondemand.s JS URL from public homepage!\n")
            return
        if need_fetch_ondemand:
            ondemand_file = session.get(ondemand_file_url)
            with open(public_ondemand_path, "w", encoding="utf-8") as f:
                f.write(ondemand_file.text)
            sys.stderr.write(f"Public ondemand.s JS saved to {public_ondemand_path}\n")

    def get_best_ondemand_js(self):
        """Try to use the public ondemand.s JS if available, else fall back to Playwright-captured one."""
        public_ondemand_path = self.data_dir / "twitter_ondemand.js"
        fallback_ondemand_path = self.data_dir / "twitter_ondemand.js"
        if public_ondemand_path.exists():
            sys.stderr.write(f"Using public ondemand.s JS: {public_ondemand_path}\n")
            with open(public_ondemand_path, "r", encoding="utf-8") as f:
                return f.read()
        elif fallback_ondemand_path.exists():
            sys.stderr.write(f"Warning: Public ondemand.s JS not found. Using Playwright-captured ondemand.s: {fallback_ondemand_path}\n")
            with open(fallback_ondemand_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            raise FileNotFoundError("No ondemand.s JS file found (neither public nor Playwright-captured)")

    def get_public_transaction_generator_data(self):
        """Load the public homepage and best available ondemand.s JS for transaction ID generation."""
        public_home_path = self.data_dir / "twitter_home.html"
        sys.stderr.write(f"Looking for public home HTML at: {public_home_path}\n")
        if not public_home_path.exists():
            sys.stderr.write(f"ERROR: {public_home_path} does not exist!\n")
            return None, None
        with open(public_home_path, "r", encoding="utf-8") as f:
            home_html = f.read()
        if not home_html.strip():
            sys.stderr.write(f"ERROR: {public_home_path} is empty!\n")
            return None, None
        ondemand_js = self.get_best_ondemand_js()
        return home_html, ondemand_js

    async def debug_api_call(self, url: str, method: str = "GET", data: dict = None):
        """Make a real API call with full debug logging, using captured credentials and transaction ID."""
        # Prepare session
        session = requests.Session()
        # Add cookies
        cookies_dict = self.get_cookies_dict()
        for name, value in cookies_dict.items():
            session.cookies.set(name, value, domain='.twitter.com')
        # Prepare headers
        headers = self.get_common_headers().copy()
        # Add required headers
        # if self.auth_token:
        #     headers['authorization'] = f"Bearer {self.auth_token}"
        if self.csrf_token:
            headers['x-csrf-token'] = self.csrf_token
        headers['cookie'] = "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])
        # Use public home/ondemand for transaction ID generation
        home_html, ondemand_js = self.get_public_transaction_generator_data()
        if home_html and ondemand_js:
            home_soup = bs4.BeautifulSoup(home_html, 'html.parser')
            ondemand_soup = bs4.BeautifulSoup(ondemand_js, 'html.parser')
            ct = ClientTransaction(home_page_response=home_soup, ondemand_file_response=ondemand_soup)
            path = urlparse(url).path
            transaction_id = ct.generate_transaction_id(method=method, path=path)
            headers['x-client-transaction-id'] = transaction_id
            sys.stderr.write(f"Generated transaction ID: {transaction_id}\n")
        # Print all request headers and cookies
        sys.stderr.write("\n--- API REQUEST ---\n")
        sys.stderr.write(f"{method} {url}\n")
        sys.stderr.write(f"Headers: {headers}\n")
        sys.stderr.write(f"Cookies: {session.cookies.get_dict()}\n")
        # Make the request
        try:
            if method.upper() == "GET":
                response = session.get(url, headers=headers)
            else:
                response = session.request(method, url, headers=headers, data=data)
            sys.stderr.write("\n--- API RESPONSE ---\n")
            sys.stderr.write(f"Status: {response.status_code}\n")
            sys.stderr.write(f"Response Headers: {dict(response.headers)}\n")
            sys.stderr.write(f"Response Body (first 1000 chars):\n {response.text[:1000]}\n")
        except Exception as e:
            sys.stderr.write(f"API call error: {e}\n")

# Example of how to use this class from another script:
async def example_usage(force_login=False):
    auth = TwitterAuthenticator(data_dir="./twitter_data")
    success = await auth.login(force_login=force_login)
    
    if success:
        # Get data for requests
        common_headers = auth.get_common_headers()
        cookies_dict = auth.get_cookies_dict()
        home_html, ondemand_js = auth.get_transaction_generator_data()
        
        sys.stderr.write(f"Got {len(common_headers)} common headers\n")
        sys.stderr.write(f"Got {len(cookies_dict)} cookies\n")
        sys.stderr.write(f"Home HTML size: {len(home_html)} bytes\n")
        sys.stderr.write(f"Ondemand.js size: {len(ondemand_js) if ondemand_js else 0} bytes\n")
        # Demonstrate a real API call with full debug logging
        test_url = "https://x.com/i/api/2/badge_count/badge_count.json?supports_ntab_urt=1"
        await auth.debug_api_call(test_url, method="GET")

if __name__ == "__main__":
    import sys
    force_login = False
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("force_login", "force_login_true", "force", "true", "1"):
        force_login = True
    asyncio.run(example_usage(force_login=force_login))