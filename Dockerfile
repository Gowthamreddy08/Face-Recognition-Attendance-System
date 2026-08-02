FROM python:3.11-slim

# System packages needed to build dlib (face_recognition's dependency)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud platforms set PORT for you; default to 5000 for local docker run
ENV PORT=5000
EXPOSE 5000

# gunicorn instead of Flask's dev server for production
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT app:app"]
