# Neblic playground

This repository sets up all the pieces necessary to run and play with the Neblic platform.
It instruments a [fork](./svc) of a microservices-based e-commerce app demo application used at Google.
See the fork [README](./svc/README.md) to understand its architecture and get more details about the instrumented microservices.

## Build and run

See this [quickstart](https://docs.neblic.com/latest/quickstart/playground/) guide to get detailed instructions on how to play with the Neblic playground.

# Local development

The `Makefile` includes targets to build the services and the collector using a local Neblic platform codebase and to build a debuggable collector. Check the `Makefile` for details.

## Enable Neblic TLS and bearer auth

To enable TLS and bearer authentication within the Neblic platform components:
* Uncomment the required lines in the `config.yaml` file
* Set the ENABLE_NEBLIC_TLS env variable to true for each service in the `docker-compose.yaml` file.

The Neblictl cli will need to use the certificate at `config/otelcol/ca/otelcol.crt` to validate the collector certificate. It can be provided when connecting to the collector or it can be installed in the system certificate store.
