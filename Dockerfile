FROM python:3.12-slim

WORKDIR /app

# Install pinned dependencies first for better layer caching.
COPY AI_Gym_Project/requirements.txt ./AI_Gym_Project/requirements.txt
RUN pip install --no-cache-dir -r AI_Gym_Project/requirements.txt

COPY AI_Gym_Project/ ./AI_Gym_Project/

WORKDIR /app/AI_Gym_Project

ENV PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8501', timeout=4).status==200 else 1)"

CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
