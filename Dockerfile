FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for persistent database
RUN mkdir -p /data

# Environment variables
ENV DATABASE_PATH=/data/state_machine.db
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8080

# Expose port
EXPOSE 8080

# Run MCP server in SSE mode
CMD ["python", "mcp_server.py", "--sse"]
