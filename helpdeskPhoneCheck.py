import httpx

BASE_API_URL = "https://cmhelpdesk.cmg.com.my/demo/chatbot_wsc/ticket"
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def process_phone_number(phone_number, base_api_url):
    # Remove hyphens and spaces
    phone_no_1 = phone_number.replace("-", "").replace(" ", "")

    # Create phone_no_2 by removing the first digit
    phone_no_2 = phone_no_1[1:]

    headers_1 = {"Phone-Number": phone_no_1}
    params_1 = {"phone": phone_no_1}
    headers_2 = {"Phone-Number": phone_no_2}
    params_2 = {"phone": phone_no_2}

    # Send the GET request with headers and params
    response_1 = httpx.get(base_api_url, headers=headers_1, params=params_1)

    if response_1.status_code == 200 and response_1.json().get("code")=="01":
        print(response_1.json().get("code"))
        logger.info(phone_no_1 + " is valid")
        return phone_no_1
    elif response_1.status_code != 200:
        print("API failed")
    else:
        logger.info(phone_no_1  + " is invalid")

    # If first request fails or returns no data, try with phone_no_2
    response_2 = httpx.get(base_api_url, headers=headers_2, params=params_2)

    if response_2.status_code == 200 and response_2.json().get("code")=="01":
        print(response_2.json().get("code"))
        logger.info(phone_no_2 + " is valid")
        return phone_no_2
    elif response_2.status_code != 200:
        print("API failed")
        return phone_number
    else:
        logger.info(phone_no_2 + " is invalid")
        return phone_number


# process_phone_number("60162266223", BASE_API_URL)
