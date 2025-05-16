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
        # Use environment variable for data directory if set
        env_data_dir = os.environ.get("TWITTER_DATA_DIR")
        if env_data_dir:
            self.data_dir = Path(env_data_dir)
        elif data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "twitter_data"
            
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
                for name, value in self.get