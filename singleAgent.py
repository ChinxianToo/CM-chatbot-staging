import json
import httpx
from typing import Literal
from langchain_core.tools import tool
from langgraph.graph import MessagesState, StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnablePassthrough
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.prebuilt import ToolInvocation, ToolExecutor
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from helpdeskPhoneCheck import process_phone_number
from datetime import datetime, timedelta


BASE_API_URL = "https://cmhelpdesk.cmg.com.my/demo/chatbot_wsc"
MODEL_BASE_URL = "http://10.1.2.96:11434/v1"
# MODEL_BASE_URL = "http://10.8.8.95:11434/v1"

model = ChatOpenAI(
    # model="llama3-groq-tool-use",
    model="llama3.1:latest",
    # model="llama3.2:3b",
    temperature=0,
    base_url=MODEL_BASE_URL,
    api_key="ollama",
)

def format_date(date_string):
    try:
        if 'T' in date_string:
            # Handle ISO format
            date_obj = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        else:
            # Handle 'YYYY-MM-DD HH:MM' format
            date_obj = datetime.strptime(date_string, '%Y-%m-%d %H:%M')
        
        day = date_obj.day
        if 10 <= day % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
        
        return date_obj.strftime(f'%d{suffix} %B %Y, %I:%M %p').replace(' 0', ' ')
    except (ValueError, AttributeError):
        return date_string  # Return original string if parsing fails

# def format_closed_date(date_string):
#     try:
#         if 'T' in date_string:
#             # Handle ISO format
#             date_obj = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
#         else:
#             # Handle 'YYYY-MM-DD HH:MM' format
#             date_obj = datetime.strptime(date_string, '%Y-%m-%d %H:%M')

#         # Add 8 hours to the date
#         date_obj += timedelta(hours=8)

#         day = date_obj.day
#         if 10 <= day % 100 <= 20:
#             suffix = 'th'
#         else:
#             suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')

#         return date_obj.strftime(f'%d{suffix} %B %Y, %I:%M %p').replace(' 0', ' ')
#     except (ValueError, AttributeError):
#         return date_string  # Return original string if parsing fails

# def format_resolution_date(date_str):
#     # Parse the input date string
#     date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")

#     # Add 8 hours to the date
#     date_obj += timedelta(hours=8)

#     # Format the day with ordinal suffix
#     day = int(date_obj.strftime("%d"))
#     if 4 <= day <= 20 or 24 <= day <= 30:
#         suffix = "th"
#     else:
#         suffix = ["st", "nd", "rd"][day % 10 - 1]

#     # Format the final date string
#     formatted_date = date_obj.strftime(f"%d{suffix} %B %Y, %I:%M %p")
#     return formatted_date

def format_date_with_ordinal(date_obj):
    # Add the ordinal suffix for the day
    day = date_obj.day
    if 10 <= day % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')

    # Format the date with the suffix and return it
    return date_obj.strftime(f'%d{suffix} %B %Y, %I:%M %p').replace(' 0', ' ')

def format_resolution_date(date_string):
    try:
        # Parse the ISO format date
        date_obj = datetime.fromisoformat(date_string.replace('Z', '+00:00'))

        # Add 8 hours to the date
        date_obj += timedelta(hours=8)

        # Format the date with ordinal suffix
        return format_date_with_ordinal(date_obj)
    except (ValueError, AttributeError):
        return date_string  # Return the original string if parsing fails

def format_closed_date(date_string):
    try:
        # Parse the ISO format date
        date_obj = datetime.fromisoformat(date_string.replace('Z', '+00:00'))

        # Add 8 hours to the date
        date_obj += timedelta(hours=8)

        # Format the date with ordinal suffix
        return format_date_with_ordinal(date_obj)
    except (ValueError, AttributeError):
        return date_string  # Return the original string if parsing fails


