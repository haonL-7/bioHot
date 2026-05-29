import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any

app = FastAPI()

# 允许跨域（本地和云端都无影响）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_knowledge_base() -> Dict[str, Any]:
    """加载 knowledge_base.json 文件"""
    with open("knowledge_base.json", "r", encoding="utf-8") as f:
        return json.load(f)

# ==================== GET 接口（匹配前端 ask?question=） ====================
@app.get("/ask")
async def ask_get(question: str):
    """前端使用 fetch('/ask?question=益生菌') 时调用"""
    data = load_knowledge_base()
    keyword = question.strip().lower()
    
    # 搜索益生菌列表
    for item in data.get("probiotics", []):
        if keyword == item["name"].lower():
            return item
    
    # 搜索代谢物列表
    for item in data.get("metabolites", []):
        if keyword == item["name"].lower():
            return item
    
    raise HTTPException(status_code=404, detail="未找到该关键词的证据")

# ==================== POST 接口（兼容旧版或备用） ====================
class QueryRequest(BaseModel):
    query: str

@app.post("/query")
async def query_evidence(req: QueryRequest):
    data = load_knowledge_base()
    keyword = req.query.strip().lower()
    
    for item in data.get("probiotics", []):
        if keyword == item["name"].lower():
            return item
    for item in data.get("metabolites", []):
        if keyword == item["name"].lower():
            return item
    
    raise HTTPException(status_code=404, detail="未找到该关键词的证据")

# ==================== 提供前端页面 ====================
@app.get("/", response_class=HTMLResponse)
async def get_index():
    """访问根路径时返回 index.html 查询界面"""
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

# ==================== 启动服务（云端自动获取端口） ====================
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)