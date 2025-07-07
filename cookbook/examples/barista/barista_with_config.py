import os

# Enable Debugging
os.environ["NOMOS_LOG_LEVEL"] = "DEBUG"
os.environ["NOMOS_ENABLE_LOGGING"] = "true"

from nomos import *
from nomos.llms.openai import OpenAI

# Define the LLM and Barista
config = AgentConfig.from_yaml("config.barista.yaml")
llm = config.llm.get_llm() if hasattr(config, "llm") and config.llm else OpenAI()
barista = Agent.from_config(config, llm)

# Start the conversation
sess = barista.create_session()

user_input = None
while True:
    res = sess.next(user_input)
    if res.decision.action == Action.RESPOND:
        user_input = input(f"Assistant: {res.decision.response}\nYou: ")
    elif res.decision.action == Action.END:
        print("Session ended.")
        break
    else:
        print("Unknown action. Exiting.")
        break

_save = input("Do you want to save the session? (y/n): ")
if _save.lower() == "y":
    sess.save_session()
