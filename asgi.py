"""
PythonAnywhere ASGI 入口文件
在 PythonAnywhere Web 面板中，将 ASGI 配置文件指向此文件
应用将会从此文件中查找名为 application 的 ASGI 实例

配置步骤：
1. 进入 PythonAnywhere Dashboard → Web 标签
2. 点击 "Add a new web app" → 选择 "Manual configuration"
3. 选择 Python 3.11 或更高版本
4. 在 "Code" 部分设置：
   - Source code: /home/你的用户名/evidence-app
   - Working directory: /home/你的用户名/evidence-app
   - ASGI configuration file: /home/你的用户名/evidence-app/asgi.py
5. 在 "Virtualenv" 部分填入：/home/你的用户名/evidence-app/venv
6. 点击 "Reload" 按钮
"""
import sys
import os

# 将项目目录加入 Python 模块搜索路径
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# 从 api.py 导入 FastAPI 应用实例，重命名为 application（PythonAnywhere 要求）
from api import app as application
