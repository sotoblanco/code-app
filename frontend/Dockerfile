FROM node:20-alpine

WORKDIR /app
RUN chown node:node /app

# Copy dependency files first (better layer caching)
COPY package.json package-lock.json ./

# Install dependencies and purge npm cache to keep layer small
RUN npm ci --prefer-offline --no-audit --no-fund && npm cache clean --force

# Copy application code directly with non-root node user (avoids duplicate layer)
COPY --chown=node:node . .

# Switch to non-root user
USER node

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD node -e "const http = require('http'); http.get('http://localhost:5173/', (res) => { process.exit(res.statusCode === 200 ? 0 : 1); }).on('error', () => process.exit(1));" || exit 1

# Run the dev server, exposed to all interfaces
CMD ["npm", "run", "dev", "--", "--host"]
