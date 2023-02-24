# builder
FROM golang:1.19 as build-env

RUN go install github.com/go-delve/delve/cmd/dlv@latest

ADD build/otelcol/src /src
WORKDIR /src

RUN go build -gcflags="all=-N -l" -o /otelcol

# runner
FROM debian:buster

RUN apt update && \
    apt install --yes netcat

COPY --from=build-env /go/bin/dlv /bin/dlv
COPY --from=build-env /otelcol /bin/otelcol
COPY config/otelcol/config.yaml /etc/otelcol/config.yaml

ENTRYPOINT /bin/dlv exec --continue --accept-multiclient --headless --listen :4040 /bin/otelcol -- --config /etc/otelcol/config.yaml
EXPOSE 4040