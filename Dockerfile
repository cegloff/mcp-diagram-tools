FROM mcr.microsoft.com/playwright/python:v1.57.0-jammy

WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install the package
RUN pip install -e .

# Copy test files
COPY test_convert.py test_render_feature.py test_covid.py ./
COPY test_render.excalidraw ./

# Default command - test the render feature
CMD ["python", "test_render_feature.py"]
