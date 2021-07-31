FROM python:3.6

WORKDIR /psma

COPY requirements.txt requirements.txt

RUN python3 -m pip install --upgrade pip
RUN pip3 install -r requirements.txt

COPY . .

ENV FLASK_APP=/psma

CMD flask run --host 0.0.0.0