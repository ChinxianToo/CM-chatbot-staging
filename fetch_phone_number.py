import requests
import json
import os
import logging
import sys
from requests.exceptions import RequestException, ConnectionError, Timeout, TooManyRedirects

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_phone_number(wproj_id):
    url = os.getenv('API_URL', 'https://cmhelpdesk.cmg.com.my/demo/chatbot_wsc/project/tel')
    header_phone = os.getenv('HEADER_PHONE', '0162550255')
    project_id = wproj_id
    
    headers = {
        "Phone-Number": header_phone
    }

    params = {
        "project_id": project_id
    }

    try:
        with requests.Session() as session:
            response = session.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") == "01" and data.get("data"):
                phone_number = data.get("data")
                logger.info(f"Successfully fetched phone number: {phone_number}")
                result = {"phone_number": phone_number, "wproj_id": wproj_id}
            else:
                error_msg = "Phone number not found or invalid response code"
                logger.error(error_msg)
                result = {"error": error_msg, "wproj_id": wproj_id}

    except ConnectionError as e:
        error_msg = f"Connection error: {str(e)}. Please check if the URL is correct and accessible."
        logger.error(error_msg)
        result = {"error": error_msg, "wproj_id": wproj_id}
    except Timeout:
        error_msg = "The request timed out. Please check your network connection or try again later."
        logger.error(error_msg)
        result = {"error": error_msg, "wproj_id": wproj_id}
    except TooManyRedirects:
        error_msg = "Too many redirects. Please check the URL and try again."
        logger.error(error_msg)
        result = {"error": error_msg, "wproj_id": wproj_id}
    except RequestException as e:
        error_msg = f"Error fetching phone number: {str(e)}"
        logger.error(error_msg)
        result = {"error": error_msg, "wproj_id": wproj_id}
    
    # Print the JSON result to stdout
    print(json.dumps(result))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(json.dumps({"error": "Missing wproj_id argument", "wproj_id": ""}))
        sys.exit(1)
    
    wproj_id = sys.argv[1]
    fetch_phone_number(wproj_id)