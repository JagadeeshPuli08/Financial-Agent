import os

from dotenv import load_dotenv

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "Vola Financial Chat Bot").strip()
AGENT_NAME = os.getenv("AGENT_NAME", "Personal_Financial_Agent").strip()

if not APP_NAME:
    APP_NAME = "Vola Financial Chat Bot"
if not AGENT_NAME:
    AGENT_NAME = "Personal_Financial_Agent"
