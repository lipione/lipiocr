FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

ARG INSTALL_OCR_EXTRAS=false

COPY backend/pyproject.toml ./pyproject.toml
COPY backend/app ./app

RUN python -m pip install --upgrade pip \
    && if [ "$INSTALL_OCR_EXTRAS" = "true" ]; then \
        python -m pip install --no-cache-dir '.[ocr]'; \
    else \
        python -m pip install --no-cache-dir .; \
    fi

RUN mkdir -p /app/storage/uploads

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
