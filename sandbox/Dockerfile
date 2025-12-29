FROM python:3.11-slim

# Install system dependencies if typically needed, but for now just rustc
# We need to run apt-get update and install rustc
RUN apt-get update && apt-get install -y rustc

# We can add numpy/pandas later if courses require them
RUN pip install numpy pytorch
CMD ["python3", "main.py"]
