# Elpio operator image. Runs `elpio operator` (kopf) in-cluster.
FROM python:3.12-slim

WORKDIR /app

# Install deps first for layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Non-root.
RUN useradd --create-home --uid 10001 elpio
USER 10001

ENTRYPOINT ["elpio"]
CMD ["operator"]
