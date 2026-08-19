# FleetFlow frontend is plain HTML/CSS/JS with no build step (no React,
# no bundler) — so this Dockerfile just serves the static files with
# nginx. If you deploy the frontend to Vercel/Netlify/GitHub Pages
# instead (recommended — see README "Deployment"), you don't need this
# file at all; it's here for the Docker/docker-compose local-stack path.
FROM nginx:alpine

COPY . /usr/share/nginx/html

EXPOSE 80

# nginx's default config already serves index.html at / and static
# assets correctly for this project — no custom config needed.
