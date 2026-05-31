import sys
import os

project_home = "/home/haonL/evidence-app"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ["DEEPSEEK_API_KEY"] = "REDACTED-ROTATE-YOUR-KEY"

from a2wsgi import ASGIMiddleware
from api import app

application = ASGIMiddleware(app)
