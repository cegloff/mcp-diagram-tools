FROM mcr.microsoft.com/playwright/python:v1.57.0-jammy

WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install the package
RUN pip install -e .

# Install Node.js 18.x (required for excalidraw-brute-export-cli)
RUN apt-get update && \
    apt-get install -y ca-certificates curl gnupg && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_18.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y nodejs && \
    npm install -g excalidraw-brute-export-cli && \
    rm -rf /var/lib/apt/lists/*

# Copy test files
COPY test_convert.py test_render_feature.py test_covid.py test_process_flow.py test_workflow_render.py ./

# Default command - test the render feature
CMD ["python", "test_render_feature.py"]
