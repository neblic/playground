ARG BUILDER_TARGET=builder-download

FROM golang:1.19.3-alpine as builder-vendored
RUN apk add --no-cache ca-certificates git
RUN apk add build-base
WORKDIR /src

# copy all included vendor folder
COPY . .

RUN go build -o /go/bin/frontend .

FROM golang:1.19.3-alpine as builder-download
RUN apk add --no-cache ca-certificates git
RUN apk add build-base
WORKDIR /src

# restore dependencies
COPY go.mod go.sum ./
RUN go mod download
COPY . .

RUN go build -o /go/bin/frontend .

# can't reference BUILDER_IMAGE in `copy --from=`
FROM ${BUILDER_TARGET} as builder


FROM alpine:3.16.3 as release
RUN apk add --no-cache ca-certificates \
    busybox-extras net-tools bind-tools
WORKDIR /src
COPY --from=builder /go/bin/frontend /src/server
COPY ./templates ./templates
COPY ./static ./static

EXPOSE 8080
ENTRYPOINT ["/src/server"]
