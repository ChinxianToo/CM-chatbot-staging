import asyncio
import requests
import json
from bullmq import Worker
from singleAgent import helpdesk_agent
from app import GRAPH_API_TOKEN
from langchain_core.messages import HumanMessage
import os
from dotenv import load_dotenv
# from fetch_phone_number import fetch_phone_number
import re
import redis
import sys

load_dotenv()
GRAPH_API_TOKEN = os.environ.get("GRAPH_API_TOKEN")

redis_client = redis.Redis(host='10.8.8.95', port=6380, db=0)

def fetch_phone_number(wproj_id):
    url = os.getenv('API_URL', 'https://cmhelpdesk.cmg.com.my/demo/chatbot_wsc/project/tel')
    header_phone = os.getenv('HEADER_PHONE', '0162550255')
    
    headers = {
        "Phone-Number": header_phone
    }

    params = {
        "project_id": wproj_id
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") == "01" and data.get("data"):
            phone_number = data["data"]
            
            # Check if the data contains "invalid"
            if "invalid" in phone_number.lower():
                error_msg = "Invalid phone number in response"
                result = {"phone_number": "-", "error": error_msg, "wproj_id": wproj_id}
            else:
                result = {"phone_number": phone_number, "wproj_id": wproj_id}
        else:
            error_msg = "Phone number not found or invalid response code"
            result = {"phone_number": "-", "error": error_msg, "wproj_id": wproj_id}

    except requests.ConnectionError as e:
        error_msg = f"Connection error: {str(e)}. Please check if the URL is correct and accessible."
        result = {"phone_number": "-", "error": error_msg, "wproj_id": wproj_id}
    except requests.Timeout:
        error_msg = "The request timed out. Please check your network connection or try again later."
        result = {"phone_number": "-", "error": error_msg, "wproj_id": wproj_id}
    except requests.TooManyRedirects:
        error_msg = "Too many redirects. Please check the URL and try again."
        result = {"phone_number": "-", "error": error_msg, "wproj_id": wproj_id}
    except requests.RequestException as e:
        error_msg = f"Error fetching phone number: {str(e)}"
        result = {"phone_number": "-", "error": error_msg, "wproj_id": wproj_id}
    
    return result

def update_ticket(log_id, ticket, button_reply_id, phone_number):
    # Try the original phone number
    phone_variants = [phone_number, phone_number[1:]]  # Original and without the first digit

    for i, phone in enumerate(phone_variants):
        try:
            update_res = requests.post(
                "https://cmhelpdesk.cmg.com.my/demo/chatbot_wsc/ticket/release",
                headers={"Phone-Number": phone},
                json={"id": log_id, "ticket_type": ticket, "c_reply": button_reply_id},
            )
            
            # Check if the request was successful
            if update_res.status_code == 200:
                response_code = update_res.json().get("code")
                return response_code  # Exit if successful
        
        except requests.RequestException as e:
            pass
    
    return None  # Return None if both attempts failed


async def send_whatsapp_message(
    business_phone_number_id, to, message_body, context_message_id=None
):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": message_body},
    }
    
    if context_message_id:
        payload["context"] = {"message_id": context_message_id}

    response = requests.post(
        f"https://graph.facebook.com/v18.0/{business_phone_number_id}/messages",
        headers={"Authorization": f"Bearer {GRAPH_API_TOKEN}"},
        json=payload,
    )
    
    return response


