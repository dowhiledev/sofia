#!/usr/bin/env python3
"""
JWT Client Demo - Production-ready example of using Nomos Client with JWT auth

This demonstrates the key features of the Nomos client with JWT authentication:
- Health checks
- Quick chat (stateless single messages)
- Session management (server-side state)
- Stateless chat (client-side state management)
"""

import asyncio
from nomos.client import AuthConfig, NomosClient


async def main():
    """Main demo function"""
    
    # Your JWT token
    jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhZGRpdGlvbmFsUHJvcDEiOnt9LCJleHAiOjE3NTI5MjU0OTh9.y-0Pv_O5Ecod9PBCG-Yfm9pBq8wZcc5jLGLN10OY9t4"
    
    # Configure JWT authentication
    auth = AuthConfig(auth_type="jwt", token=jwt_token)
    
    print("🚀 Nomos Client JWT Demo")
    print("=" * 40)
    
    async with NomosClient("http://localhost:8000", auth=auth) as client:
        # 1. Health Check
        print("🏥 Health Check:")
        health = await client.health_check()
        print(f"   Status: {health['status']}")
        print()
        
        # 2. Quick Chat (one-off messages)
        print("💬 Quick Chat:")
        response = await client.quick_chat("Hi! Tell me about yourself.")
        print(f"   Agent: {response}")
        print()
        
        # 3. Session Management (server handles state)
        print("📝 Session Management:")
        session = await client.create_session(initiate=True)
        print(f"   Session ID: {session.session_id}")
        
        # Send a few messages
        msg_response = await client.send_message(session.session_id, "What can you help me with?")
        print(f"   Agent: {msg_response.message}")
        
        # End session
        await client.end_session(session.session_id)
        print("   ✅ Session ended")
        print()
        
        # 4. Stateless Chat (client manages state)
        print("🔄 Stateless Chat:")
        chat_response = await client.start_conversation()
        session_data = chat_response.session_data
        print(f"   Agent: {chat_response.response}")
        
        # Continue conversation
        chat_response = await client.continue_conversation(
            "Can you help me with Dragon Ball character information?", 
            session_data
        )
        session_data = chat_response.session_data  # Update state
        print(f"   Agent: {chat_response.response}")
        print()
        
        print("✅ Demo completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Demo interrupted")
    except Exception as e:
        print(f"❌ Demo failed: {e}")
