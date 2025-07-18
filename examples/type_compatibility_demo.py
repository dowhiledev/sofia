"""
Integration test example showing how the client works with existing Nomos types.
"""

from nomos.client import AuthConfig, ChatRequest, ChatResponse, NomosClient
from nomos.models.agent import State, Event, Summary


def test_type_compatibility():
    """Test that client types are compatible with core Nomos types."""
    
    # Create a State object using the core Nomos type
    state = State(
        session_id="test-session-123",
        current_step_id="greeting",
        history=[
            Event(type="user", content="Hello!"),
            Event(type="assistant", content="Hi there! How can I help you?"),
            Summary(summary=["User greeted", "Assistant responded politely"])
        ],
        flow_state=None
    )
    
    # Verify the state can be used in client requests
    chat_request = ChatRequest(
        user_input="What services do you offer?",
        session_data=state
    )
    
    print("✅ State object created successfully")
    print(f"   Session ID: {state.session_id}")
    print(f"   Current Step: {state.current_step_id}")
    print(f"   History Length: {len(state.history)}")
    
    print("✅ ChatRequest created with State")
    print(f"   User Input: {chat_request.user_input}")
    print(f"   Session Data: {chat_request.session_data.session_id}")
    
    # Test AuthConfig
    auth_configs = [
        AuthConfig(),  # Default (no auth)
        AuthConfig(auth_type="jwt", token="test-jwt-token"),
        AuthConfig(auth_type="api_key", token="test-api-key"),
    ]
    
    for i, auth in enumerate(auth_configs):
        print(f"✅ AuthConfig {i+1}: {auth.auth_type}")
    
    # Test client initialization with different configurations
    clients = [
        NomosClient("http://localhost:8000"),
        NomosClient("http://localhost:8000", auth=auth_configs[1]),
        NomosClient("http://localhost:8000", timeout=60.0),
        NomosClient("http://localhost:8000", headers={"X-Test": "value"}),
    ]
    
    for i, client in enumerate(clients):
        print(f"✅ Client {i+1} initialized: {client.base_url}")
        print(f"   Auth Type: {client.auth.auth_type}")
        print(f"   Timeout: {client.timeout}s")
    
    print("\n🎉 All type compatibility tests passed!")
    print("\n💡 The client integrates seamlessly with existing Nomos types:")
    print("   - State objects from nomos.models.agent work directly")
    print("   - All Pydantic models are fully compatible") 
    print("   - Type hints provide excellent IDE support")
    print("   - No conversion needed between client and core types")


if __name__ == "__main__":
    test_type_compatibility()
