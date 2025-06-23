FROM python:3.13

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . /app/

# Collect static files (optional, uncomment if needed)
# RUN python webnovel/manage.py collectstatic --noinput

CMD ["sh", "-c", "python webnovel/manage.py migrate && python webnovel/manage.py runserver 0.0.0.0:8000"] 