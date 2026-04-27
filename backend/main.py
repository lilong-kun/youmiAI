# main.py
"""
悠米 AI 对话后端 - FastAPI
支持 WebSocket 流式对话、日志记录、模型调用
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

import ollama
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# ---------------------------- 路径配置 ----------------------------
BACKEND_DIR = Path(__file__).parent.absolute()
ROOT_DIR = BACKEND_DIR.parent

# ---------------------------- 配置加载 ----------------------------
CONFIG_PATH = BACKEND_DIR / "config.json"
DEFAULT_CONFIG = {
    "port": 8000,
    "model": "qwen3.5:4b",
    "theme_color": "#6C63FF",
    "background_image": "",
    "logs_dir": "logs",
    "log_file": "backend.log"
}


def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # 确保必要字段存在
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    else:
        return DEFAULT_CONFIG.copy()


config = load_config()

# ---------------------------- 日志系统 ----------------------------
LOG_DIR = ROOT_DIR / config["logs_dir"]
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / config["log_file"]

# 配置根日志器
logger = logging.getLogger("yumi_backend")
logger.setLevel(logging.INFO)
# 文件 handler
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)
# 控制台 handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
logger.addHandler(console_handler)


# ---------------------------- FastAPI 应用 ----------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("悠米后端服务启动")
    yield
    logger.info("悠米后端服务关闭")


app = FastAPI(title="悠米 AI 对话服务", lifespan=lifespan)

# 挂载静态文件（前端）
static_dir = ROOT_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """返回前端页面"""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "悠米后端运行中，但未找到前端文件"}


# ---------------------------- WebSocket 对话 ----------------------------
@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    client_id = f"{websocket.client.host}:{websocket.client.port}"
    logger.info(f"客户端 {client_id} 已连接")

    try:
        while True:
            # 接收用户消息
            data = await websocket.receive_text()
            logger.info(f"收到来自 {client_id} 的消息: {data[:50]}...")

            try:
                msg = json.loads(data)
                user_content = msg.get("content", "")
            except:
                user_content = data

            if not user_content.strip():
                await websocket.send_text(json.dumps({"error": "消息内容为空"}))
                continue

            # 调用 Ollama 流式生成
            try:
                stream = ollama.chat(
                    model=config["model"],
                    messages=[{"role": "user", "content": user_content}],
                    stream=True
                )

                # 逐块发送回复
                for chunk in stream:
                    if "message" in chunk and "content" in chunk["message"]:
                        token = chunk["message"]["content"]
                        await websocket.send_text(json.dumps({"token": token}))
                        await asyncio.sleep(0)  # 让出控制权

                # 发送结束标记
                await websocket.send_text(json.dumps({"done": True}))
                logger.info(f"回复发送完毕，客户端 {client_id}")

            except Exception as e:
                logger.error(f"模型调用失败: {str(e)}")
                await websocket.send_text(json.dumps({"error": f"模型调用出错: {str(e)}"}))

    except WebSocketDisconnect:
        logger.info(f"客户端 {client_id} 断开连接")
    except Exception as e:
        logger.error(f"WebSocket 异常: {str(e)}")


# ---------------------------- 健康检查接口 ----------------------------
@app.get("/health")
async def health_check():
    return {"status": "ok", "model": config["model"]}


# ---------------------------- 直接启动入口 ----------------------------
if __name__ == "__main__":
    import uvicorn

    port = int(sys.argv[1]) if len(sys.argv) > 1 else config["port"]
    logger.info(f"启动服务，端口 {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")