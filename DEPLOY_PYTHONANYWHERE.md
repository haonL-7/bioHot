# PythonAnywhere 部署指南

## 准备工作

1. 注册 [PythonAnywhere](https://www.pythonanywhere.com) 账号（免费套餐即可）
2. 确认项目文件已上传到 GitHub（方便一键克隆）

## 部署步骤

### 步骤 1：上传代码

打开 PythonAnywhere 的 **Bash 终端**（Consoles 标签），执行：

```bash
# 克隆项目（替换为你的仓库地址）
git clone https://github.com/你的用户名/evidence-app.git

# 或者手动上传：在 Files 标签中上传所有项目文件到 /home/你的用户名/evidence-app/
```

### 步骤 2：创建虚拟环境并安装依赖

```bash
cd ~/evidence-app
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn openai
```

### 步骤 3：配置环境变量（可选）

```bash
# 在 Bash 中设置 DeepSeek API Key（如果代码中未硬编码）
echo 'export DEEPSEEK_API_KEY="sk-你的API密钥"' >> ~/.bashrc
source ~/.bashrc
```

### 步骤 4：在 Web 面板中配置

1. 进入 **Dashboard → Web** 标签
2. 点击 **"Add a new web app"**
3. 选择 **"Manual configuration"**（不要选 FastAPI 自动配置）
4. Python 版本选 **3.11** 或 **3.12**
5. 在配置表单中填写：

| 配置项 | 值 |
|---|---|
| **Source code** | `/home/你的用户名/evidence-app` |
| **Working directory** | `/home/你的用户名/evidence-app` |
| **ASGI configuration file** | `/home/你的用户名/evidence-app/asgi.py` |
| **Virtualenv** | `/home/你的用户名/evidence-app/venv` |

### 步骤 5：配置静态文件（可选）

在 Web 面板的 **Static files** 部分：

| URL | Directory |
|---|---|
| `/static/` | `/home/你的用户名/evidence-app/static/` |

### 步骤 6：启动应用

点击 Web 面板顶部的 **绿色 "Reload" 按钮**。

你的网站将在以下地址生效：
```
https://你的用户名.pythonanywhere.com/
```

### 步骤 7：验证

打开浏览器访问 `https://你的用户名.pythonanywhere.com/`，应该能看到完整的证据评估系统页面。

---

## 免费套餐限制

- 只能访问白名单中的外部 API（**api.deepseek.com 在白名单中** ✅）
- 每天有一定的 CPU 时间限制
- 不支持自定义域名
- 3 个月未登录会暂停应用

---

## 故障排查

**问题：网站显示 "Something went wrong"**
→ 查看错误日志：Web 标签 → Log files → Error log

**问题：AI 分析不工作**
→ 确认 `DEEPSEEK_API_KEY` 环境变量已设置，或在 api.py 中硬编码了密钥

**问题：知识库搜索无结果**
→ 确认 `knowledge_base.json` 文件已上传到项目目录

**问题：页面样式异常**
→ 确认 index.html 和 api.py 在同一目录，且 api.py 已正确加载前端文件
