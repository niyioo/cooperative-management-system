# /frontend/Dockerfile
FROM node:18-alpine

# Set work directory
WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy project
COPY . .

# Expose port
EXPOSE 5173