FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install Pyro4

ENTRYPOINT ["python"]
CMD ["peer.py"]