async def process(job, job_token):
    body = job.data

    try:
        message = body["entry"][0]["changes"][0]["value"]["messages"][0]
        
        business_phone_number_id = body["entry"][0]["changes"][0]["value"]["metadata"][
            "phone_number_id"
        ]
        
        user_phone_number = message["from"]
        # user_phone_number = "60162550255"

        # hotline_result = fetch_phone_number("0")
        # logger.info(f"Hotline result: {hotline_result}")
        # hotline = hotline_result['phone_number']
        # logger.info(f"Hotline: {hotline}")

        # Authentication check
        auth_response = requests.post(
            "https://cmhelpdesk.cmg.com.my/demo/chatbot_wsc/auth/check",
            json={"phone_number": user_phone_number},
            timeout=10
        )
        
        phone=user_phone_number
    
        if auth_response.json().get("code") == "01":
        # Phone number is valid, exit function
            phone=user_phone_number
        else:
            # Step 2: If original number is invalid, try removing '6' at the start
            if user_phone_number.startswith("6"):
                phone_without_6 = user_phone_number[1:]
                
                auth_response = requests.post(
                    "https://cmhelpdesk.cmg.com.my/demo/chatbot_wsc/auth/check",
                    json={"phone_number": phone_without_6},
                    timeout=10
                )

                if auth_response.json().get("code") == "01":
                    # Phone number without '6' is valid, exit function
                    phone = phone_without_6
                else:
                    await send_whatsapp_message(
                        business_phone_number_id,
                        user_phone_number,
                        "Hello! Thank you for reaching out. It appears that we couldn't locate your details in our system. If you're a new user, please contact our Helpdesk team to get registered",
                        message["id"],
                    )
                    return
            else:
                await send_whatsapp_message(
                    business_phone_number_id,
                    user_phone_number,
                    "Hello! Thank you for reaching out. It appears that we couldn't locate your details in our system. If you're a new user, please contact our Helpdesk team to get registered",
                    message["id"],
                )
                return

        # Process different message types
        if message["type"] == "button" and "button" in message:
            user_message = message
            
            button_reply_id = user_message["button"]["payload"]
            
            wamid_value = message['context']['id']
            
            redis_data = redis_client.get(wamid_value)
            
            if redis_data:
                data = json.loads(redis_data)

                ext_log_id = data.get('ext_log_id')
                ticket = data.get('ticket')
                log_id = data.get("log_id")
                wproj_id = data.get("wproj_id")
            else:
                ext_log_id = ticket = log_id = wproj_id = None
            
            # Process rating buttons first before any other checks
            if button_reply_id in ["Good", "Poor"]:
                # Check if this ticket has already been rated using Redis
                rating_key = f"rating:{ext_log_id}"
                
                existing_rating = redis_client.get(rating_key)
                
                if existing_rating:
                    await send_whatsapp_message(
                        business_phone_number_id,
                        user_phone_number,
                        "You have already submitted your rating for this ticket.",
                        message["id"],
                    )
                    return

                # Handle "Good" button - submit rating and send thank you message
                if button_reply_id == "Good":
                    rating_payload = {
                        "log_id": log_id,
                        "ext_log_id": ext_log_id,
                        "ticket_type": ticket,
                        "rating": button_reply_id,
                        "wproj_id": wproj_id
                    }
                    
                    rating_response = requests.post(
                        "https://cmhelpdesk.cmg.com.my/demo/chatbot_wsc/survey/rating",
                        headers={"Phone-Number": phone},
                        json=rating_payload,
                        timeout=10
                    )
                    
                    if rating_response.status_code == 200:
                        # Store in Redis to prevent duplicate submissions
                        redis_client.set(rating_key, button_reply_id)
                        
                        # Send thank you message for feedback
                        await send_whatsapp_message(
                            business_phone_number_id,
                            user_phone_number,
                            "Thank you for your response",
                            message["id"],
                        )
                    else:
                        await send_whatsapp_message(
                            business_phone_number_id,
                            user_phone_number,
                            "Sorry, there was an error submitting your rating. Please try again later.",
                            message["id"],
                        )
                
                # Handle "Poor" button - no backend processing needed since it's a direct URL redirect
                elif button_reply_id == "Poor":
                    pass
                
                return

            # Only proceed with ticket status check for Yes/No buttons
            check_button_status = requests.get(
            "https://cmhelpdesk.cmg.com.my/demo/chatbot_wsc/ticket",
                params={"id": ext_log_id, "ticket_type": ticket},
                headers={"Phone-Number": phone},
                timeout=10
            )
            
            json_data = check_button_status.json()

            # Corrected status check - the status is nested under data -> log_status
            status_desc = None
            
            if json_data.get('code') == '01' and 'data' in json_data:
                log_status = json_data['data'].get('log_status', [])
                
                if log_status and isinstance(log_status, list) and len(log_status) > 0:
                    status_desc = log_status[0].get('status_desc')

            if status_desc == "Released":
                await send_whatsapp_message(
                    business_phone_number_id,
                    user_phone_number,
                    "You have already proceeded to ticket closure",
                    message["id"],
                )
                return
            

            # Process button actions only if ticket is not released
            if button_reply_id == "Yes":
                release_payload = {"id": log_id, "ticket_type": ticket, "c_reply": button_reply_id}
                
                update_res = requests.post(
                    "https://cmhelpdesk.cmg.com.my/demo/chatbot_wsc/ticket/release",
                    headers={"Phone-Number": phone},
                    json=release_payload,
                    timeout=10
                )
                
                code = update_res.json().get("code")

                if code == "01":
                    await send_whatsapp_message(
                        business_phone_number_id,
                        user_phone_number,
                        f"Your ticket {ext_log_id} is Released/Closed",
                        message["id"],
                    )

                    # proceed to send survey rating template
                    survey_payload = {
                        "data": {
                            "reported_by_mobile": user_phone_number,
                            "log_id": log_id,
                        },
                        "ext_log_id": ext_log_id,
                        "ticket": ticket
                    }

                    # Send survey notification
                    try:
                        survey_res = requests.post(
                            "http://10.8.8.95:2119/notification/survey_rating",
                            json=survey_payload,
                            headers={"Content-Type": "application/json"},
                            timeout=10
                        )
                        
                        survey_data = survey_res.json()
                        
                        if survey_data.get("status") == "OK":
                            pass
                            
                    except Exception as e:
                        pass

                else:
                    await send_whatsapp_message(
                        business_phone_number_id,
                        user_phone_number,
                        f"Failed to close your ticket {ext_log_id}",
                        message["id"],
                    )

            elif button_reply_id == "No":
                # No backend processing needed since "No" button is now a direct URL redirect
                pass
            
            else:
                await send_whatsapp_message(
                    business_phone_number_id,
                    user_phone_number,
                    "API server failure.",
                    message["id"],
                )

            return
            # input_message = HumanMessage(content=user_message)
        elif message["type"] == "interactive":
            title = message["interactive"]["list_reply"]["title"]
            
            input_message = HumanMessage(content=title)
            
        elif message["type"] == "text":
            user_message = message["text"]["body"]
            
            input_message = HumanMessage(content=user_message)

        else:
            send_whatsapp_message(
                business_phone_number_id,
                user_phone_number,
                f"Unsupported message type: {message['type']}",
                message["id"],
            )
            return

        state = {"messages": [input_message]}
        
        llm_config = {
            "configurable": {
                "user_phone_number": user_phone_number,
                "thread_id": user_phone_number,
            },
            "metadata": {
                "user_phone_number": user_phone_number,
            },
            "recursion_limit": 50,
        }
        
        llm_responses = helpdesk_agent.invoke(
            state,
            llm_config,
        )
        
        llm_response = llm_responses["messages"][-1].content
        print("llm_response: ", llm_response)

        if "CNF001" in llm_response and message["type"] == "text":
            ticket_info_str = llm_response.split("CNF001: ")[1]
            
            ticket_info = ticket_info_str.split("|")

            success, result_message = send_interactive_message(
                ticket_info,
                message,
                business_phone_number_id
            )

            if not success:
                await send_whatsapp_message(
                    business_phone_number_id,
                    message["from"],
                    f"An error occurred while sending ticket information. {result_message}",
                    message["id"]
                )
        else:
            await send_whatsapp_message(
                business_phone_number_id, message["from"], llm_response, message["id"]
            )

        # Mark message as read
        read_payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message["id"],
        }
        
        mark_read_response = requests.post(
            f"https://graph.facebook.com/v18.0/{business_phone_number_id}/messages",
            headers={"Authorization": f"Bearer {GRAPH_API_TOKEN}"},
            json=read_payload,
            timeout=10
        )

    except Exception as e:
        pass


