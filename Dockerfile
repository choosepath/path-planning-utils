# ---------- builder ----------
FROM python:3.11-slim AS builder

ENV INSTALL_PATH=/utilities-cp
WORKDIR ${INSTALL_PATH}

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

# ---------- runtime ----------
FROM python:3.11-slim

LABEL authors="savvas"

ENV INSTALL_PATH=/utilities-cp
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR ${INSTALL_PATH}

COPY --from=builder /opt/venv /opt/venv
COPY . .

EXPOSE 5000

CMD ["gunicorn", "--workers", "2", "--threads", "4", "--timeout", "120", "--graceful-timeout", "30", "--keep-alive", "5", "--access-logfile", "-", "--error-logfile", "-", "-b", "0.0.0.0:5000", "app:app"]