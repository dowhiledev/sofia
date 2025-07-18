#!/usr/bin/env node

/**
 * Authentication Examples for Nomos TypeScript SDK
 *
 * This file demonstrates various authentication patterns
 * including JWT and API key authentication.
 */

import { NomosClient, NomosAuthError } from '../src/index.js';

// Configuration
const BASE_URL = process.env.NOMOS_API_URL || 'http://localhost:8000';
const JWT_TOKEN = process.env.NOMOS_JWT_TOKEN;
const API_KEY = process.env.NOMOS_API_KEY;

async function main() {
  console.log('🔐 Nomos SDK Authentication Examples\n');

  // Example 1: Basic health check (no auth required)
  await healthCheckExample();

  // Example 2: JWT Authentication
  if (JWT_TOKEN) {
    await jwtAuthExample();
  } else {
    console.log('⚠️  Skipping JWT example - NOMOS_JWT_TOKEN not set');
  }

  // Example 3: API Key Authentication
  if (API_KEY) {
    await apiKeyAuthExample();
  } else {
    console.log('⚠️  Skipping API Key example - NOMOS_API_KEY not set');
  }

  // Example 4: Development Token Generation
  await tokenGenerationExample();

  // Example 5: Error Handling
  await errorHandlingExample();

  // Example 6: Dynamic Authentication
  await dynamicAuthExample();

  // Example 7: Verbose Chat (if authentication works)
  if (JWT_TOKEN) {
    const client = new NomosClient({
      baseUrl: BASE_URL,
      auth: { type: 'jwt', token: JWT_TOKEN }
    });
    await verboseChatExample(client);
  }
}

async function healthCheckExample() {
  console.log('📊 Health Check Example (No Auth Required)');

  const client = new NomosClient(BASE_URL);

  try {
    const health = await client.healthCheck();
    console.log('✅ Server Status:', health.status);
    console.log('⏰ Timestamp:', new Date(health.timestamp * 1000).toISOString());
  } catch (error) {
    console.error('❌ Health check failed:', error.message);
  }

  console.log('');
}

async function jwtAuthExample() {
  console.log('🔑 JWT Authentication Example');

  // Method 1: Initialize with auth config
  const client = new NomosClient({
    baseUrl: BASE_URL,
    auth: {
      type: 'jwt',
      token: JWT_TOKEN!
    }
  });

  try {
    const session = await client.createSession(true);
    console.log('✅ Session created with JWT auth:', session.session_id);

    await client.sendMessage(session.session_id, 'Hello with JWT!');
    console.log('✅ Message sent successfully');

    await client.endSession(session.session_id);
    console.log('✅ Session ended');
  } catch (error) {
    if (error instanceof NomosAuthError) {
      console.error('❌ Auth Error:', error.message, `(${error.status})`);
    } else {
      console.error('❌ Error:', error.message);
    }
  }

  console.log('');
}

async function apiKeyAuthExample() {
  console.log('🗝️  API Key Authentication Example');

  const client = new NomosClient(BASE_URL);

  // Method 2: Set auth after initialization
  client.setAuth({
    type: 'api_key',
    token: API_KEY!
  });

  try {
    const session = await client.createSession(true);
    console.log('✅ Session created with API key:', session.session_id);

    const history = await client.getSessionHistory(session.session_id);
    console.log('✅ Retrieved session history, entries:', history.history.length);

    await client.endSession(session.session_id);
    console.log('✅ Session ended');
  } catch (error) {
    if (error instanceof NomosAuthError) {
      console.error('❌ Auth Error:', error.message, `(${error.status})`);
    } else {
      console.error('❌ Error:', error.message);
    }
  }

  console.log('');
}

async function tokenGenerationExample() {
  console.log('🏭 Token Generation Example (Development Only)');

  const client = new NomosClient(BASE_URL);

  try {
    // Generate a JWT token for testing
    const tokenResponse = await client.generateToken({
      user_id: 'test-user',
      role: 'user',
      permissions: ['chat', 'session']
    });

    console.log('✅ Generated token:', tokenResponse.access_token.substring(0, 20) + '...');
    console.log('✅ Token type:', tokenResponse.token_type);

    // Use the generated token
    client.setAuth({
      type: 'jwt',
      token: tokenResponse.access_token
    });

    const session = await client.createSession(true);
    console.log('✅ Session created with generated token:', session.session_id);

    await client.endSession(session.session_id);
    console.log('✅ Session ended');

  } catch (error) {
    if (error.message.includes('404')) {
      console.log('⚠️  Token generation endpoint not available (likely disabled in production)');
    } else {
      console.error('❌ Token generation failed:', error.message);
    }
  }

  console.log('');
}

async function errorHandlingExample() {
  console.log('🚨 Error Handling Example');

  // Test with invalid token
  const client = new NomosClient({
    baseUrl: BASE_URL,
    auth: {
      type: 'jwt',
      token: 'invalid-token'
    }
  });

  try {
    await client.createSession();
    console.log('⚠️  Unexpected success with invalid token');
  } catch (error) {
    if (error instanceof NomosAuthError) {
      console.log('✅ Correctly caught auth error:', error.message);
      console.log('✅ Status code:', error.status);
    } else {
      console.log('✅ Caught general error:', error.message);
    }
  }

  console.log('');
}

async function dynamicAuthExample() {
  console.log('🔄 Dynamic Authentication Example');

  const client = new NomosClient(BASE_URL);

  // Start without authentication
  try {
    await client.createSession();
    console.log('✅ Created session without auth (server allows this)');
  } catch (error) {
    console.log('⚠️  Server requires authentication');
  }

  // Add authentication dynamically
  if (JWT_TOKEN) {
    console.log('🔐 Adding JWT authentication...');
    client.setAuth({
      type: 'jwt',
      token: JWT_TOKEN
    });

    try {
      const session = await client.createSession();
      console.log('✅ Session created after adding auth:', session.session_id);
      await client.endSession(session.session_id);
    } catch (error) {
      console.error('❌ Still failed after adding auth:', error.message);
    }
  }

  // Clear authentication
  console.log('🔓 Clearing authentication...');
  client.clearAuth();

  try {
    await client.createSession();
    console.log('✅ Created session without auth after clearing');
  } catch (error) {
    console.log('⚠️  Failed without auth after clearing (expected if auth required)');
  }

  console.log('');
}

// Helper function to demonstrate chat with verbose mode
async function verboseChatExample(client: NomosClient) {
  console.log('💬 Verbose Chat Example');

  try {
    const response = await client.chat({
      user_input: 'What is the weather like today?'
    }, true); // verbose = true

    console.log('✅ Chat response received');
    console.log('🔧 Tool output:', response.tool_output || 'None');
    console.log('📊 Session ID:', response.session_data.session_id);
  } catch (error) {
    console.error('❌ Chat failed:', error.message);
  }

  console.log('');
}

// Run the examples
main().catch(console.error);
