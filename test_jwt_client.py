#!/usr/bin/env python3
"""
Test script for Nomos Client with JWT Authentication

This script tests the Nomos client against a JWT-authenticated server.
"""

import asyncio
from nomos.client import AuthConfig, NomosClient


async def test_jwt_client():
    """Test the Nomos client with JWT authentication"""
    
    # JWT token provided by user
    jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhZGRpdGlvbmFsUHJvcDEiOnt9LCJleHAiOjE3NTI5MjU0OTh9.y-0Pv_O5Ecod9PBCG-Yfm9pBq8wZcc5jLGLN10OY9t4"
    
    # Configure JWT authentication
    auth = AuthConfig(auth_type="jwt", token=jwt_token)
    
    print("🚀 Testing Nomos Client with JWT Authentication")
    print("=" * 60)
    print(f"🔗 Server URL: http://localhost:8000")
    print(f"🔐 Auth Type: JWT")
    print(f"🎫 Token: {jwt_token[:20]}...")
    print()
    
    async with NomosClient("http://localhost:8000", auth=auth) as client:
        try:
            # Test 1: Health Check
            print("🏥 Test 1: Health Check")
            print("-" * 30)
            health = await client.health_check()
            print(f"✅ Server is healthy: {health}")
            print()
            
            # Test 2: Quick Chat
            print("💬 Test 2: Quick Chat")
            print("-" * 30)
            response = await client.quick_chat("Hello! Can you introduce yourself?")
            print(f"🤖 Agent: {response}")
            print()
            
            # Test 3: Session Management
            print("📝 Test 3: Session Management")
            print("-" * 30)
            
            # Create session
            print("Creating new session...")
            session = await client.create_session(initiate=True)
            print(f"✅ Session created: {session.session_id}")
            
            if session.message:
                print(f"🤖 Initial message: {session.message}")
            print()
            
            # Send messages
            messages = [
                "What services do you offer?",
                "How can I get started?",
                "Thank you for the information!"
            ]
            
            for i, message in enumerate(messages, 1):
                print(f"👤 Message {i}: {message}")
                response = await client.send_message(session.session_id, message)
                print(f"🤖 Response {i}: {response.message}")
                print()
            
            # Get session history
            print("📜 Getting session history...")
            history = await client.get_session_history(session.session_id)
            print(f"📋 History contains {len(history.history)} messages")
            print()
            
            # End session
            print("🔚 Ending session...")
            result = await client.end_session(session.session_id)
            print(f"✅ {result.get('message', 'Session ended successfully')}")
            print()
            
            # Test 4: Stateless Chat
            print("🔄 Test 4: Stateless Chat")
            print("-" * 30)
            
            # Start conversation
            chat_response = await client.start_conversation()
            session_data = chat_response.session_data
            
            print(f"🤖 Initial response: {chat_response.response}")
            if chat_response.tool_output:
                print(f"🔧 Tool output: {chat_response.tool_output}")
            print()
            
            # Continue conversation
            stateless_messages = [
                "I'm looking for assistance with a project",
                "Can you help me understand your capabilities?",
            ]
            
            for message in stateless_messages:
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
            print()
            
            print("🎉 All tests completed successfully!")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            print(f"Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()


async def main():
    """Main function"""
    try:
        await test_jwt_client()
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
