FROM node:20-bookworm-slim AS build
WORKDIR /src

COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci

COPY frontend/craco.config.js frontend/jsconfig.json frontend/tailwind.config.js frontend/postcss.config.js frontend/components.json ./
COPY frontend/public ./public
COPY frontend/src ./src

ARG REACT_APP_BACKEND_URL=http://localhost:8000
ENV REACT_APP_BACKEND_URL=${REACT_APP_BACKEND_URL}
ENV GENERATE_SOURCEMAP=false

RUN npm run build

FROM nginx:1.27-alpine
COPY docker/frontend.nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/build /usr/share/nginx/html
EXPOSE 80
