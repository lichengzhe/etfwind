FROM python:3.11-slim

ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir .

# 安装 Playwright 依赖和 Chromium
RUN playwright install-deps chromium && playwright install chromium

RUN mkdir -p /app/data

EXPOSE 8080

CMD ["./start.sh"]
