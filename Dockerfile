# Use a single base image with Python, then install curl
FROM python:3.12-slim

# Install curl
RUN apt-get update && apt-get install -y curl

# Set the working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy in the rest of the application code
COPY . .

# Ensure the entrypoint script is executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# # Set environment variables
# ENV GRAPH_API_TOKEN="EAAHHeZBqAlvEBO9KeR75Ly1k9dGu9WZBPAV3tKZAbW4ZBDPSIaMTZBIkAMhOdJdu6DHFO9AZA69Trv1hez3y7nIJCUqtb0oc3SGsaJtpO6fhtOquCFOERmH9ZC7Sodu16yT5Sdi7m2sLgHZBdnhbrU8Kaz68HJX6kUYZAjjXfxt6zD6cZBGFOUiwF8zUvZCYUAHa7HrAQZDZD"
# ENV WEBHOOK_VERIFY_TOKEN="HAPPY"

# Expose the port and set entrypoint and default command
EXPOSE 8169
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "app.py"]
