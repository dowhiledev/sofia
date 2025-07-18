#!/usr/bin/env python3
"""
Test script for the new Nomos Client API with JWT Authentication

This script tests the refactored Nomos client using the new API style:
- client.chat.next() for stateless chat
- client.session.init() for session creation
- client.session.next() for session messages
- client.session.get_history() for history
- client.session.end() for ending sessions
"""

import asyncio
from nomos.client import AuthConfig, NomosClient


async def test_new_api():
    """Test the new Nomos client API style"""
    
    # JWT token provided by user
    jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhZGRpdGlvbmFsUHJvcDEiOnt9LCJleHAiOjE3NTI5MjU0OTh9.y-0Pv_O5Ecod9PBCG-Yfm9pBq8wZcc5jLGLN10OY9t4"
    
    # Configure JWT authentication
    auth = AuthConfig(auth_type="jwt", token=jwt_token)
    
    print("🚀 Testing New Nomos Client API")
    print("=" * 50)
    print(f"🔗 Server URL: http://localhost:8000")
    print(f"🔐 Auth Type: JWT")
    print()
    
    async with NomosClient("http://localhost:8000", auth=auth) as client:
        try:
            # Test 1: Health Check
            print("🏥 Test 1: Health Check")
            print("-" * 30)
            health = await client.health_check()
            print(f"✅ Server is healthy: {health}")
            print()
            
            # Test 2: Stateless Chat with client.chat.next()
            print("🔄 Test 2: Stateless Chat (client.chat.next)")
            print("-" * 30)
            
            # First message
            print("👤 You: Hello! Can you introduce yourself?")
            response = await client.chat.next("Hello! Can you introduce yourself?")
            session_data = response.session_data
            print(f"🤖 Agent: {response.response}")
            if response.tool_output:
                print(f"🔧 Tool output: {response.tool_output}")
            print()
            
            # Continue conversation with updated session data
            print("👤 You: What services do you offer?")
            response = await client.chat.next("What services do you offer?", session_data)
            session_data = response.session_data  # Update session state
            print(f"🤖 Agent: {response.response}")
            print()
            
            print(f"💾 Session state ID: {session_data.session_id}")
            print(f"📍 Current step: {session_data.current_step_id}")
            print(f"📚 History length: {len(session_data.history)}")
            print()
            
            # Test 3: Session Management with client.session.*
            print("📝 Test 3: Session Management (client.session.*)")
            print("-" * 30)
            
            # Create session
            print("Creating new session...")
            session = await client.session.init(initiate=True)
            print(f"✅ Session created: {session.session_id}")
            print(f"🤖 Initial message: {session.message}")
            print()
            
            # Send messages
            messages = [
                "What can you help me with?",
                "Tell me about Dragon Ball characters",
                "Thanks for the information!"
            ]
            
            for i, message in enumerate(messages, 1):
                print(f"👤 Message {i}: {message}")
                response = await client.session.next(session.session_id, message)
                print(f"🤖 Response {i}: {response.message}")
                print()
            
            # Get session history
            print("📜 Getting session history...")
            history = await client.session.get_history(session.session_id)
            print(f"📋 History contains {len(history['history'])} messages")
            print()
            
            # End session
            print("🔚 Ending session...")
            result = await client.session.end(session.session_id)
            print(f"✅ {result.get('message', 'Session ended successfully')}")
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
        await test_new_api()
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
