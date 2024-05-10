FROM python:3.11-alpine

ENV PYTHONUNBUFFERED=TRUE

RUN pip install kubernetes cloudflare==2.19.0

COPY src/main.py /main.py
COPY run.sh /run.sh

CMD ["/run.sh"]
