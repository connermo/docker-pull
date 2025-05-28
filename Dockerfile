# Build frontend
FROM node:18-alpine as frontend-builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Build the app
RUN npm run build

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    docker.io \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# Copy backend files
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/backend/downloads
RUN mkdir -p /app/backend/static

# Copy frontend build files
COPY --from=frontend-builder /app/build/* /app/backend/static/
COPY --from=frontend-builder /app/build/static /app/backend/static/static

# Copy backend code
COPY backend/ /app/backend/

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Set working directory
WORKDIR /app/backend

# Expose ports
EXPOSE 8000

# Set environment variables
ENV API_HOST=0.0.0.0
ENV API_PORT=8000
ENV DOCKER_REGISTRY_MIRROR=""
ENV DOCKER_HTTP_PROXY=""
ENV DOCKER_HTTPS_PROXY=""

# Create startup script
RUN echo '#!/bin/bash\nservice nginx start\npython main.py' > /app/start.sh && \
    chmod +x /app/start.sh

# Start both nginx and backend
CMD ["/app/start.sh"] 