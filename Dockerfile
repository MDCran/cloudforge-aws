FROM ghcr.io/astral-sh/uv:0.8.22-python3.12-bookworm-slim@sha256:28df4bbd896cf66a224f2e0cb22240a9a2b9803a3a13519bcadf2e9fdd68c632
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked
COPY . .
ENV PYTHONPATH=/app:/app/packages
RUN useradd --create-home cloudforge && chown -R cloudforge:cloudforge /app
USER cloudforge
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "scripts.local:app", "--host", "0.0.0.0", "--port", "8000"]
