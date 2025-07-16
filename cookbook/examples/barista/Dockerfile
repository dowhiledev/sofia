FROM ghcr.io/dowhiledev/nomos:latest
WORKDIR /app
COPY config.agent.yaml /app/config.agent.yaml
COPY barista_tools.py /app/barista_tools.py
CMD ["nomos", "serve", "--config", "config.agent.yaml"]
