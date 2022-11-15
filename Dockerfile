FROM ubuntu:20.04

ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Singapore
ENV DEBIAN_FRONTEND=noninteractive
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

RUN apt-get update --fix-missing && \
    apt-get upgrade -y

RUN apt-get install -y build-essential wget curl

WORKDIR /validator_service

COPY . /validator_service

RUN apt-get update --fix-missing\
    && apt-get install -y software-properties-common \
    && apt-get update --fix-missing
    
RUN apt-get install -y python3-pip

RUN pip3 install -r requirements.txt

# CMD python3 main.py
# CMD make worker