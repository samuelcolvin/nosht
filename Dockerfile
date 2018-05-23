# ===============================================
# python build stage
FROM python:3.6-alpine3.7 as python-build

RUN apk --no-cache add gcc g++ musl-dev libuv libffi-dev make postgresql-dev

ADD ./src/requirements.txt /home/root/requirements.txt
RUN pip install -r /home/root/requirements.txt
# get rid of unnecessary files to keep the size of site-packages and the final image down
RUN find /usr/local/lib/python3.6/site-packages \
    -name '*.pyc' -o \
    -name '*.pyx' -o \
    -name '*.pyd' -o \
    -name '*.c' -o \
    -name '*.h' -o \
    -name '*.txt' | xargs rm
RUN find /usr/local/lib/python3.6/site-packages -name '__pycache__' -delete

# ===============================================
# js build stage
FROM alpine:3.7 as js-build
RUN apk --no-cache add yarn
WORKDIR /home/root

ADD ./js/package.json /home/root/package.json
ADD ./js/yarn.lock /home/root/yarn.lock
RUN yarn

ADD ./js/src /home/root/src
ADD ./js/public /home/root/public
RUN yarn build

# ===============================================
# final image
FROM python:3.6-alpine3.7
COPY --from=python-build /usr/local/lib/python3.6/site-packages /usr/local/lib/python3.6/site-packages
COPY --from=js-build /home/root/build /home/root/js/build

ADD ./src /home/root

# print used in numerous places doesn't work properly
ENV PYTHONUNBUFFERED 1
ENV APP_ON_DOCKER 1
WORKDIR /home/root
RUN adduser -D runuser
USER runuser
CMD ["./run.py", "docker-run"]