def send_interactive_message(
    ticket_batch, message, business_phone_number_id
):
    # Limit the number of tickets to 10 to avoid potential length issues
    original_length = len(ticket_batch)
    ticket_batch = ticket_batch[:10]
    
    def truncate_text(text, max_length):
        """Helper function to truncate text and add ellipsis if needed"""
        if len(text) <= max_length:
            return text
        
        truncated = text[:max_length - 3] + "..."  # Reserve 3 characters for ellipsis
        return truncated
    
    sections = [
        {
            "title": "Your Latest Tickets",
            "rows": [
                {
                    "id": f"ticket_{i}",
                    "title": truncate_text(ticket.split(" - ")[0], 69),  # Truncate title to 69 chars
                    "description": truncate_text(" - ".join(ticket.split(" - ")[1:]), 72)  # Ensure description with ellipsis is exactly 72 chars
                }
                for i, ticket in enumerate(ticket_batch)
            ],
        }
    ]
    
    payload = {
        "messaging_product": "whatsapp",
        "to": message["from"],
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {
                "type": "text",
                "text": "Your Latest Outstanding Tickets",
            },
            "body": {"text": "Please select a ticket to view details."},
            "footer": {"text": "CMG"},
            "action": {"button": "Select Ticket", "sections": sections},
        },
        "context": {"message_id": message["id"]},
    }
    
    try: 
        response = requests.post(
            f"https://graph.facebook.com/v18.0/{business_phone_number_id}/messages",
            headers={"Authorization": f"Bearer {GRAPH_API_TOKEN}"},
            json=payload,
            timeout=10
        )
        
        response.raise_for_status()
        
        return True, "Message sent successfully"
        
    except requests.exceptions.RequestException as e:
        error_message = f"Error sending message: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_message += f"\nResponse content: {e.response.text}"
        return False, error_message


async def main():
    try:
        worker = Worker(
            "helpdeskQueue", process, {"connection": "redis://10.8.8.95:6380"}
        )
        
    except Exception as e:
        return

    while True:
        await asyncio.sleep(1)
        # Log every 30 seconds to show the worker is still alive
        # (You might want to remove this in production to reduce log noise)

    await worker.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        pass


