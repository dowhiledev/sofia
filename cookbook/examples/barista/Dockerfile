FROM dowhiledev/nomos-base:latest
WORKDIR /app
COPY config.agent.yaml /app/config.agent.yaml
COPY barista_tools.py /app/src/tools/
CMD ["nomos", "serve", "--config", "config.agent.yaml"]
