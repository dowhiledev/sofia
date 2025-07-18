# Nomos Client

A Python client library for connecting to Nomos Agent API servers with full typing support, authentication handling, and both synchronous and asynchronous interfaces.

## Features

- 🔐 **Multiple Authentication Methods**: JWT, API Key, or no authentication
- 📡 **Async/Sync Support**: Both asyncio and synchronous interfaces
- 🎯 **Full Type Safety**: Complete typing with Pydantic models
- 🏗️ **Session Management**: Stateful session handling on the server
- 🔄 **Stateless Chat**: Client-side session state management
- ⚡ **Error Handling**: Comprehensive error handling with specific exceptions
- 🛠️ **Convenience Methods**: Simple interfaces for common operations

## Quick Start

### Basic Usage

```python
from nomos import NomosClient

# Simple async chat
async with NomosClient("http://localhost:8000") as client:
    response = await client.quick_chat("Hello!")
    print(response)
```

### Authentication

```python
from nomos import NomosClient, AuthConfig

# JWT Authentication
auth = AuthConfig(auth_type="jwt", token="your-jwt-token")
client = NomosClient("http://localhost:8000", auth=auth)

# API Key Authentication  
auth = AuthConfig(auth_type="api_key", token="your-api-key")
client = NomosClient("http://localhost:8000", auth=auth)
```

### Session Management

```python
async with NomosClient("http://localhost:8000") as client:
    # Create session with initial message
    session = await client.create_session(initiate=True)
    print(f"Session ID: {session.session_id}")
    
    # Send messages
    response = await client.send_message(session.session_id, "Hello!")
    print(response.message)
    
    # Get conversation history
    history = await client.get_session_history(session.session_id)
    print(f"Messages: {len(history.history)}")
    
    # End session
    await client.end_session(session.session_id)
```

### Stateless Chat

```python
async with NomosClient("http://localhost:8000") as client:
    # Start conversation
    chat_response = await client.start_conversation()
    session_data = chat_response.session_data
    
    # Continue conversation
    chat_response = await client.continue_conversation(
        "Hello there!", 
        session_data
    )
    session_data = chat_response.session_data  # Update state
    
    print(chat_response.response)
```

### Synchronous Client

```python
from nomos import NomosClientSync

with NomosClientSync("http://localhost:8000") as client:
    response = client.quick_chat("Hello!")
    print(response)
```

## API Reference

### NomosClient

The main asynchronous client class.

#### Methods

- `health_check()` - Check server health
- `create_session(initiate=False)` - Create new session
- `send_message(session_id, message)` - Send message to session
- `get_session_history(session_id)` - Get session history
- `end_session(session_id)` - End session
- `chat(user_input, session_data, verbose)` - Stateless chat
- `quick_chat(message)` - Simple one-off chat
- `start_conversation()` - Initialize stateless conversation
- `continue_conversation(message, session_data)` - Continue conversation

### NomosClientSync

Synchronous version with the same methods (without `await`).

### Models

#### AuthConfig
```python
AuthConfig(
    auth_type="none|jwt|api_key",
    token="your-token"
)
```

#### SessionResponse
```python
SessionResponse(
    session_id=str,
    message=dict
)
```

#### ChatResponse
```python
ChatResponse(
    response=dict,
    tool_output=Optional[str],
    session_data=State
)
```

### Exceptions

- `NomosClientError` - Base client exception
- `AuthenticationError` - Authentication failures
- `APIError` - API response errors (includes status_code)

## Examples

See `examples/client_examples.py` for comprehensive examples including:

- Health checks
- Different authentication methods
- Session management
- Stateless chat
- Error handling
- Interactive chat sessions

Run examples:
```bash
python examples/client_examples.py
python examples/client_examples.py --interactive
```

## Configuration

### Environment Variables

- `NOMOS_JWT_TOKEN` - JWT token for examples
- `NOMOS_API_KEY` - API key for examples

### Custom Headers

```python
headers = {
    "X-Client-Version": "1.0.0",
    "X-Custom-Header": "value"
}

client = NomosClient(
    "http://localhost:8000",
    headers=headers
)
```

### Timeout Configuration

```python
client = NomosClient(
    "http://localhost:8000",
    timeout=60.0  # 60 seconds
)
```

## Error Handling

```python
from nomos.client import APIError, AuthenticationError, NomosClientError

try:
    async with NomosClient("http://localhost:8000") as client:
        response = await client.quick_chat("Hello!")
except AuthenticationError as e:
    print(f"Auth failed: {e}")
except APIError as e:
    print(f"API error {e.status_code}: {e}")
except NomosClientError as e:
    print(f"Client error: {e}")
```

## Integration with Existing Nomos Types

The client uses the same `State` model as the core Nomos library for complete compatibility:

```python
from nomos.models.agent import State

# State objects are fully compatible between client and server
state = State(
    session_id="example",
    current_step_id="start", 
    history=[],
    flow_state=None
)

response = await client.chat(session_data=state)
updated_state = response.session_data
```

## Testing

Run the client tests:
```bash
python -m pytest tests/test_client.py -v
```