@tool
def get_function(config: RunnableConfig) -> dict: 
    """
    Use this function immediately when the user asks to check their ticket status.
    Use this function when user wants to know or check their existing tickets such as "My ticket".
    Use this function when user wants to check ticket.
    Fetch a list of ticket numbers for the user and display only those with specific statuses.
    After fetching the tickets, prompt the user to choose a specific ticket number.
    Return 'No outstanding tickets found' if all retrieved tickets are of 'released' status or excluded.
    """

    # Define the list of valid statuses (both IDs and descriptions)
    valid_statuses = {
        "IP", "P", "IORT", "PORT", "IPRT", "PPRT", "IRMT", "O", 
        "HA", "PRMT", "OP", "In Progress", "Pending", 
        "In Progress to ORT", "Pending ORT", "In Progress to PRT", 
        "Pending PRT", "In Progress (Remote)", "Open", "Assigned", 
        "Pending IRT",
    }

    phone_number = config["metadata"]["user_phone_number"]
    print("USER PHONE: " + phone_number)

    test = process_phone_number(
        phone_number,
        base_api_url="https://cmhelpdesk.cmg.com.my/demo/chatbot_wsc/ticket",
    )
    phone = test
    print(phone)

   

    # Define statuses to exclude
    excluded_statuses = {"LC", "Closed"}

    try:
        # Update to use params for GET requests
        response = httpx.get(
            f"{BASE_API_URL}/ticket",
            headers={"Phone-Number": phone},
            params={"phone": phone},  # Use params for GET requests
            timeout=10.0
        )

        # Check if the response is successful
        response.raise_for_status()  # Raises an HTTPError for bad responses
        response_dict = response.json()
        
        # Validate the structure of the response
        if "data" not in response_dict or not isinstance(response_dict["data"], dict):
            return {"sarchurzay": "Invalid response structure from the API."}

    except httpx.HTTPStatusError as e:
        return {"sarchurzay": f"Error contacting the API: {str(e)}"}
    except json.JSONDecodeError:
        return {"sarchurzay": "Failed to decode JSON response from the API."}
    except httpx.RequestError as e:
        return {"sarchurzay": f"Request error: {str(e)}"}
    except Exception as e:
        return {"sarchurzay": f"An unexpected error occurred: {str(e)}"}

    all_tickets = []
    ticket_types = ["IncidentLog", "inquiryTicket", "RequestTicket"]
    
    for ticket_type in ticket_types:
        ticket_list = response_dict["data"].get(ticket_type, [])
        for ticket in ticket_list:
            ext_log_id = ticket.get("ext_log_id")
            status_id = ticket.get("log_status", [{}])[-1].get("status_id")
            status_desc = ticket.get("log_status", [{}])[-1].get("status_desc")
            created_at = ticket.get("created_at")
            title = ticket.get("title", {}).get("name", "No Title")  # Get the title

            # Include tickets only if their status (ID or description) is valid and not excluded
            if (status_id in valid_statuses or status_desc in valid_statuses) and (
                status_id not in excluded_statuses and
                status_desc not in excluded_statuses
            ):
                all_tickets.append({"ext_log_id": ext_log_id, "created_at": created_at, "title": title})

    # Sort tickets by created_at in descending order
    all_tickets.sort(key=lambda x: x["created_at"], reverse=True)

    if not all_tickets:
        return {"message": "You do not have any open tickets in CM Helpdesk."}

    # Extract sorted ext_log_ids
    sorted_ticket_info = [f"{ticket['ext_log_id']} - {ticket['title']}" for ticket in all_tickets]

    # Format the message and return the ticket numbers
    return {
        "message": f"CNF001: {'|'.join(sorted_ticket_info)}",
        "ticket_info": sorted_ticket_info,
    }


