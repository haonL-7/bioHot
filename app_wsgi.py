"""
WSGI wrapper for FastAPI — PythonAnywhere compatible
Usage: Point PythonAnywhere WSGI config to this file
"""
import sys
import os

project_home = "/home/haonL/evidence-app"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ["DEEPSEEK_API_KEY"] = "REDACTED-ROTATE-YOUR-KEY"

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
