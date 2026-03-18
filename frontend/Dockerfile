# /frontend/Dockerfile
FROM node:20-slim

# Set work directory
WORKDIR /app

# Install dependencies
COPY package.json ./
RUN npm install

# Copy project
COPY . .

# Expose port
EXPOSE 5173