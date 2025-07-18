# Nomos TypeScript/JavaScript SDK

[![npm version](https://badge.fury.io/js/nomos-sdk.svg)](https://www.npmjs.com/package/nomos-## 📖 Features

- **Full TypeScript Support** - Complete type safety and IntelliSense
- **Authentication Support** - JWT and API key authentication
- **Session Management** - Create, manage, and clean up conversation sessions
- **Direct Chat API** - Stateless chat interactions
- **Error Handling** - Comprehensive error handling and recovery
- **Rate Limiting Support** - Handles rate limit responses gracefully
- **Node.js & Browser** - Works in both environments
- **Zero Dependencies** - Minimal footprint with only essential dependencies

## 🔧 Error Handling

The SDK includes comprehensive error handling with specific error types for authentication issues:

```typescript
import { NomosClient, NomosAuthError } from 'nomos-sdk';

const client = new NomosClient({
  baseUrl: 'https://your-nomos-server.com',
  auth: { type: 'jwt', token: 'your-token' }
});

try {
  const session = await client.createSession();
} catch (error) {
  if (error instanceof NomosAuthError) {
    switch (error.status) {
      case 401:
        console.error('Authentication failed - check your token');
        break;
      case 403:
        console.error('Access forbidden - insufficient permissions');
        break;
      case 429:
        console.error('Rate limit exceeded - slow down requests');
        break;
    }
  } else {
    console.error('Other error:', error.message);
  }
}
```

## 🔐 Security Best Practices

1. **Never expose tokens in client-side code**
2. **Use environment variables for tokens**
3. **Implement token refresh logic for long-running applications**
4. **Disable token generation endpoint in production**

```typescript
// Good: Use environment variables
const client = new NomosClient({
  baseUrl: process.env.NOMOS_API_URL,
  auth: {
    type: 'jwt',
    token: process.env.NOMOS_JWT_TOKEN
  }
});
```](https://github.com/dowhiledev/nomos/workflows/CI%20-%20TypeScript%20SDK/badge.svg)](https://github.com/dowhiledev/nomos/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A powerful TypeScript/JavaScript SDK for interacting with Nomos agents. Build conversational AI applications with ease, now with full authentication support.

## 🚀 Quick Start

### Installation

```bash
npm install nomos-sdk
```

> **Note:** This package is published as an ES module. For CommonJS projects, use dynamic imports:
> ```javascript
> // ES Module (recommended)
> import { NomosClient } from 'nomos-sdk';
>
> // CommonJS (use dynamic import)
> const { NomosClient } = await import('nomos-sdk');
> ```

### Basic Usage (No Authentication)

```typescript
import { NomosClient } from 'nomos-sdk';

// Create a client
const client = new NomosClient('http://localhost:8000');

// Start a conversation
const session = await client.createSession(true);
console.log('Agent:', session.message);

// Send messages
const response = await client.sendMessage(session.session_id, 'Hello!');
console.log('Response:', response.message);

// End session
await client.endSession(session.session_id);
```

### Authenticated Usage

```typescript
import { NomosClient } from 'nomos-sdk';

// Initialize with authentication
const client = new NomosClient({
  baseUrl: 'http://localhost:8000',
  auth: {
    type: 'jwt', // or 'api_key'
    token: 'your-jwt-token-or-api-key'
  }
});

// Or set authentication later
const client2 = new NomosClient('http://localhost:8000');
client2.setAuth({
  type: 'jwt',
  token: 'your-jwt-token'
});

// Use normally - authentication headers are added automatically
const session = await client.createSession(true);
```

## � Authentication

The SDK supports two authentication methods:

### JWT Authentication

```typescript
const client = new NomosClient({
  baseUrl: 'https://your-nomos-server.com',
  auth: {
    type: 'jwt',
    token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
  }
});
```

### API Key Authentication

```typescript
const client = new NomosClient({
  baseUrl: 'https://your-nomos-server.com',
  auth: {
    type: 'api_key',
    token: 'your-api-key-here'
  }
});
```

### Development Token Generation

For development and testing environments, you can generate JWT tokens directly:

```typescript
// Note: This endpoint should be disabled in production
const tokenResponse = await client.generateToken({
  user_id: 'test-user',
  role: 'user'
});

// Use the generated token
client.setAuth({
  type: 'jwt',
  token: tokenResponse.access_token
});
```

### Managing Authentication

```typescript
// Set authentication
client.setAuth({ type: 'jwt', token: 'your-token' });

// Clear authentication
client.clearAuth();

// Authentication is automatically included in all requests
```

## �📖 Features

- **Full TypeScript Support** - Complete type safety and IntelliSense
- **Authentication Support** - JWT and API key authentication
- **Session Management** - Create, manage, and clean up conversation sessions
- **Direct Chat API** - Stateless chat interactions
- **Error Handling** - Comprehensive error handling and recovery
- **Rate Limiting Support** - Handles rate limit responses gracefully
- **Node.js & Browser** - Works in both environments
- **Zero Dependencies** - Minimal footprint with only essential dependencies

## 🔧 Usage Examples

### Stateless Chat

```typescript
import { NomosClient } from 'nomos-sdk';

const client = new NomosClient('http://localhost:8000');
const { response, session_data } = await client.chat({ user_input: 'Hello' });
console.log(response); // agent reply

// Use the returned session_data to continue the conversation

const followUp = await client.chat({
  user_input: 'Tell me more',
  session_data,
});
console.log(followUp.response);
```

### Stateful Sessions

```typescript
import { NomosClient } from 'nomos-sdk';

const client = new NomosClient();
const { session_id } = await client.createSession(true);
await client.sendMessage(session_id, 'How are you?');
const history = await client.getSessionHistory(session_id);
await client.endSession(session_id);
```

## 📝 Complete Examples

Check out the [complete examples](https://github.com/dowhiledev/nomos/tree/main/examples/typescript-sdk-example) including:

- **Basic Usage** - Simple request/response examples
- **Advanced Patterns** - Production-ready patterns
- **Interactive Chat** - CLI chat interface
- **Error Handling** - Comprehensive error recovery
- **Multi-session Management** - Handle multiple conversations

## 🏗️ Development

### Building from Source

```bash
git clone https://github.com/dowhiledev/nomos.git
cd nomos/sdk/ts
npm install
npm run build
```

### Running Tests

```bash
npm test
```

### Linting

```bash
npm run lint
```

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](https://github.com/dowhiledev/nomos/blob/main/CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License.

## 🔗 Links

- [Documentation](https://github.com/dowhiledev/nomos)
- [Examples](https://github.com/dowhiledev/nomos/tree/main/examples/typescript-sdk-example)
- [Issues](https://github.com/dowhiledev/nomos/issues)
- [npm Package](https://www.npmjs.com/package/nomos-sdk)
