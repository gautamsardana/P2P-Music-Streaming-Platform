FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install Pyro4 \
 && apt-get update \
 && apt-get install -y iproute2 \
 && rm -rf /var/lib/apt/lists/*
ENTRYPOINT ["python"]
CMD ["peer.py"]