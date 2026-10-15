# tw-tile-gen backend — FastAPI + OpenCV + scikit-image (marching cubes) for Google Cloud Run
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080

# libgomp: OpenMP runtime used by scikit-learn / OpenCV wheels
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY main.py tile_processor.py ./

# Fail the build early if a native dependency can't load.
RUN python -c "import cv2, sklearn, skimage.measure, scipy.sparse, fast_simplification, trimesh, tile_processor; print('deps ok')"

# uid 1000: Hugging Face Spaces runs containers as user 1000 (also fine on Cloud Run)
RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1 --timeout-keep-alive 75"]
