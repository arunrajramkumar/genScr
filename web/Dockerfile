# Production image: static export served by nginx (tiny, no Node at runtime).
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_SITE_NAME=genScr
ARG NEXT_PUBLIC_CONTACT_EMAIL=
ARG NEXT_PUBLIC_ENABLE_PROJECTIONS=false
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_SITE_NAME=$NEXT_PUBLIC_SITE_NAME \
    NEXT_PUBLIC_CONTACT_EMAIL=$NEXT_PUBLIC_CONTACT_EMAIL \
    NEXT_PUBLIC_ENABLE_PROJECTIONS=$NEXT_PUBLIC_ENABLE_PROJECTIONS \
    NEXT_TELEMETRY_DISABLED=1 STATIC_EXPORT=1
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/out /usr/share/nginx/html
EXPOSE 3000
