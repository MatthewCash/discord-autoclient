FROM selenium/standalone-chrome:120.0

RUN sudo apt-get update
RUN sudo apt-get install python3-pip git -y

WORKDIR /app

COPY requirements.txt ./
RUN sudo python3 -m pip install --upgrade pip
RUN sudo python3 -m pip install -r requirements.txt

COPY src /app

ENV PYTHONUNBUFFERED=1

CMD ["python3", "main.py"]
