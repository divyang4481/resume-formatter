FROM node:22-alpine AS build

WORKDIR /app

# Accept build-time environment (development or production)
ARG ENVIRONMENT=development

COPY package.json package-lock.json ./
RUN npm install

COPY . .
# If ENVIRONMENT is production, Angular will swap environment.ts with environment.prod.ts
RUN npm run build -- --configuration ${ENVIRONMENT}

FROM nginx:alpine
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
