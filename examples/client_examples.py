#!/usr/bin/env python3
"""
Nomos Client Examples

This script demonstrates various usage patterns for the Nomos client library,
including different authentication methods, session management, and stateless chat.
"""

import asyncio
import os
from typing import Optional

from nomos.client import AuthConfig, NomosClient, NomosClientSync


async def example_health_check():
    """Example: Health check"""
    print("🏥 Health Check Example")
    print("=" * 50)
    
    async with NomosClient("http://localhost:8000") as client:
        try:
            health = await client.health_check()
            print(f"✅ Server is healthy: {health}")
        except Exception as e:
            print(f"❌ Health check failed: {e}")
    print()


async def example_no_auth_chat():
    """Example: Simple chat without authentication"""
    print("💬 No Authentication Chat Example")
    print("=" * 50)
    
    async with NomosClient("http://localhost:8000") as client:
        try:
            # Quick chat
            response = await client.quick_chat("Hello! How are you?")
            print(f"🤖 Agent: {response}")
            
            # Another quick message
            response = await client.quick_chat("What can you help me with?")
            print(f"🤖 Agent: {response}")
            
        except Exception as e:
            print(f"❌ Chat failed: {e}")
    print()


async def example_jwt_auth_chat():
    """Example: Chat with JWT authentication"""
    print("🔐 JWT Authentication Chat Example")
    print("=" * 50)
    
    # You would get this token from your authentication service
    jwt_token = os.getenv("NOMOS_JWT_TOKEN")
    
    if not jwt_token:
        print("⚠️  No JWT token found in NOMOS_JWT_TOKEN environment variable")
        print("   Skipping JWT example...")
        print()
        return
    
    auth = AuthConfig(auth_type="jwt", token=jwt_token)
    
    async with NomosClient("http://localhost:8000", auth=auth) as client:
        try:
            response = await client.quick_chat("Hello with JWT auth!")
            print(f"🤖 Agent: {response}")
        except Exception as e:
            print(f"❌ JWT chat failed: {e}")
    print()


async def example_api_key_auth():
    """Example: Chat with API key authentication"""
    print("🔑 API Key Authentication Example")
    print("=" * 50)
    
    api_key = os.getenv("NOMOS_API_KEY")
    
    if not api_key:
        print("⚠️  No API key found in NOMOS_API_KEY environment variable")
        print("   Skipping API key example...")
        print()
        return
    
    auth = AuthConfig(auth_type="api_key", token=api_key)
    
    async with NomosClient("http://localhost:8000", auth=auth) as client:
        try:
            response = await client.quick_chat("Hello with API key auth!")
            print(f"🤖 Agent: {response}")
        except Exception as e:
            print(f"❌ API key chat failed: {e}")
    print()


async def example_session_management():
    """Example: Session-based conversation"""
    print("📝 Session Management Example")
    print("=" * 50)
    
    async with NomosClient("http://localhost:8000") as client:
        try:
            # Create a new session with initial message
            print("🚀 Creating new session...")
            session = await client.create_session(initiate=True)
            print(f"✅ Session created: {session.session_id}")
            
            if session.message:
                print(f"🤖 Initial message: {session.message}")
            
            # Send messages in the session
            messages = [
                "I'd like to order a coffee",
                "Can you tell me about your menu?",
                "I'll take a large latte, please",
            ]
            
            for message in messages:
                print(f"👤 You: {message}")
                response = await client.send_message(session.session_id, message)
                print(f"🤖 Agent: {response.message}")
                print()
            
            # Get conversation history
            print("📜 Getting conversation history...")
            history = await client.get_session_history(session.session_id)
            print(f"📋 History contains {len(history.history)} messages")
            
            # End the session
            print("🔚 Ending session...")
            result = await client.end_session(session.session_id)
            print(f"✅ {result.get('message', 'Session ended')}")
            
        except Exception as e:
            print(f"❌ Session management failed: {e}")
    print()


async def example_stateless_chat():
    """Example: Stateless chat with client-side session management"""
    print("🔄 Stateless Chat Example")
    print("=" * 50)
    
    async with NomosClient("http://localhost:8000") as client:
        try:
            # Start a conversation
            print("🚀 Starting conversation...")
            chat_response = await client.start_conversation()
            session_data = chat_response.session_data
            
            print(f"🤖 Initial response: {chat_response.response}")
            if chat_response.tool_output:
                print(f"🔧 Tool output: {chat_response.tool_output}")
            print()
            
            # Continue the conversation
            messages = [
                "Hello! I'm interested in your services.",
                "Can you help me understand what you offer?",
                "That sounds great! How do I get started?",
            ]
            
            for message in messages:
                print(f"👤 You: {message}")
                chat_response = await client.continue_conversation(message, session_data)
                session_data = chat_response.session_data  # Update session state
                
                print(f"🤖 Agent: {chat_response.response}")
                if chat_response.tool_output:
                    print(f"🔧 Tool output: {chat_response.tool_output}")
                print()
            
            print(f"💾 Final session state ID: {session_data.session_id}")
            print(f"📍 Current step: {session_data.current_step_id}")
            print(f"📚 History length: {len(session_data.history)}")
            
        except Exception as e:
            print(f"❌ Stateless chat failed: {e}")
    print()


