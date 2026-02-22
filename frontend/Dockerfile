# frontend/Dockerfile
# Build Stage
FROM node:22-alpine as build

WORKDIR /app

# Copy package descriptors 
COPY package*.json ./

# Install all dependencies
RUN npm ci

# Copy the rest of the application
COPY . .

# Accept VITE_API_URL as a build argument
ARG VITE_API_URL

# Build the Vite React application. We explicitly bake in the backend URL instead of using relative paths
RUN VITE_API_URL=$VITE_API_URL npm run build

# Serve Stage using Nginx
FROM nginx:alpine

COPY nginx.conf.template /etc/nginx/nginx.conf.tmp

# Copy build output to Nginx's static file serving directory
COPY --from=build /app/dist /usr/share/nginx/html

# Explicitly use our own entrypoint to replace the ENV var
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port
EXPOSE 8080

CMD ["/entrypoint.sh"]
