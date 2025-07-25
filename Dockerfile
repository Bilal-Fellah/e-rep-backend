FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl wget gnupg unzip fonts-liberation libnss3 libatk-bridge2.0-0 \
    libgtk-3-0 libxss1 libasound2 libxcomposite1 libxrandr2 libxdamage1 \
    libgbm1 libpango-1.0-0 libpangocairo-1.0-0 libcups2 libx11-xcb1 \
    libxshmfence1 libglu1-mesa libxtst6 libenchant-2-2 libsecret-1-0 \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy your files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN python -m playwright install --with-deps

EXPOSE 10000

# Start the app
CMD ["hypercorn", "run:app", "--bind", "0.0.0.0:10000"]
