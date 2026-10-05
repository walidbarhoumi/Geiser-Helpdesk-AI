# ──────────────────────────────────────────────────────────────
# GEISER Frontend — Multi-stage Production Dockerfile
# Stage 1: Node build  →  Stage 2: Nginx serve
# ──────────────────────────────────────────────────────────────

# ── Stage 1: Build ────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies (layer-cached)
COPY package.json package-lock.json* yarn.lock* pnpm-lock.yaml* ./
RUN npm ci --prefer-offline 2>/dev/null || npm install

# Copy source
COPY . .

# Build arguments — allow API URL override at image build time
ARG VITE_API_URL=http://localhost:8000/api/v1
ARG VITE_WS_HOST=

ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_WS_HOST=${VITE_WS_HOST}

# Production build
RUN npm run build

# ── Stage 2: Serve with Nginx ──────────────────────────────────
FROM nginx:1.27-alpine

# Remove default nginx site
RUN rm -f /etc/nginx/conf.d/default.conf

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/geiser.conf

# Copy built assets from Stage 1
COPY --from=builder /app/dist /usr/share/nginx/html

# Non-root nginx: adjust permissions
RUN chown -R nginx:nginx /usr/share/nginx/html \
    && chmod -R 755 /usr/share/nginx/html \
    && chown -R nginx:nginx /var/cache/nginx \
    && chown -R nginx:nginx /var/log/nginx \
    && chown -R nginx:nginx /etc/nginx/conf.d \
    && touch /var/run/nginx.pid \
    && chown nginx:nginx /var/run/nginx.pid

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
