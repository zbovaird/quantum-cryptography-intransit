FROM python:3.10-slim

WORKDIR /app

# Install system dependencies if needed (e.g. for cryptography if we switch back)
# RUN apt-get update && apt-get install -y build-essential libssl-dev libffi-dev

# Copy project files
COPY . /app

# Install dependencies
# We use the refactored core which uses standard library, but flask/requests are needed.
# If pyproject.toml is used:
RUN pip install .

# Expose the port for the Flask app
EXPOSE 5000

# Default command (can be overridden in docker-compose)
CMD ["python", "-m", "src.app"]
