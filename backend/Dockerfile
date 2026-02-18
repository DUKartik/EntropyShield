# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for OpenCV and others
# poppler-utils is REQUIRED for pdf2image/pdfminer extraction visual features
RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 poppler-utils && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch and Torchvision (Required for SegFormer/Transformers)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Threading: Force single-threaded execution for underlying libraries
# This prevents deadlocks when mixing OpenCV (OpenMP) and PyTorch in Cloud Run
ENV OMP_NUM_THREADS=4
ENV OPENBLAS_NUM_THREADS=4
ENV MKL_NUM_THREADS=4
ENV VECLIB_MAXIMUM_THREADS=4
ENV NUMEXPR_NUM_THREADS=4

# Cloud Run injects the PORT environment variable (defaults to 8080)
ENV PORT=8080

# Run uvicorn server
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
