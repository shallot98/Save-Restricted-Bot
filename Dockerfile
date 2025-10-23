FROM python:3.9
WORKDIR /app

COPY requirements.txt /app/
RUN pip3 install -r requirements.txt

COPY . /app

# Create downloads directory
RUN mkdir -p /app/downloads

CMD flask run -h 0.0.0.0 -p 10000 & python3 main.py