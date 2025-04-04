FROM python:3.10-slim

WORKDIR /app

# Set pip cache directory and other optimizations
ENV PIP_NO_CACHE_DIR=false \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=100

# Copy requirements files first to leverage Docker cache
COPY web_crawler/requirements.txt web_crawler-requirements.txt
COPY shared/requirements.txt shared-requirements.txt

# Install dependencies with pip cache
RUN pip install --cache-dir=/root/.pip-cache -r web_crawler-requirements.txt && \
    pip install --cache-dir=/root/.pip-cache -r shared-requirements.txt && \
    rm -rf /root/.cache/pip/*

# Copy and install shared module
COPY shared/ /app/shared/
RUN cd /app/shared && pip install --cache-dir=/root/.pip-cache -e . && \
    rm -rf /root/.cache/pip/*

# Now copy the rest of the application
COPY web_crawler/src/ src/
COPY web_crawler/setup.py .
COPY web_crawler/README.md .

# Install the package
RUN pip install --cache-dir=/root/.pip-cache -e . && \
    rm -rf /root/.cache/pip/*

# Set the working directory to src
WORKDIR /app/src

# Expose the FastAPI port
EXPOSE 8000

# Command to run the FastAPI server
CMD ["python", "main.py"] 