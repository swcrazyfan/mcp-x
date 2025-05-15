try:
    import bs4
    import requests
    from x_client_transaction.utils import generate_headers, handle_x_migration, get_ondemand_file_url
    from x_client_transaction import ClientTransaction
    import urllib.parse

    print(f"Successfully imported required libraries")

    # INITIALIZE SESSION
    session = requests.Session()
    session.headers = generate_headers()
    print(f"Generated headers: {session.headers}")

    # GET HOME PAGE RESPONSE
    # required only when hitting twitter.com but not x.com
    # returns bs4.BeautifulSoup object
    print("Getting home page response...")
    try:
        home_page_response = handle_x_migration(session=session)
        print(f"Got home page response: {type(home_page_response)}")
    except Exception as e:
        print(f"Error getting home page: {str(e)}")
        raise

    # GET ondemand.s FILE RESPONSE
    print("Getting ondemand.s file URL...")
    try:
        ondemand_file_url = get_ondemand_file_url(response=home_page_response)
        print(f"Got ondemand.s file URL: {ondemand_file_url}")
        ondemand_file = session.get(url=ondemand_file_url)
        ondemand_file_response = bs4.BeautifulSoup(ondemand_file.content, 'html.parser')
        print(f"Got ondemand file response: {type(ondemand_file_response)}")
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

    # Generate a transaction ID
    url = "https://x.com/i/api/1.1/jot/client_event.json"
    method = "POST"
    path = urllib.parse.urlparse(url=url).path
    try:
        transaction_id = ct.generate_transaction_id(method=method, path=path)
        print(f"Generated transaction ID: {transaction_id}")
    except Exception as e:
        print(f"Error generating transaction ID: {str(e)}")
        raise

except Exception as e:
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()
