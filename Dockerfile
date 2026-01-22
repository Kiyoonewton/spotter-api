FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Create location cache directory
RUN mkdir -p /app/location_cache && chmod 777 /app/location_cache

# Copy project files
COPY . /app/

# Expose port
EXPOSE 8000

# Run the application
# Update the CMD line in Dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--log-level=debug", "--capture-output", "--enable-stdio-inheritance", "eld_api.wsgi:application"]