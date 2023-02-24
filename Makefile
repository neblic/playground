check_defined = \
    $(strip $(foreach 1,$1, \
        $(call __check_defined,$1,$(strip $(value 2)))))
__check_defined = \
    $(if $(value $1),, \
      $(error Undefined $1$(if $2, ($2))))

# requires protoc, Go protoc-gen-go, protoc-gen-go-grpc and Python grpc-tools :
# go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
# go install google.golang.org/grpc/cmd/protoc-gen-go@latest
# pip install grpcio grpcio-tools
.PHONY: update-svcs-pb
update-svcs-pb:
	find svc/src/ -maxdepth 1 -type d \( ! -name src -and ! -name loadgenerator \) -exec bash -c "cd '{}' && ./genproto.sh" \;

.PHONY: update-svcs-latest-neblic
update-svcs-latest-neblic:
	cd svc/src/checkoutservice && go get github.com/neblic/platform && go mod tidy
	cd svc/src/frontend && go get github.com/neblic/platform && go mod tidy
	cd svc/src/productcatalogservice && go get github.com/neblic/platform && go mod tidy
	cd svc/src/shippingservice && go get github.com/neblic/platform && go mod tidy

.PHONY: set-svcs-neblic
set-svcs-neblic:
	@:$(call check_defined, NEBLIC_VERSION, Neblic target version)
	cd svc/src/checkoutservice && go mod edit -require=github.com/neblic/platform@${NEBLIC_VERSION} && go mod tidy
	cd svc/src/frontend && go mod edit -require=github.com/neblic/platform@${NEBLIC_VERSION} && go mod tidy
	cd svc/src/productcatalogservice && go mod edit -require=github.com/neblic/platform@${NEBLIC_VERSION} && go mod tidy
	cd svc/src/shippingservice && go mod edit -require=github.com/neblic/platform@${NEBLIC_VERSION} && go mod tidy

# requires otelcol builder
# https://github.com/open-telemetry/opentelemetry-collector/tree/main/cmd/builder
.PHONY: build-otelcol-dev
build-otelcol-dev:
	@:$(call check_defined, LOCAL_PLATFORM_MODULE, Neblic platform Go module path)
	envsubst < build/otelcol/ocb.yaml.tmpl > build/otelcol/ocb.yaml && \
		builder --config=build/otelcol/ocb.yaml --skip-compilation && \
		cd build/otelcol/src && go mod vendor && cd - && \
		docker build -f build/otelcol/Dockerfile -t ghcr.io/neblic/otelcol-dev:latest . && \
		rm build/otelcol/ocb.yaml && rm -Rf build/otelcol/src

.PHONY: build-otelcol-local-neblic
build-otelcol-local-neblic:
	@:$(call check_defined, LOCAL_PLATFORM_MODULE, Neblic platform Go module path)
	cd ${LOCAL_PLATFORM_MODULE} && \
		goreleaser release --snapshot --rm-dist

.PHONY: clean-svcs-local-neblic-replace
clean-svcs-local-neblic-replace:
	cd svc/src/checkoutservice && \
		go mod edit -dropreplace github.com/neblic/platform && \
		rm -Rf vendor
	cd svc/src/frontend && \
		go mod edit -dropreplace github.com/neblic/platform && \
		rm -Rf vendor
	cd svc/src/productcatalogservice && \
		go mod edit -dropreplace github.com/neblic/platform && \
		rm -Rf vendor
	cd svc/src/shippingservice && \
		go mod edit -dropreplace github.com/neblic/platform && \
		rm -Rf vendor

.PHONY: build-svcs-local-neblic
build-svcs-local-neblic:
	@:$(call check_defined, LOCAL_PLATFORM_MODULE, Neblic platform Go module path)
	cd svc/src/checkoutservice && \
		go mod edit -replace github.com/neblic/platform=$(LOCAL_PLATFORM_MODULE) && \
		go mod tidy && \
		go mod vendor
	cd svc/src/frontend && \
		go mod edit -replace github.com/neblic/platform=$(LOCAL_PLATFORM_MODULE) && \
		go mod tidy && \
		go mod vendor
	cd svc/src/productcatalogservice && \
		go mod edit -replace github.com/neblic/platform=$(LOCAL_PLATFORM_MODULE) && \
		go mod tidy && \
		go mod vendor
	cd svc/src/shippingservice && \
		go mod edit -replace github.com/neblic/platform=$(LOCAL_PLATFORM_MODULE) && \
		go mod tidy && \
		go mod vendor
	docker compose build --build-arg BUILDER_TARGET=builder-vendored
	$(MAKE) clean-svcs-local-neblic-replace

.PHONY: up-dev
up-dev:
	@:$(call check_defined, LOCAL_PLATFORM_MODULE, Neblic platform Go module path)
	$(MAKE) build-otelcol-dev
	$(MAKE) build-svcs-local-neblic
	docker compose -f docker-compose.common.yaml -f docker-compose.dev.yaml up -d

.PHONY: up-local
up-local:
	@:$(call check_defined, LOCAL_PLATFORM_MODULE, Neblic platform Go module path)
	$(MAKE) build-otelcol-local-neblic
	$(MAKE) build-svcs-local-neblic
	docker compose up -d