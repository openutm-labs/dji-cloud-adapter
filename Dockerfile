FROM python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d
ARG VCS_REF=development
LABEL org.opencontainers.image.source="https://github.com/openutm-labs/dji-cloud-adapter" \
      org.opencontainers.image.revision=$VCS_REF \
      org.opencontainers.image.licenses="Apache-2.0"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home adaptor
USER adaptor
EXPOSE 8080
CMD ["uvicorn", "dji_cloud_adaptor.api:build_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log"]
