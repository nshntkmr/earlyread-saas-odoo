FROM python:3.12-slim

RUN useradd --create-home appuser
WORKDIR /srv/ai_service

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

USER appuser
EXPOSE 8808

# Remote deployment serves streamable HTTP; desktop/stdio users run the
# package locally instead of this image.
CMD ["posterra-mcp", "--http", "--port", "8808"]
