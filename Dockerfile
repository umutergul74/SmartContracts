FROM python:3.12.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir .

ENTRYPOINT ["scbounty"]
CMD ["env", "doctor"]
