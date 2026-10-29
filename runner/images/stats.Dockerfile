FROM python:3.12-slim

WORKDIR /app

# Frozen stats stack: every dependency is ==-pinned so builds are
# reproducible with no resolver drift at build time.
RUN pip install --no-cache-dir \
    pandas==3.1.0 \
    numpy==2.5.4 \
    scipy==1.18.1 \
    statsmodels==0.15.0 \
    matplotlib==3.11.2 \
    nbformat==5.11.1 \
    nbclient==0.11.0

CMD ["python3"]
