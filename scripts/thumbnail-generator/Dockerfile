# Use the Playwright Docker image as the base image
FROM mcr.microsoft.com/playwright:v1.32.3-jammy

# Set the working directory
WORKDIR /app

# Copy package.json to the container
COPY package.json .

# Install dependencies
RUN npm install

# Copy the remaining files
COPY . .

# Create the output directory
RUN mkdir -p /app/output

# Run the script when the container is started
CMD ["node", "generate-thumbnail.js"]
