# Multi-stage build for React frontend

# Stage 1: Build
FROM node:20-alpine AS builder

# Create a non-root user and set it as the running user
RUN groupadd -r myappgroup && useradd --no-log-init -r -g myappgroup myappuser

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Stage 2: Production with nginx
FROM nginx:alpine

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:80 || exit 1

# Switch to non-root user
USER myappuser

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
