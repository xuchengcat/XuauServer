FROM node:22-alpine

WORKDIR /app
COPY --chown=1000:1000 client.js bangcle.js bangcle_auth_tables.js wbsk.js wbsk_tables.js runner.js ./

USER 1000:1000
CMD ["node", "runner.js"]
