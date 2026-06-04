# Elpio image. Runs `elpio operator` (kopf) by default; the same image also
# serves the admission webhook and the management API (the `server` extra).
FROM python:3.12-slim

WORKDIR /app

# Install deps first for layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir '.[server]'

# Non-root.
RUN useradd --create-home --uid 10001 elpio
USER 10001

ENTRYPOINT ["elpio"]
CMD ["operator"]
