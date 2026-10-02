# SYNTHETIC demo image: builds the warehouse at image build time so the app starts instantly.
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 GAW_PROFILE=demo PORT=7860
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python -m src.build            # generate -> pipeline -> model -> analysis (synthetic, deterministic)
EXPOSE 7860
CMD gunicorn app.main:server --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 120
