# https://pypi.org/project/webscrapbook/

FROM python:3.7.3-alpine

LABEL version="1.0" maintainer="vsc55@cerebelum.net" description="Docker webscrapbook"

ARG wsb_ver
ENV wsb_ver=${wsb_ver}

RUN apk upgrade --no-cache; \
	apk add --no-cache --virtual .build-deps gcc libc-dev libxslt-dev; \
    apk add --no-cache bash libxslt curl; \
	pip install --no-cache-dir --upgrade pip; \
	if [ "$wsb_ver" = "" ] ; \
	then pip install --no-cache-dir webscrapbook; \ 
	else pip install --no-cache-dir webscrapbook==${wsb_ver}; \
	fi; \
	apk del .build-deps;

WORKDIR /
COPY --chown=root:root ["config.ini", "./"]
COPY --chown=root:root ["entrypoint.sh", "run_wsb.sh", "./"]

ENV HTTP_PORT=8080 MODE_RUN=production WSB_VERSION=${wsb_ver:-latest}

VOLUME ["/data"]
EXPOSE ${HTTP_PORT}/tcp

HEALTHCHECK --interval=1m --timeout=15s --start-period=20s --retries=4  CMD curl -sf http://localhost:${HTTP_PORT} > /dev/null || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["start"]
