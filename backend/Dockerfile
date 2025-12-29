FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if needed
# RUN apt-get update && apt-get install -y gcc

# Copy requirements/pyproject
COPY pyproject.toml .

# Install dependencies
# Using pip directly since pyproject.toml is simple, or we could use uv
RUN pip install "fastapi[all]" sqlmodel uvicorn uv

COPY . .

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
