FROM alpine:3.14

RUN apk add zip
COPY compute_hash.sh /compute_hash.sh
RUN chmod +x /compute_hash.sh

ENTRYPOINT ["/compute_hash.sh"]