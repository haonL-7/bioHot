import sys
import os

project_home = "/home/haonL/evidence-app"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# ⚠️  DO NOT hardcode API keys here. Set via PythonAnywhere dashboard
#     or /home/haonL/evidence-app/.env
if not os.environ.get("DEEPSEEK_API_KEY"):
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("DEEPSEEK_API_KEY="):
                    os.environ["DEEPSEEK_API_KEY"] = line.split("=", 1)[1].strip()
                    break
if not os.environ.get("DEEPSEEK_API_KEY"):
    raise RuntimeError("DEEPSEEK_API_KEY is required. Set via PythonAnywhere dashboard or .env file")

from a2wsgi import ASGIMiddleware
from api import app

application = ASGIMiddleware(app)
