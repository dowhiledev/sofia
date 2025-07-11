# Deployment Guide

NOMOS provides multiple deployment options to suit different environments and requirements.

> [!TIP]
> For details on how Docker images are automatically built and published, see the [Docker Publishing Guide](../dev-deploy/docker-publishing.md).

## CLI Deployment

### Quick Deployment with CLI

The simplest way to deploy your agent is using the NOMOS CLI:

```bash
# Deploy with FastAPI server
nomos serve --config config.agent.yaml

# Custom port and workers
nomos serve --config config.agent.yaml --port 9000 --workers 4

# Load additional tools
nomos serve --config config.agent.yaml --tools tools.py --tools utils.py
```

See the [CLI Usage Guide](cli-usage.md) for complete deployment options.

## Docker Base Image

NOMOS provides a base Docker image that you can use to quickly containerize your agents. The base image is available from multiple registries:

- **GitHub Packages** (Recommended): `ghcr.io/dowhiledev/nomos:latest`
- **Docker Hub**: `chandralegend/nomos-base:latest`

### Using the Base Image

1. Create a Dockerfile using GitHub Packages (recommended):

```dockerfile
FROM ghcr.io/dowhiledev/nomos:latest

# Copy your config file
COPY config.agent.yaml /app/config.agent.yaml

# Copy your tools
COPY tools.py /app/src/tools/
```

Or use Docker Hub:

```dockerfile
FROM chandralegend/nomos-base:latest

# Copy your config file
COPY config.agent.yaml /app/config.agent.yaml

# Copy your tools
COPY tools.py /app/src/tools/
```

2. Build and run your container:

```bash
docker build -t my-nomos-agent .
docker run -e OPENAI_API_KEY=your-api-key-here -p 8000:8000 my-nomos-agent
```

### Available Image Tags

- `latest` - Latest stable release from main branch
- `v1.0.0`, `v1.1.0`, etc. - Specific version tags
- `main` - Latest development build from main branch

### Multi-Architecture Support

The GitHub Packages images support multiple architectures:
- `linux/amd64` (x86_64)
- `linux/arm64` (ARM64, Apple Silicon)

## Environment Variables

The base image supports configuration via environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | Yes (if using OpenAI) |
| `MISTRAL_API_KEY` | Mistral API key | Yes (if using Mistral) |
| `GOOGLE_API_KEY` | Google API key | Yes (if using Gemini) |
| `HUGGINGFACE_API_TOKEN` | HuggingFace token | Yes (if using HuggingFace) |
| `CONFIG_URL` | URL to download agent configuration | No |
| `CONFIG_PATH` | Path to mounted configuration file | No |
| `PORT` | Server port (default: 8000) | No |
| `DATABASE_URL` | PostgreSQL connection URL | No |
| `REDIS_URL` | Redis connection URL | No |
| `ENABLE_TRACING` | Enable OpenTelemetry tracing (`true`/`false`) | No |
| `ELASTIC_APM_SERVER_URL` | Elastic APM server URL | If tracing enabled |
| `ELASTIC_APM_TOKEN` | Elastic APM Token | If tracing enabled |
| `SERVICE_NAME` | Service name for tracing | No (default: `nomos-agent`) |
| `SERVICE_VERSION` | Service version for tracing | No (default: `1.0.0`) |
| `NOMOS_LOG_LEVEL` | Logging level (`DEBUG`, `INFO`, etc.) | No (default: `INFO`) |
| `NOMOS_ENABLE_LOGGING` | Enable logging (`true`/`false`) | No (default: `false`) |
| `KAFKA_BROKERS` | Kafka broker addresses | No |
| `KAFKA_TOPIC` | Kafka topic for events | No (default: `session_events`) |

## Persistent Storage and Session Management

NOMOS supports multiple options for session storage:

### In-Memory Storage

The default storage mechanism is in-memory, which does not persist sessions between container restarts.

### Redis Session Storage

For caching and distributed deployments, you can use Redis as a session store:

```bash
docker run \\
  -e REDIS_URL=redis://redis:6379/0 \\
  -e OPENAI_API_KEY=your-openai-key \\
  -p 8000:8000 my-nomos-agent
```

### PostgreSQL Persistent Storage

For fully persistent sessions that survive container restarts:

```bash
docker run \\
  -e DATABASE_URL=postgresql+asyncpg://user:pass@postgres/dbname \\
  -e OPENAI_API_KEY=your-openai-key \\
  -p 8000:8000 my-nomos-agent
```

## Tracing and Monitoring

### Elastic APM Integration

NOMOS supports distributed tracing using [OpenTelemetry](https://opentelemetry.io/) and can export traces to [Elastic APM](https://www.elastic.co/apm/).

To enable tracing, set the following environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `ENABLE_TRACING` | Enable OpenTelemetry tracing (`true`/`false`) | No (default: `false`) |
| `ELASTIC_APM_SERVER_URL` | Elastic APM server URL | If tracing enabled |
| `ELASTIC_APM_TOKEN` | Elastic APM Token | If tracing enabled |
| `SERVICE_NAME` | Service name for tracing | No (default: `nomos-agent`) |
| `SERVICE_VERSION` | Service version for tracing | No (default: `1.0.0`) |

Example:

```bash
docker run \\
  -e ENABLE_TRACING=true \\
  -e ELASTIC_APM_SERVER_URL=http://your-apm-server:8200 \\
  -e ELASTIC_APM_TOKEN=your-apm-token \\
  -e SERVICE_NAME=my-nomos-agent \\
  -e SERVICE_VERSION=1.0.0 \\
  -e OPENAI_API_KEY=your-openai-key \\
  -p 8000:8000 my-nomos-agent
```

## API Endpoints

NOMOS provides the following REST and WebSocket endpoints:

### Server-side Session Management

- `POST /session` - Create a new session
- `POST /session/{session_id}/message` - Send a message to a session
- `WS /ws/{session_id}` - WebSocket connection for real-time interaction
- `DELETE /session/{session_id}` - End a session
- `GET /session/{session_id}/history` - Get session history

### Client-side Session Management

- `POST /chat` - Stateless chat endpoint where the client maintains session state

## Production Deployment Examples

### Docker Compose

```yaml
version: '3.8'
services:
  nomos-agent:
    image: my-nomos-agent:latest
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - ENABLE_TRACING=true
      - ELASTIC_APM_SERVER_URL=${APM_SERVER_URL}
      - ELASTIC_APM_TOKEN=${APM_TOKEN}
      - KAFKA_BROKERS=kafka:9092
    depends_on:
      - postgres
      - redis
      - kafka

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=nomos
      - POSTGRES_USER=nomos
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  kafka:
    image: bitnami/kafka:latest
    environment:
      - KAFKA_CFG_ZOOKEEPER_CONNECT=zookeeper:2181
      - KAFKA_CFG_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092
    depends_on:
      - zookeeper

  zookeeper:
    image: bitnami/zookeeper:latest
    environment:
      - ALLOW_ANONYMOUS_LOGIN=yes

volumes:
  postgres_data:
  redis_data:
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nomos-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nomos-agent
  template:
    metadata:
      labels:
        app: nomos-agent
    spec:
      containers:
      - name: nomos-agent
        image: my-nomos-agent:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: nomos-secrets
              key: openai-api-key
        - name: DATABASE_URL
          valueFrom:
            configMapKeyRef:
              name: nomos-config
              key: database-url
---
apiVersion: v1
kind: Service
metadata:
  name: nomos-agent-service
spec:
  selector:
    app: nomos-agent
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

## Scaling and Performance

### Horizontal Scaling

NOMOS agents are stateless by default (when using external session storage), making them easy to scale horizontally:

1. Use Redis or PostgreSQL for session storage
2. Deploy multiple agent instances
3. Use a load balancer to distribute requests

### Performance Optimization

1. **Choose the right LLM**: Use smaller, faster models for simple tasks
2. **Configure session storage**: Use Redis for better performance than PostgreSQL
3. **Enable connection pooling**: Configure your database connections appropriately
4. **Monitor performance**: Use Elastic APM or similar tools to track performance

## Security Considerations

1. **API Keys**: Always use environment variables, never hardcode in images
2. **Network Security**: Use HTTPS in production
3. **Database Security**: Ensure your database connections are encrypted
4. **Container Security**: Keep base images updated, scan for vulnerabilities

For more details, see the [base image README](../support/visual-builder/README.md).
