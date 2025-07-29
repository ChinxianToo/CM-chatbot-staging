from quart import Quart, jsonify, request
from bullmq import Queue
import os
import httpx
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import traceback

app = Quart(__name__)

# Environment variables
PORT = os.environ.get("PORT", 8169)
WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN")
GRAPH_API_TOKEN = os.environ.get("GRAPH_API_TOKEN")
BUSSINESS_ID = os.environ.get("BUSSINESS_ID")
DEMO_API_URL = "https://cmhelpdesk.cmg.com.my/demo/chatbot_wsc/auth/check"
UPDATE_API_URL = "https://cmhelpdesk.cmg.com.my/demo/chatbot_wsc/chatbot_message/update"

helpdeskQueue = Queue(
    "helpdeskQueue", {"connection": {"host": "10.8.8.95", "port": 6380}}
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MessageType(Enum):
    INTERACTIVE = "interactive"
    TEXT = "text"
    BUTTON = "button"

async def process_api_response(response: httpx.Response, action: str = "API call"):
    """Process API response and log relevant information"""
    logger.info(f"{action} status code: {response.status_code}")
    
    if response.status_code == 200:
        try:
            data = response.json()
            if "code" in data:
                logger.info(f"{action} response code: {data['code']}")
                if data.get("code") == "X1" and "data" in data:
                    logger.warning(f"{action} error: {data['data'].get('Error')}")
            return data
        except ValueError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return None
    return None

@app.route("/webhook", methods=["POST"])
async def webhookPost():
    body = await request.get_json()
    logger.info(f"Webhook POST body: {body}")

    try:
        entry = body["entry"][0]["changes"][0]["value"]
        
        # Extract business phone ID from the message
        business_phone_id = entry.get("metadata", {}).get("phone_number_id")
        
        # Check if business ID matches
        if business_phone_id != "385912324613598":
            logger.warning(f"Business ID mismatch. Expected: 385912324613598, Received: {business_phone_id}")
            return jsonify({"message": "Invalid business ID"}), 403
        

        if "messages" in entry:
            message = entry["messages"][0]
            user_phone_number = message["from"]
            message_id = message["id"]
            message_type = message["type"]
            
            # Determine sender based on message type
            sender = "System"
            if message_type == MessageType.BUTTON.value:
                sender = entry.get("contacts", [{}])[0].get("profile", {}).get("name", "System")

            logger.info(f"Received message from: {user_phone_number}")

            if message_type in [m.value for m in MessageType]:
                await helpdeskQueue.add("myHelpdeskJob", body)

            # Update message status
            async with httpx.AsyncClient() as client:
                update_headers = {"Phone-Number": user_phone_number}
                update_params = {
                    "messageId": message_id,
                    "sender": sender,
                    "message_status": "received"
                }
                
                res = await client.post(
                    UPDATE_API_URL,
                    headers=update_headers,
                    params=update_params
                )
                await process_api_response(res, "Update API")

        elif "statuses" in entry:
            status = entry["statuses"][0]
            user_phone_number = status["recipient_id"]
            message_id = status["id"]
            message_status = status["status"]
            
            # Update message status
            async with httpx.AsyncClient() as client:
                update_headers = {"Phone-Number": user_phone_number}
                update_params = {
                    "messageId": message_id,
                    "sender": "System",
                    "message_status": message_status
                }
                
                res = await client.post(
                    UPDATE_API_URL,
                    headers=update_headers,
                    params=update_params
                )
                await process_api_response(res, "Status Update API")

        # Call demo API
        # async with httpx.AsyncClient() as client:
        #     res = await client.post(
        #         DEMO_API_URL,
        #         json={"phone_number": user_phone_number}
        #     )
        #     await process_api_response(res, "Demo API")

    except KeyError as e:
        logger.error(f"KeyError: {e}. Unexpected message structure.")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}\n{traceback.format_exc()}")

    return jsonify({"message": "Webhook received successfully"})

@app.route("/webhook", methods=["GET"])
async def webhookGet():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        return challenge
    return "", 403

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=PORT)




# from quart import Quart, jsonify, request
# from bullmq import Queue
# import os
# import httpx
# import logging
# from typing import Optional, Dict, Any
# from dataclasses import dataclass
# from enum import Enum
# import traceback

