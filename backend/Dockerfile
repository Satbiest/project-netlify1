FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false \
    UNSTRUCTURED_DISABLE_NOTICE=1 \
    NLTK_DATA=/app/.cache/nltk_data

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libmagic1 poppler-utils tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements*.txt ./
# CPU-only PyTorch avoids downloading CUDA libraries on the hosting service.
RUN pip install --no-cache-dir 'torch<3' 'torchvision<1' --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# Prepare public NLP assets once during build; this step never calls Gemini.
COPY scripts/prepare_container_assets.py ./scripts/prepare_container_assets.py
RUN python scripts/prepare_container_assets.py

COPY . .
RUN useradd -m -u 10001 cvboost && chown -R cvboost:cvboost /app
USER cvboost
EXPOSE 10000
CMD ["sh", "-c", "exec python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]
