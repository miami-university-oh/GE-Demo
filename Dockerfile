# Stage 1: Build the React frontend
FROM node:22-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python server
FROM python:3.11-slim AS production

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# CPU-only torch first: the default CUDA build adds multiple GB the container cannot use
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# Bake the YOLO pose weights into the image so the container needs no internet at runtime
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n-pose.pt')"

COPY backend/ ./backend/

COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Download mediamtx automatically for linux amd64
RUN apt-get update && apt-get install -y --no-install-recommends wget tar && \
    wget -qO- https://github.com/bluenviron/mediamtx/releases/download/v1.9.3/mediamtx_v1.9.3_linux_amd64.tar.gz | tar xvz mediamtx && \
    chmod +x ./mediamtx

COPY mediamtx.yml ./mediamtx.yml

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
