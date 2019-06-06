FROM python:3.6-alpine

RUN pip install flask gunicorn

ENV PORT 8080
EXPOSE $PORT

COPY ./ /app/

WORKDIR /app

RUN pip install -r requirements.txt

CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:application"]
