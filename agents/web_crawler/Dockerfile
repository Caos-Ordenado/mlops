FROM python:3.10-slim

WORKDIR /app

# Copy the source code
COPY . .

# Install the package in development mode
RUN pip install -e .

# Set the working directory to src
WORKDIR /app/src

# Expose the FastAPI port
EXPOSE 8000

# Command to run the FastAPI server
CMD ["python", "main.py"] 