import requests
import logging

# Configure logging to capture errors
logging.basicConfig(level=logging.ERROR)

# API URL
url = "https://cmhelpdesk.cmg.com.my/demo/chatbot_wsc/chatbot_message/update"

# Headers
headers = {
    "Phone-Number": "60162266223"
}

# Query parameters
params = {
    "messageId": "wamid.HBgLNjAxNjIyNjYyMjMVAgARGBJBRjVCM",
    "sender": "chai",
    "message_status": "delivered"
}

try:
    # Send the POST request
    response = requests.post(url, headers=headers, params=params)
    
    # Print response
    print("Status Code:", response.status_code)
    print("Response Body:", response.text)
except requests.exceptions.RequestException as e:
    logging.error("Error occurred: %s", e)


# import requests
# import logging

# # Configure logging
# logging.basicConfig(level=logging.ERROR)

# # API URL
# url = "https://cmhelpdesk.cmg.com.my/demo/chatbot_wsc/auth/check"

# # Headers
# headers = {
#     "Content-Type": "application/x-www-form-urlencoded"
# }

# # Data payload
# data = {
#     "phone_number": "60162266223"
# }

# try:
#     # Sending POST request
#     response = requests.post(url, headers=headers, data=data)
    
#     # Print response status and JSON
#     print("Status Code:", response.status_code)
#     print("Response:", response.json())

# except requests.exceptions.RequestException as e:
#     logging.error("API request failed: %s", str(e))
