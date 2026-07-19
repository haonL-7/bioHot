"""
WSGI wrapper for FastAPI — PythonAnywhere compatible
Usage: Point PythonAnywhere WSGI config to this file
"""
import sys
import os

project_home = "/home/haonL/evidence-app"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# ⚠️  DO NOT hardcode API keys here. Set via PythonAnywhere dashboard:
#     "Web" tab → "Environment variables" → DEEPSEEK_API_KEY=your-key
#     Or create a .env file in /home/haonL/evidence-app/
if not os.environ.get("DEEPSEEK_API_KEY"):
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("DEEPSEEK_API_KEY="):
                    os.environ["DEEPSEEK_API_KEY"] = line.split("=", 1)[1].strip()
                    break
if not os.environ.get("DEEPSEEK_API_KEY"):
    raise RuntimeError(
        "DEEPSEEK_API_KEY is required. "
        "Set it via PythonAnywhere dashboard (Web → Environment variables) "
        "or create /home/haonL/evidence-app/.env with DEEPSEEK_API_KEY=your-key"
    )

# Step-by-step with clear error reporting
import_error = None

try:
    from a2wsgi import ASGIMiddleware
except Exception as e:
    import_error = f"a2wsgi import failed: {e}"

if import_error is None:
    try:
        from api import app
    except Exception as e:
        import_error = f"api import failed: {e}"

if import_error is None:
    try:
        application = ASGIMiddleware(app)
    except Exception as e:
        import_error = f"ASGIMiddleware wrap failed: {e}"

# If any step failed, return a simple WSGI app that shows the error
if import_error:

    def application(environ, start_response):
        status = "200 OK"
        headers = [("Content-Type", "text/plain; charset=utf-8")]
        start_response(status, headers)
        return [
            f"Setup Error: {import_error}\n".encode(),
            f"sys.path: {sys.path[:3]}\n".encode(),
            f"cwd: {os.getcwd()}\n".encode(),
        ]
