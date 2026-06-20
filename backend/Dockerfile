# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend code
COPY . .

# Create a system user/group and set owner on the app directory
RUN groupadd -g 10001 hearthgroup && \
    useradd -u 10001 -g hearthgroup -d /app -s /sbin/nologin hearthuser && \
    chown -R hearthuser:hearthgroup /app

# Switch to non-root user
USER hearthuser

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["python", "main.py"]