@tool
def post_function(input_str: str, config: RunnableConfig) -> dict:
    """
    Use this function when the user provides one or more specific ext_log_id.
    Search for tickets by ext_log_id from IncidentLog, InquiryTicket, or RequestTicket.
    Return information of the specific ticket.
    Otherwise, return a message that the ticket is not registered under the user's phone number.
    """
    valid_statuses = [
        "In Progress", "Pending", "In Progress to ORT", "Pending ORT",
        "In Progress to PRT", "Pending PRT", "In Progress (Remote)",
        "Open", "Assigned", "Pending IRT", "Resolved",
    ]

    phone_number = config["metadata"]["user_phone_number"]
    print("USER PHONE: " + phone_number)
    test = process_phone_number(
        phone_number,
        base_api_url="https://cmhelpdesk.cmg.com.my/demo/chatbot_wsc/ticket",
    )
    phone = test
    print(phone)

    # Handle both input formats
    ext_log_ids = []

    if isinstance(input_str, str):
        if "ext_log_id:" in input_str:
            ext_log_ids = [id.split(": ")[1].strip() for id in input_str.split(",") if "ext_log_id:" in id]
        else:
            ext_log_ids = [input_str.strip()]
    elif isinstance(input_str, list):
        for item in input_str:
            if "ext_log_id:" in item:
                ext_log_ids.append(item.split(": ")[1].strip())
            else:
                ext_log_ids.append(item.strip())
    else:
        return {"sarchurzay": "Invalid input format for ext_log_ids"}

    if not ext_log_ids:
        return {"sarchurzay": "At least one ext_log_id (ticket number) is required to check your ticket status."}

    print("Processed ext_log_ids:", ext_log_ids)

    api_url = f"{BASE_API_URL}/ticket"
    headers = {"Phone-Number": phone}
    ticket_types = ["IncidentLog", "InquiryTicket", "RequestTicket"]
    results = []
    print(ext_log_ids)

    def format_activity_date(date_string):
        try:
            activity_date = datetime.strptime(date_string, '%Y-%m-%d %H:%M')
            day = activity_date.day
            if 10 <= day % 100 <= 20:
                suffix = 'th'
            else:
                suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
            return activity_date.strftime(f'%d{suffix} %B %Y, %I:%M %p').replace(' 0', ' ')
        except (ValueError, AttributeError):
            return date_string

    for ext_log_id in ext_log_ids:
        ticket_found = False
        error_count = 0

        for ticket_type in ticket_types:
            if ticket_found:
                break

            try:
                print(f"Fetching ticket for ext_log_id: {ext_log_id} of type {ticket_type}")
                response = httpx.get(
                    api_url,
                    headers=headers,
                    params={"ticket_type": ticket_type, "id": ext_log_id},
                    timeout=10.0
                )

                print(f"API Response for {ext_log_id}: {response.text}")

                # If we get a 500 status, increment error count and continue to next ticket type
                if response.status_code == 500:
                    error_count += 1
                    continue

                response.raise_for_status()
                res = response.json()

                if res and "data" in res and res["data"]:
                    data = res["data"]
                    if ticket_type == "RequestTicket":
                        status = data.get("log_status", [{}])[0].get("status_id", "Unknown")
                        status_desc = data.get("log_status", [{}])[0].get("status_desc", "Unknown")
                    else:
                        if isinstance(data, list) and len(data) > 0:
                            data = data[0]
                        status = data.get("log_status", [{}])[-1].get("status_id", "Unknown")
                        status_desc = data.get("log_status", [{}])[-1].get("status_desc", "Unknown")
                        print(status_desc)

                    created_at_value = format_date(data.get("created_at", "Unknown Date")) # resolution date

                    print("resolution date orig ", data.get("created_at", "Unknown Date"))
                    
                    print("resolution date ",created_at_value)


                    if status in valid_statuses or status_desc in valid_statuses:
                        latest_activities = []
                        formatted_action_dates = []  # New list to store formatted action dates
                        if "activityLogs" in res and isinstance(res["activityLogs"], list):
                            for activity in res["activityLogs"][:3]:
                                original_date = activity.get("action_date", "Unknown Date")
                                formatted_date = format_activity_date(original_date)
                                formatted_action_dates.append(formatted_date)  # Store the formatted date
                                activity_remark = activity.get("activity_remarks", "No remarks available")
                                activity_remark = activity_remark.replace("<b>", "").replace("</b>", "")
                                if activity_remark:
                                    latest_activities.append(f"[{formatted_date}] {activity_remark}")

                        # Print the formatted action dates for debugging
                        print("Formatted Action Dates for ticket", ext_log_id)
                        for i, date in enumerate(formatted_action_dates, 1):
                            print(f"Formatted Action Date {i}: {date}")

                        title_name = data.get("title", {}).get("name", "Unknown Title")

                    
                        results.append({
                            "Ticket Number": data.get("ext_log_id", ext_log_id),
                            "Ticket Type": ticket_type,
                            "Status": status_desc,
                            "Reported Date": created_at_value,
                            "Title": title_name,
                            "Message": data.get("description", "No Description Available"),
                            "Latest Activities": latest_activities,
                        })
                        ticket_found = True
                        break
                    elif status_desc.lower() == "released":
                        ticket_number = data.get("ext_log_id", ext_log_id)
                        resolution_date = format_resolution_date(data['log_resolution_date'])
                        title = data['title']['name']
                        status = data['log_status'][0]['status_desc']
                        resolution = data['log_resolution']
                        root_cause = data['root_cause']
                        
                        results.append({
                            "Ticket Number": ticket_number,
                            "Resolution Date": resolution_date,
                            "Title": title,
                            "Status": status,
                            "Resolution": resolution,
                            "Root Caused": root_cause
                        })
                        ticket_found = True
                        break

                    elif status_desc.lower() == "closed":
                        updated_at_value = format_closed_date(data["closed_log"][0].get("updated_at", "Unknown Date")) # closed date
                        ticket_number = data.get("ext_log_id", ext_log_id)
                        resolution_date = format_resolution_date(data['log_resolution_date'])
                        title = data['title']['name']
                        status = data['log_status'][0]['status_desc']
                        resolution = data['log_resolution']
                        root_cause = data['root_cause']
                        
                        results.append({
                            "Ticket Number": ticket_number,
                            "Resolution Date": resolution_date,
                            "Title": title,
                            "Status": status,
                            "Resolution": resolution,
                            "Root Caused": root_cause,
                            "Closed Date": updated_at_value,
                        })
                        ticket_found = True
                        break

            except httpx.HTTPStatusError as e:
                print(f"HTTP error for {ext_log_id}: {e.response.status_code}, {e.response.text}")
                results.append({"sarchurzay": "Please use the correct ticket number format."})
                continue
            except httpx.RequestError as e:
                print(f"Request error: {e}")
                results.append({"sarchurzay": "Please use the correct ticket number format."})
                continue

        # After trying all ticket types, check if we should add an error message
        if error_count == len(ticket_types):  # If we got 500 status for all ticket types
            results.append({
                "Ticket Number": ext_log_id,
                "message": "This ticket number is not registered under your phone number.",
            })
        elif not ticket_found:  # If we didn't find the ticket but didn't get all 500s
            results.append({
                "Ticket Number": ext_log_id,
                "message": "Unable to find ticket information.",
            })

    # Format the results for the response
    formatted_results = []
    for result in results:
        if "message" in result:
            formatted_results.append(f"{result['message']}")
        elif "Resolution" in result:
            if result.get("Closed Date"):  # Check if it's a closed ticket
                formatted_results.append(
                f"Hi here! We would like to notify that your ticket is Closed! Please refer to below details:\n\n"
                f"*Ticket Number:* {result['Ticket Number']}\n"
                f"*Resolution Date:* {result['Resolution Date']}\n"
                f"*Title:* {result['Title']}\n"
                f"*Status:* {result['Status']}\n"
                f"*Resolution:* {result['Resolution']}\n"
                f"*Root Cause:* {result['Root Caused']}\n\n"
                f"*Closed Date:* {result['Closed Date']}"
            )
            else:  # Released ticket
                print("hi relased")
                formatted_results.append(
                    f"Hi here! We would like to notify that your ticket is Released! Please refer to below details:\n\n"
                    f"*Ticket Number:* {result['Ticket Number']}\n"
                    f"*Resolution Date:* {result['Resolution Date']}\n"
                    f"*Title:* {result['Title']}\n"
                    f"*Status:* {result['Status']}\n"
                    f"*Resolution:* {result['Resolution']}\n"
                    f"*Root Cause:* {result['Root Caused']}"
                )
        else:  # This is an active ticket
            print(66666666666666666666666666, result['Reported Date'])
            latest_activities = "\n".join(result["Latest Activities"]) if result["Latest Activities"] else "No activities found."
            formatted_results.append(
            "*Ticket Details*\n"
            f"*Ticket Number:* {result['Ticket Number']}\n"
            f"*Reported Date:* {result['Reported Date']}\n"
            f"*Status:* {result['Status']}\n"
            f"*Type:* {result['Ticket Type']}\n"
            f"*Issue:* {result['Title']}\n\n"
            f"*Latest Updates:*\n\n"
            f"{latest_activities}"
        )

    print("helpdesk agent")
    print(f"results: {formatted_results}")
    print("results: \n\n".join(formatted_results))
    print("helpdesk agent")
    return {"results": "\n\n".join(formatted_results)}

