FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

ARG REACT_APP_ORCHESTRATOR_URL=http://localhost:3001
ARG REACT_APP_WS_URL=ws://localhost:3001
ENV REACT_APP_ORCHESTRATOR_URL=$REACT_APP_ORCHESTRATOR_URL
ENV REACT_APP_WS_URL=$REACT_APP_WS_URL

COPY . .
RUN npm run build

# ── runtime ────────────────────────────────────────────────────────────────────
FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
EXPOSE 80
