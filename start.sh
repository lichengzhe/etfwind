#!/bin/bash

cd /app
export PYTHONPATH=/app

# 启动 worker 后台进程
python src/worker.py &

# 启动 web 服务（前台）
uvicorn src.web.app:app --host 0.0.0.0 --port 8080
