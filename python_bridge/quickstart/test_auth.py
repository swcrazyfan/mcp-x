try:
    import bs4
    import requests
    import json
    import os
    import re
    from pathlib import Path
    from x_client_transaction.utils import generate_headers, handle_x_migration, get_ondemand_file_url
    from x_client_transaction import ClientTransaction
    import urllib.parse

    print(f"Successfully imported required libraries")

    # Load our saved cookies and headers
    data_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent / "twitter_data"
    print(f"Data directory: {data_dir}")
    
    cookies_path = data_dir / "twitter_cookies.json"
    headers_path = data_dir / "twitter_common_headers.json"
    
    if cookies_path.exists() and headers_path.exists():
        print("Loading saved cookies and headers...")
        with open(cookies_path, "r") as f:
            cookies = json.load(f)
        with open(headers_path, "r") as f:
            common_headers = json.load(f)
        print(f"Loaded {len(cookies)} cookies and {len(common_headers)} headers")
    else:
        print("Cookies or headers file not found!")
        raise FileNotFoundError("Cookie or header files missing")

    # INITIALIZE SESSION
    session = requests.Session()
    session.headers.update(common_headers)
    
    # Add cookies to session
    cookies_dict = {}
    for cookie in cookies:
        if 'name' in cookie and 'value' in cookie:
            cookies_dict[cookie['name']] = cookie['value']
            session.cookies.set(cookie['name'], cookie['value'], domain='.twitter.com')
            session.cookies.set(cookie['name'], cookie['value'], domain='.x.com')
    
    print(f"Session prepared with headers and cookies")

    # GET HOME PAGE RESPONSE
    print("Getting home page response...")
    try:
        home_page_response = handle_x_migration(session=session)
        print(f"Got home page response: {type(home_page_response)}")
    except Exception as e:
        print(f"Error getting home page: {str(e)}")
        raise

    # GET ondemand.s FILE RESPONSE - Use hardcoded URL from our previous tests
    ondemand_file_url = "https://abs.twimg.com/responsive-web/client-web/ondemand.s.63fc9f1a.js"
    print(f"Using hardcoded ondemand.s file URL: {ondemand_file_url}")
    try:
        ondemand_file = session.get(url=ondemand_file_url)
        if ondemand_file.status_code == 200:
            print(f"Successfully downloaded ondemand.js file: {len(ondemand_file.text)} bytes")
            ondemand_file_response = bs4.BeautifulSoup(ondemand_file.content, 'html.parser')
            print(f"Got ondemand file response: {type(ondemand_file_response)}")
        else:
            print(f"Failed to download ondemand.js file: {ondemand_file.status_code}")
            raise Exception(f"Failed to download ondemand.js file: {ondemand_file.status_code}")
    except Exception as e:
        print(f"Error getting ondemand file: {str(e)}")
        raise

    # Initialize transaction generator
    print("Initializing transaction generator...")
    try:
        ct = ClientTransaction(home_page_response=home_page_response, ondemand_file_response=ondemand_file_response)
        print("Successfully initialized transaction generator")
    except Exception as e:
        print(f"Error initializing transaction generator: {str(e)}")
        raise

    # Generate a transaction ID and test API call
    url = "https://x.com/i/api/2/badge_count/badge_count.json?supports_ntab_urt=1"
    method = "GET"
    path = urllib.parse.urlparse(url=url).path
    try:
        transaction_id = ct.generate_transaction_id(method=method, path=path)
        print(f"Generated transaction ID: {transaction_id}")
        
        # Add the transaction ID to the headers
        headers = session.headers.copy()
        headers["x-client-transaction-id"] = transaction_id
        
        # Make the API call
        response = session.get(url, headers=headers)
        print(f"API call status: {response.status_code}")
        if response.status_code == 200:
            print(f"API call successful! Response: {response.text[:100]}...")
        else:
            print(f"API call failed! Response: {response.text}")
    except Exception as e:
        print(f"Error during API test: {str(e)}")
        raise

except Exception as e:
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()
