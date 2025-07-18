#!/usr/bin/env node

/**
 * Simple Chat Example with Authentication
 *
 * This example shows how to set up a basic authenticated chat session
 * with a Nomos agent.
 */

import { NomosClient, NomosAuthError } from '../src/index.js';
import { createInterface } from 'readline';

const rl = createInterface({
  input: process.stdin,
  output: process.stdout
});

function question(prompt: string): Promise<string> {
  return new Promise(resolve => rl.question(prompt, resolve));
}

async function main() {
  console.log('🤖 Nomos SDK - Simple Authenticated Chat Example\n');

  // Get configuration from user or environment
  const baseUrl = process.env.NOMOS_API_URL || await question('Enter Nomos server URL (or press Enter for localhost:8000): ') || 'http://localhost:8000';

  const client = new NomosClient(baseUrl);

  // Check if server is available
  try {
    const health = await client.healthCheck();
    console.log(`✅ Server is ${health.status}\n`);
  } catch (error) {
    console.error('❌ Server is not available:', error.message);
    process.exit(1);
  }

  // Set up authentication if needed
  const authChoice = await question('Use authentication? (jwt/api_key/none): ');

  if (authChoice === 'jwt' || authChoice === 'api_key') {
    const token = process.env.NOMOS_TOKEN || await question(`Enter your ${authChoice.toUpperCase()} token: `);

    if (!token) {
      console.log('❌ No token provided, exiting...');
      process.exit(1);
    }

    client.setAuth({
      type: authChoice as 'jwt' | 'api_key',
      token: token.trim()
    });

    console.log(`✅ Authentication configured with ${authChoice.toUpperCase()}\n`);
  }

  // Start chat session
  let sessionId: string;

  try {
    const session = await client.createSession(true);
    sessionId = session.session_id;
    console.log('🚀 Chat session started!');
    console.log('Agent:', JSON.stringify(session.message, null, 2));
  } catch (error) {
    if (error instanceof NomosAuthError) {
      console.error(`❌ Authentication failed: ${error.message}`);
      process.exit(1);
    } else {
      console.error(`❌ Failed to start session: ${error.message}`);
      process.exit(1);
    }
  }

  console.log('\n💬 Type your messages (type "exit" to quit, "history" to see conversation history):\n');

  // Chat loop
  let shouldContinue = true;
  while (shouldContinue) {
    try {
      const userInput = await question('You: ');

      if (userInput.toLowerCase() === 'exit') {
        shouldContinue = false;
        break;
      }

      if (userInput.toLowerCase() === 'history') {
        const history = await client.getSessionHistory(sessionId);
        console.log('\n📚 Conversation History:');
        history.history.forEach((entry, index) => {
          console.log(`${index + 1}. ${JSON.stringify(entry, null, 2)}`);
        });
        console.log('');
        continue;
      }

      if (userInput.trim() === '') {
        continue;
      }

      const response = await client.sendMessage(sessionId, userInput);
      console.log('Agent:', JSON.stringify(response.message, null, 2));

    } catch (error) {
      if (error instanceof NomosAuthError) {
        console.error(`❌ Authentication error: ${error.message}`);
        if (error.status === 401) {
          console.error('Your token may have expired. Please restart with a new token.');
          shouldContinue = false;
          break;
        }
      } else {
        console.error(`❌ Error: ${error.message}`);
      }
    }
  }

  // Clean up
  try {
    await client.endSession(sessionId);
    console.log('\n✅ Session ended successfully. Goodbye!');
  } catch (error) {
    console.log('\n⚠️  Session cleanup failed, but that\'s okay.');
  }

  rl.close();
}

main().catch(error => {
  console.error('💥 Unexpected error:', error);
  rl.close();
  process.exit(1);
});
