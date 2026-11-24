FROM python:3.10-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build
COPY pyproject.toml setup.cfg LICENSE README.md ./
COPY src/ ./src/
RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python3 -m pip wheel --no-deps --no-build-isolation --wheel-dir /wheels .

FROM python:3.10-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app
COPY --from=builder /wheels /wheels
RUN python3 -m pip install --no-cache-dir --no-index --find-links=/wheels rag-regression-auditor \
    && rm -rf /wheels

COPY Makefile LICENSE README.md CHANGELOG.md ./
COPY policy/ ./policy/
COPY fixtures/ ./fixtures/
COPY sql/ ./sql/
COPY scripts/ ./scripts/
COPY experiments/ ./experiments/
COPY tools/ ./tools/
COPY tests/ ./tests/
COPY docs/ ./docs/
COPY assets/ ./assets/

ENTRYPOINT ["python3", "-m", "rag_regression_auditor.cli"]
CMD ["audit", "--fixture", "fixtures/rag_eval_corpus.jsonl", "--policy", "policy/rag_audit_policy.json"]
