FROM node:20-alpine

WORKDIR /app

# Install dependencies based on package-lock.json
COPY package.json package-lock.json* ./
RUN npm install

# Copy source code
COPY . .

# Build Next.js app
RUN npm run build

# Start Next.js app
CMD ["npm", "start"]

EXPOSE 3000
