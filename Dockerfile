#FROM jupyter/scipy-notebook:68d2d835fb16
FROM python:3.9-slim-buster
USER root
RUN apt update && apt install -y locales

RUN export LC_ALL="sv_SE.UTF- 8" && \
    export LC_CTYPE="sv_SE.UTF-8" && \
    dpkg-reconfigure locales && \
    mkdir -p /usr/src/app


WORKDIR /usr/src/app

COPY ./requirements.txt requirements.txt
RUN python3 -m pip install -r requirements.txt
