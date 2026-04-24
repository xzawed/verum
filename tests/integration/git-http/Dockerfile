FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx git git-core fcgiwrap spawn-fcgi \
    && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /srv/git /var/run/fcgiwrap /tmp/work
COPY nginx.conf /etc/nginx/nginx.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 80
HEALTHCHECK --interval=5s --timeout=3s --retries=10 \
    CMD git ls-remote http://localhost/verum-fixtures/sample-repo.git HEAD || exit 1
ENTRYPOINT ["/entrypoint.sh"]
