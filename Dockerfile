# Use a lightweight Python base image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy all files to the container
COPY . .

# Install dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Set a default port (for health check if using keep_alive)
ENV PORT=8080

# Command to run your bot
CMD ["python", "bot/main.py"]
 
