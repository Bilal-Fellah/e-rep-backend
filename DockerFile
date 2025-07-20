# Use official Playwright base image with browser dependencies
FROM mcr.microsoft.com/playwright/python:v1.53.0-focal

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy entire project to /app in the container
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port used by your app
EXPOSE 10000

# Start your app using Hypercorn (adjust if needed)
CMD ["hypercorn", "run:app", "--bind", "0.0.0.0:10000"]
