FROM python:3.11-slim

# Install rustc without extra recommended packages, then clean apt cache
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends rustc && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Use CPU-only PyTorch and do not cache downloaded wheels inside the layer
ENV PIP_ROOT_USER_ACTION=ignore PIP_NO_CACHE_DIR=1
RUN pip install --no-cache-dir numpy "torch==2.0.1" matplotlib --index-url https://download.pytorch.org/whl/cpu

CMD ["python3", "main.py"]
