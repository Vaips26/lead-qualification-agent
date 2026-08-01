FROM node:20-slim

RUN apt-get update -y && apt-get install -y openssl

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

RUN npx prisma generate --schema=node_modules/@mastra/core/dist/prisma/schema.prisma

RUN npm run build

EXPOSE 3000
ENV NODE_ENV=production
CMD ["node", "dist/index.js"]
