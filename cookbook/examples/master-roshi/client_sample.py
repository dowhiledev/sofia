import asyncio
import os
from nomos.client import AuthConfig, NomosClient


async def test_client():
    jwt_token = os.getenv("NOMOS_JWT_TOKEN")
    auth = AuthConfig(auth_type="jwt", token=jwt_token)


    async with NomosClient("http://localhost:8000", auth=auth) as client:
        # Health Check
        health = await client.health_check()
        print(f"Server is healthy: {health}")

        # Stateless Chat with client.chat.next()
        # First message
        response = await client.chat.next("Hello! Can you introduce yourself?")
        session_data = response.session_data
        print(response)

        # Continue conversation with updated session data
        response = await client.chat.next("Where is Goku from?", session_data)
        session_data = response.session_data  # Update session state
        print(response)

        # Create a session
        session = await client.session.init(initiate=True)

        # Send messages
        messages = [
            "What can you help me with?",
            "Tell me about Dragon Ball characters",
            "Thanks for the information!"
        ]
        for _, message in enumerate(messages, 1):
            response = await client.session.next(session.session_id, message)
            print(response)

        # Get session history
        history = await client.session.get_history(session.session_id)
        print(history)

        # End session
        result = await client.session.end(session.session_id)
        print(result)


async def main():
    await test_client()

if __name__ == "__main__":
    asyncio.run(main())
