FROM python:3.13-alpine@sha256:1e1f6334529d1fb26a2ef619d7cffb30a7c7d7cc1cc7338ebee283a58d1aeaca AS python-runtime
COPY docker/python-runtime.txt /tmp/python-runtime.txt
RUN pip install --no-cache-dir --no-compile --only-binary=:all: --require-hashes -r /tmp/python-runtime.txt && \
    python -B -m pip check && \
    rm -rf /usr/local/lib/python3.13/sqlite3 /usr/local/lib/python3.13/lib-dynload/_sqlite3*.so

FROM alpine:3.24@sha256:3f4d6b32e26703c6082839234f43769d5046b3ac7c910033911d1e71d8cd630a AS alpine-packages
COPY docker/alpine-runtime/ /locks/
RUN arch="$(apk --print-arch)" && lock="/locks/$arch.sha256" && test -s "$lock" && \
    mkdir /apk && cd /apk && \
    while read -r checksum package; do \
        wget -q -O "$package" "https://dl-cdn.alpinelinux.org/alpine/v3.24/main/$arch/$package" || exit 1; \
    done < "$lock" && \
    sha256sum -c "$lock"

FROM alpine:3.24@sha256:3f4d6b32e26703c6082839234f43769d5046b3ac7c910033911d1e71d8cd630a
ENV PATH=/usr/local/bin:$PATH LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# The runtime retains APK's installed database and a locked service account.
RUN --network=none --mount=type=bind,from=alpine-packages,source=/apk,target=/apk \
    apk --repositories-file /dev/null add --no-cache /apk/*.apk && \
    addgroup -S -g 10001 cinevault && adduser -S -D -u 10001 -G cinevault cinevault && \
    sed -i '/^cinevault:!:/s/^cinevault:!:[0-9][0-9]*:/cinevault:!:20370:/' /etc/shadow && \
    grep -q '^cinevault:!:20370:' /etc/shadow && \
    rm -f /var/log/apk.log && \
    mkdir /data && chown 10001:10001 /data
COPY --from=python-runtime /usr/local /usr/local
WORKDIR /srv/cinevault
COPY --chown=cinevault:cinevault app ./app
USER 10001:10001
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2)"
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:create_app()"]
