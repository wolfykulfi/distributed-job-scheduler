FROM node:20-slim AS build

WORKDIR /app
COPY package*.json ./
RUN npm install

COPY . .
# Baked into the JS bundle at build time -- the browser calls this URL directly, so it must be
# reachable from the host (not a container-internal hostname).
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
