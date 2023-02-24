ARG BUILDER_TARGET=builder-download

FROM golang:1.19.3-alpine as builder-vendored
RUN apk add --no-cache ca-certificates git
RUN apk add build-base
WORKDIR /src

# copy all included vendor folder
COPY . .

RUN go build -o /go/bin/shippingservice .

FROM golang:1.19.3-alpine as builder-download
RUN apk add --no-cache ca-certificates git
RUN apk add build-base
WORKDIR /src

# restore dependencies
COPY go.mod go.sum ./
RUN go mod download
COPY . .

RUN go build -o /go/bin/shippingservice .

# can't reference BUILDER_IMAGE in `copy --from=`
FROM ${BUILDER_TARGET} as builder


FROM alpine:3.16.3 AS without-grpc-health-probe-bin
RUN apk add --no-cache ca-certificates
WORKDIR /src
COPY --from=builder /go/bin/shippingservice /src/shippingservice
ENV APP_PORT=50051

EXPOSE 50051
ENTRYPOINT ["/src/shippingservice"]


FROM without-grpc-health-probe-bin
RUN GRPC_HEALTH_PROBE_VERSION=v0.4.14 && \
    wget -qO/bin/grpc_health_probe https://github.com/grpc-ecosystem/grpc-health-probe/releases/download/${GRPC_HEALTH_PROBE_VERSION}/grpc_health_probe-linux-amd64 && \
    chmod +x /bin/grpc_health_probe