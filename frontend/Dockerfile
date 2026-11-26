# Build-Stage
FROM node:22-alpine AS builder

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
# Fassung für den Vergleich mit dem Server und die Sicherheitsköpfe (vite.config.js liest ../VERSION und
# ../docker/sicherheit.conf)
COPY VERSION /VERSION
COPY docker/sicherheit.conf /docker/sicherheit.conf
RUN npm run build

# Serve-Stage
FROM nginx:alpine

COPY --from=builder /build/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/sicherheit.conf /etc/nginx/snippets/sicherheit.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