# app = Quart(__name__)

# # Environment variables
# PORT = os.environ.get("PORT", 8169)
# WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN")
# GRAPH_API_TOKEN = os.environ.get("GRAPH_API_TOKEN")
# BUSSINESS_ID = os.environ.get("BUSSINESS_ID")
# DEMO_API_URL = "https://cmhelpdesk.cmg.com.my/demo/chatbot_wsc/auth/check"
# UPDATE_API_URL = "https://cmhelpdesk.cmg.com.my/demo/chatbot_wsc/chatbot_message/update"

# helpdeskQueue = Queue(
#     "helpdeskQueue", {"connection": {"host": "10.8.8.95", "port": 6380}}
# )

# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)

# class MessageType(Enum):
#     INTERACTIVE = "interactive"
#     TEXT = "text"
#     BUTTON = "button"

# async def process_api_response(response: httpx.Response, action: str = "API call"):
#     """Process API response and log relevant information"""
#     logger.info(f"{action} status code: {response.status_code}")
    
#     if response.status_code == 200:
#         try:
#             data = response.json()
#             if "code" in data:
#                 logger.info(f"{action} response code: {data['code']}")
#                 if data.get("code") == "X1" and "data" in data:
#                     logger.warning(f"{action} error: {data['data'].get('Error')}")
#             return data
#         except ValueError as e:
#             logger.error(f"Failed to parse JSON response: {e}")
#             return None
#     return None

# async def update_message_status(user_phone_number: str, message_id: str, sender: str, message_status: str):
#     """Update message status using dynamic headers and parameters."""
#     async with httpx.AsyncClient() as client:
#         headers = {"Phone-Number": user_phone_number}
#         params = {
#             "messageId": message_id,
#             "sender": sender,
#             "message_status": message_status
#         }
#         try:
#             res = await client.post(UPDATE_API_URL, headers=headers, params=params)
#             await process_api_response(res, "Update API")
#         except httpx.RequestError as e:
#             logger.error(f"Request error while updating message status: {e}")

# @app.route("/webhook", methods=["POST"])
# async def webhookPost():
#     body = await request.get_json()
#     logger.info(f"Webhook POST body: {body}")

#     try:
#         entry = body["entry"][0]["changes"][0]["value"]
        
#         # Extract business phone ID from the message
#         business_phone_id = entry.get("metadata", {}).get("phone_number_id")
        
#         # Check if business ID matches
#         if business_phone_id != "385912324613598":
#             logger.warning(f"Business ID mismatch. Expected: 385912324613598, Received: {business_phone_id}")
#             return jsonify({"message": "Invalid business ID"}), 403
        
#         if "messages" in entry:
#             message = entry["messages"][0]
#             user_phone_number = message["from"]
#             message_id = message["id"]
#             message_type = message["type"]
            
#             # Determine sender based on message type
#             sender = "System"
#             if message_type == MessageType.BUTTON.value:
#                 sender = entry.get("contacts", [{}])[0].get("profile", {}).get("name", "System")

#             logger.info(f"Received message from: {user_phone_number}")

#             if message_type in [m.value for m in MessageType]:
#                 await helpdeskQueue.add("myHelpdeskJob", body)

#             # Update message status
#             await update_message_status(user_phone_number, message_id, sender, "received")

#         elif "statuses" in entry:
#             status = entry["statuses"][0]
#             user_phone_number = status["recipient_id"]
#             message_id = status["id"]
#             message_status = status["status"]
            
#             # Update message status
#             await update_message_status(user_phone_number, message_id, "System", message_status)

#     except KeyError as e:
#         logger.error(f"KeyError: {e}. Unexpected message structure.")
#     except httpx.HTTPStatusError as e:
#         logger.error(f"HTTP error: {e}")
#     except Exception as e:
#         logger.error(f"Unexpected error: {e}\n{traceback.format_exc()}")

#     return jsonify({"message": "Webhook received successfully"})

# @app.route("/webhook", methods=["GET"])
# async def webhookGet():
#     mode = request.args.get("hub.mode")
#     token = request.args.get("hub.verify_token")
#     challenge = request.args.get("hub.challenge")

#     if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
#         return challenge
#     return "", 403

# if __name__ == "__main__":
#     app.run(debug=True, host="0.0.0.0", port=PORT)
