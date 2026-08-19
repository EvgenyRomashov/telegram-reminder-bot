FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app

COPY pyproject.toml README.md ./
COPY reminder_bot ./reminder_bot
RUN pip install --no-cache-dir .

RUN mkdir -p /app/data && chown -R app:app /app
USER app

CMD ["python", "-m", "reminder_bot.main"]