def example_sync_client():
    """Example: Using the synchronous client"""
    print("⚡ Synchronous Client Example")
    print("=" * 50)
    
    with NomosClientSync("http://localhost:8000") as client:
        try:
            # Health check
            health = client.health_check()
            print(f"✅ Server health: {health}")
            
            # Quick chat
            response = client.quick_chat("Hello from sync client!")
            print(f"🤖 Agent: {response}")
            
            # Session example
            session = client.create_session()
            print(f"📝 Created session: {session.session_id}")
            
            response = client.send_message(session.session_id, "Test message")
            print(f"🤖 Response: {response.message}")
            
            client.end_session(session.session_id)
            print("✅ Session ended")
            
        except Exception as e:
            print(f"❌ Sync client failed: {e}")
    print()


async def example_error_handling():
    """Example: Error handling patterns"""
    print("⚠️  Error Handling Example")
    print("=" * 50)
    
    from nomos.client import APIError, AuthenticationError, NomosClientError
    
    # Test with invalid URL
    try:
        async with NomosClient("http://invalid-server:9999") as client:
            await client.health_check()
    except NomosClientError as e:
        print(f"✅ Caught connection error: {type(e).__name__}: {e}")
    
    # Test with invalid session
    try:
        async with NomosClient("http://localhost:8000") as client:
            await client.send_message("invalid-session-id", "test")
    except APIError as e:
        print(f"✅ Caught API error: {type(e).__name__}: {e} (Status: {e.status_code})")
    
    # Test with invalid auth
    try:
        auth = AuthConfig(auth_type="jwt", token="invalid-token")
        async with NomosClient("http://localhost:8000", auth=auth) as client:
            await client.quick_chat("test")
    except AuthenticationError as e:
        print(f"✅ Caught auth error: {type(e).__name__}: {e}")
    except Exception as e:
        print(f"⚠️  Other error (server might not have auth enabled): {e}")
    
    print()


async def example_custom_headers():
    """Example: Using custom headers"""
    print("📤 Custom Headers Example")
    print("=" * 50)
    
    custom_headers = {
        "X-Client-Version": "1.0.0",
        "X-User-Agent": "Nomos-Python-Client",
    }
    
    async with NomosClient(
        "http://localhost:8000",
        headers=custom_headers
    ) as client:
        try:
            response = await client.quick_chat("Hello with custom headers!")
            print(f"🤖 Agent: {response}")
        except Exception as e:
            print(f"❌ Custom headers example failed: {e}")
    print()


async def interactive_chat_example():
    """Example: Interactive chat session"""
    print("🗣️  Interactive Chat Example")
    print("=" * 50)
    print("Type 'quit' to exit, 'session' to try session mode, or 'stateless' for stateless mode")
    print()
    
    mode = input("Choose mode (session/stateless): ").strip().lower()
    
    if mode == "session":
        await interactive_session_chat()
    elif mode == "stateless":
        await interactive_stateless_chat()
    else:
        print("Invalid mode selected.")


async def interactive_session_chat():
    """Interactive session-based chat"""
    async with NomosClient("http://localhost:8000") as client:
        try:
            session = await client.create_session(initiate=True)
            print(f"📝 Session created: {session.session_id}")
            
            if session.message:
                print(f"🤖 Agent: {session.message}")
            
            while True:
                user_input = input("\n👤 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    break
                
                if not user_input:
                    continue
                
                try:
                    response = await client.send_message(session.session_id, user_input)
                    print(f"🤖 Agent: {response.message}")
                except Exception as e:
                    print(f"❌ Error: {e}")
            
            await client.end_session(session.session_id)
            print("👋 Session ended!")
            
        except Exception as e:
            print(f"❌ Interactive session failed: {e}")


async def interactive_stateless_chat():
    """Interactive stateless chat"""
    async with NomosClient("http://localhost:8000") as client:
        try:
            # Start conversation
            chat_response = await client.start_conversation()
            session_data = chat_response.session_data
            
            print(f"🤖 Agent: {chat_response.response}")
            
            while True:
                user_input = input("\n👤 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    break
                
                if not user_input:
                    continue
                
                try:
                    chat_response = await client.continue_conversation(user_input, session_data)
                    session_data = chat_response.session_data
                    print(f"🤖 Agent: {chat_response.response}")
                except Exception as e:
                    print(f"❌ Error: {e}")
            
            print("👋 Chat ended!")
            
        except Exception as e:
            print(f"❌ Interactive stateless chat failed: {e}")


async def main():
    """Run all examples"""
    print("🚀 Nomos Client Examples")
    print("=" * 70)
    print()
    
    # Check if we want to run interactive mode
    if len(os.sys.argv) > 1 and os.sys.argv[1] == "--interactive":
        await interactive_chat_example()
        return
    
    # Run all automated examples
    examples = [
        example_health_check,
        example_no_auth_chat,
        example_jwt_auth_chat,
        example_api_key_auth,
        example_session_management,
        example_stateless_chat,
        example_sync_client,
        example_error_handling,
        example_custom_headers,
    ]
    
    for example_func in examples:
        try:
            if asyncio.iscoroutinefunction(example_func):
                await example_func()
            else:
                example_func()
        except KeyboardInterrupt:
            print("\n👋 Examples interrupted by user")
            break
        except Exception as e:
            print(f"❌ Example {example_func.__name__} failed: {e}")
            print()
    
    print("🎉 All examples completed!")
    print()
    print("💡 Tips:")
    print("  - Run with --interactive for interactive chat")
    print("  - Set NOMOS_JWT_TOKEN for JWT auth examples")
    print("  - Set NOMOS_API_KEY for API key auth examples")
    print("  - Make sure your Nomos server is running on http://localhost:8000")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