tools = [post_function, get_function]
tool_executor = ToolExecutor(tools)


class Response(BaseModel):
    """Final answer to the user regarding their ticket status"""

    ticket_status: str = Field(description="The current status of the user's ticket")
    ticket_type: str = Field(description="The ticket type of the user's ticket")
    date_created: str = Field(description="The date created of the user's ticket")
    latest_activities: str = Field(description="3 latest activities about the ticket")
    next_steps: str = Field(
        description="Information on what the user should do next, if any action is required"
    )

# class ChatResponse(BaseModel):
#     """Schema for chat responses that don't require tool use"""
#     message: str = Field(description="The response message to the user")

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a helpdesk assistant for Llama 3.1. Your primary tasks involve using get_function and post_function to handle ticket-related queries. Follow these guidelines:

                1. Use get_function to retrieve ticket lists when users ask about status without providing a specific number.
                2. Use post_function to fetch details for a specific ticket when given a ticket number (ext_log_id).
                3. For queries about multiple tickets, provide information on all mentioned tickets, summarizing clearly and concisely.
                4. Extract ALL ticket statuses, not just the last one. Consider all provided statuses.
                5. If a user provides a ticket number, prioritize using post_function with the given ticket number.
                6. For invalid ticket numbers, reply: "The ticket number you provided is not registered under your phone number."
                7. For non-ticket related requests, unclear queries, or mentions of ticket creation and appointments, respond with: I'm sorry, I can't assist with that or I do not understand your question.
                8. Always provide the exact status as returned by the API, without simplifying or generalizing it.
                9. For general greetings or non-ticket inquiries, respond with a friendly greeting like: Hello! How can I assist you today?, Don't use get_function unless ticket information is requested.
                10. If get_function returns no tickets, respond ONLY with: "No outstanding tickets found for this phone number."
                11. If the user asks for help (e.g., "Help", "help", "Help me", "help me", "Follow up", "Good"), respond with:
                "I'm here to help you with ticket-related inquiries. How may I assist you today?"
                12. If the user asks about the chatbot's purpose, functions, or capabilities (e.g., "what can you do", "what is the purpose of this chatbot", "what are your functions", "who are you", "report", "reopen ticket"), respond with:

                "As a helpdesk assistant, I'm here to help you with ticket-related inquiries. I can:
                - Check the status of your existing tickets
                - Provide details on specific tickets when given a ticket number
                - List your current open tickets
                \n\nHow may I assist you with your tickets today?"

                

                IMPORTANT: When providing ticket information from post_function, use this format ONLY when tickets are found and neither ticket status is Closed nor Released:
                *Ticket Details*
                *Ticket Number:* [ticket number]
                *Reported Date:* [date created]
                *Status:* [status]
                *Type:* [ticket type]
                *Issue:* [title]
                
                *Latest Updates:*
                
                [Date and Time]
                Activity description
                [Date and Time]
                Activity description
                [Date and Time]
                Activity description

                IMPORTANT: When providing ticket information from post_function,use this format ONLY when ticket status is Closed:
                Hi here! We would like to notify that your ticket is Closed! Please refer to below details:

                *Ticket Number:* [ticket number]
                *Resolution Date:* [resolution date]
                *Title:* [title]
                *Status:* [status]
                *Resolution:* [resolution]
                *Root Cause:* [root cause]
                *Closed Date:* [closed date]

                IMPORTANT: When providing ticket information from post_function,use this format ONLY when ticket status is Released:
                Hi here! We would like to notify that your ticket is Released! Please refer to below details:

                *Ticket Number:* [ticket number]
                *Resolution Date:* [resolution date]
                *Title:* [title]
                *Status:* [status]
                *Resolution:* [resolution]
                *Root Cause:* [root cause]
            """,
        ),
        MessagesPlaceholder(variable_name="messages", optional=True),
    ]
)


# Create the tools to bind to the model
tools = [convert_to_openai_function(t) for t in tools]
tools.append(convert_to_openai_function(Response))
# tools.append(convert_to_openai_function(ChatResponse))
model = {"messages": RunnablePassthrough()} | prompt | model.bind_tools(tools)


def should_continue(state: MessagesState) -> Literal["agent", "action", "end"]:
    """Return the next node to execute."""
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage):
        return "agent"
    elif last_message.additional_kwargs.get("tool_calls"):
        return "action"
    else:
        return "end"


# def call_model(state: MessagesState, config: RunnableConfig):
#     messages = []
#     for m in state["messages"][::-1]:
#         messages.append(m)
#         if len(messages) >= 10:
#             if messages[-1].type != "tool":
#                 break
#     last_message = messages[0]
    
#     if last_message.type == "tool":
#         try:
#             # First try to parse as JSON
#             parsed_content = json.loads(last_message.content.replace("'", '"'))
            
#             # Only after successful JSON parsing, check for specific keys
#             if "CNF001" in last_message.content:
#                 return {"messages": [AIMessage(content=parsed_content["message"])]}
#             elif "error" in parsed_content:  # Check for error key in parsed JSON
#                 return {"messages": [AIMessage(content=parsed_content["error"])]}
#             elif "results" in parsed_content:
#                 return {"messages": [AIMessage(content=parsed_content["results"])]}
            
#             # If no specific keys found but valid JSON, return the content
#             return {"messages": [AIMessage(content=last_message.content)]}
            
#         except json.JSONDecodeError:
#             # If not valid JSON, return the content as is
#             return {"messages": [AIMessage(content=last_message.content)]}

#     response = model.invoke(messages[::-1], config)
#     return {"messages":[response]}


# def call_model(state: MessagesState, config: RunnableConfig):
#     messages = []
#     for m in state["messages"][::-1]:
#         messages.append(m)
#         if len(messages) >= 10:
#             if messages[-1].type != "tool":
#                 break
#     last_message = messages[0]
#     # print(messages[::-1])
#     if last_message.type == "tool":
#         if "CNF001" in last_message.content:
#             msg = json.loads(last_message.content.replace("'", '"'))
#             return {"messages": [AIMessage(content=msg["message"])]}
#         elif "sarchurzay" in last_message.content:
#             error_message = json.loads(last_message.content.replace("'", '"'))["sarchurzay"]
#             return {"messages": [AIMessage(content=error_message)]}

#     response = model.invoke(messages[::-1], config)
#     return {"messages": [response]}

def call_model(state: MessagesState, config: RunnableConfig):
    messages = []
    for m in state["messages"][::-1]:
        messages.append(m)
        if len(messages) >= 10:
            if messages[-1].type != "tool":
                break
    last_message = messages[0]
    print(messages[::-1])
    if last_message.type == "tool":
        if "CNF001" in last_message.content:
            msg = json.loads(last_message.content.replace("'", '"'))
            return {"messages": [AIMessage(content=msg["message"])]}

    response = model.invoke(messages[::-1], config)
    print(response)
    return {"messages": [response]}


def call_tool(state: MessagesState, config: RunnableConfig):
    messages = state[
        "messages"
    ]  # We know the last message involves at least one tool call
    last_message = messages[-1]
    # We loop through all tool calls and append the message to our message log
    for tool_call in last_message.additional_kwargs["tool_calls"]:
        action = ToolInvocation(
            tool=tool_call["function"]["name"],
            tool_input=json.loads(tool_call["function"]["arguments"]),
            id=tool_call["id"],
        )

        # We call the tool_executor and get back a response
        response = tool_executor.invoke(action, config=config)
        # We use the response to create a FunctionMessage
        function_message = ToolMessage(
            content=str(response), name=action.tool, tool_call_id=tool_call["id"]
        )
        print(function_message)

        # Add the function message to the list
        messages.append(function_message)
    # We return a list, because this will get added to the existing list

    return {"messages": messages}


workflow = StateGraph(MessagesState)
workflow.add_node("agent", call_model)
workflow.add_node("action", call_tool)
workflow.add_edge(START, "agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "agent": "agent",
        "action": "action",
        "end": END,
    },
)
workflow.add_edge("action", "agent")

helpdesk_agent = workflow.compile()
