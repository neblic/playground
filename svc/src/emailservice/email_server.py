#!/usr/bin/python
#
# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from concurrent import futures
import argparse
import http.server
import os
import socketserver
import signal
import sys
import time
import grpc
import traceback
from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateError
from pathlib import Path
from threading import Thread
from google.api_core.exceptions import GoogleAPICallError
from google.auth.exceptions import DefaultCredentialsError
from google.protobuf.json_format import Parse

import demo_pb2
import demo_pb2_grpc
from grpc_health.v1 import health_pb2
from grpc_health.v1 import health_pb2_grpc

from opentelemetry import trace
from opentelemetry.instrumentation.grpc import GrpcInstrumentorServer
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from kafka import KafkaConsumer

# import googleclouddebugger
import googlecloudprofiler

from logger import getJSONLogger
logger = getJSONLogger('emailservice-server')

# try:
#     googleclouddebugger.enable(
#         module='emailserver',
#         version='1.0.0'
#     )
# except:
#     pass

# Loads confirmation email template from file
env = Environment(
    loader=FileSystemLoader('templates'),
    autoescape=select_autoescape(['html', 'xml'])
)
template = env.get_template('confirmation.html')

class EmailService():
  def __init__(self):
    raise Exception('cloud mail client not implemented')
    super().__init__()

  @staticmethod
  def send_email(client, email_address, content):
    response = client.send_message(
      sender = client.sender_path(project_id, region, sender_id),
      envelope_from_authority = '',
      header_from_authority = '',
      envelope_from_address = from_address,
      simple_message = {
        "from": {
          "address_spec": from_address,
        },
        "to": [{
          "address_spec": email_address
        }],
        "subject": "Your Confirmation Email",
        "html_body": content
      }
    )
    logger.info("Message sent: {}".format(response.rfc822_message_id))

  def send_order_confirmation(self, request, context):
    email = request.email
    order = request.order

    try:
      confirmation = template.render(order = order)
    except TemplateError as err:
      context.set_details("An error occurred when preparing the confirmation mail.")
      logger.error(err.message)
      context.set_code(grpc.StatusCode.INTERNAL)
      return demo_pb2.Empty()

    try:
      EmailService.send_email(self.client, email, confirmation)
    except GoogleAPICallError as err:
      context.set_details("An error occurred when sending the email.")
      print(err.message)
      context.set_code(grpc.StatusCode.INTERNAL)
      return demo_pb2.Empty()

    return demo_pb2.Empty()

class DummyEmailService():
  def __init__(self, http_port, mail_location = "/tmp/mail", max_mails = 100):
    os.makedirs(mail_location, exist_ok=True)

    self.mail_location = mail_location
    self.max_mails = max_mails

    class Handler(http.server.SimpleHTTPRequestHandler):
      def __init__(self, *args, **kwargs):
          super().__init__(*args, directory=mail_location, **kwargs)

    def serve_forever(httpd):
      with httpd:
        print("serving at port", http_port)
        httpd.serve_forever()

    httpd = socketserver.TCPServer(("", http_port), Handler)
    thread = Thread(target=serve_forever, args=(httpd, ))
    thread.setDaemon(True)
    thread.start()

    super().__init__()

  def send_order_confirmation(self, request, context):
    logger.info('A request to send order confirmation email to {} has been received.'.format(request.email))

    order = request.order
    try:
      confirmation = template.render(order = order)
    except TemplateError as err:
      context.set_details("An error occurred when preparing the confirmation mail.")
      logger.error(err.message)
      context.set_code(grpc.StatusCode.INTERNAL)
      return demo_pb2.Empty()

    mail_filename = f"{order.order_id}.html"
    with open(os.path.join(self.mail_location, mail_filename), "w") as f:
      f.write(confirmation)

    paths = sorted(Path(self.mail_location).iterdir(), key=os.path.getmtime) 
    for expired_mail in paths[self.max_mails:]:
      os.remove(expired_mail)

    return demo_pb2.Empty()

class HealthCheck():
  def Check(self, request, context):
    return health_pb2.HealthCheckResponse(
      status=health_pb2.HealthCheckResponse.SERVING)

  def Watch(self, request, context):
    return health_pb2.HealthCheckResponse(
      status=health_pb2.HealthCheckResponse.UNIMPLEMENTED)

class Killer:
    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

        self.shutdown_signal = False

    def exit_gracefully(self, signal_no, stack_frame):
        self.shutdown_signal = True
        raise SystemExit

def start(dummy_mode):
  service = None
  if dummy_mode:
    http_port = int(os.environ.get('MAIL_HTTP_PORT', "8081"))
    service = DummyEmailService(http_port=http_port)
  else:
    raise Exception('non-dummy mode not implemented yet')

  # health check server
  server = grpc.server(futures.ThreadPoolExecutor(max_workers=10),)
  health_pb2_grpc.add_HealthServicer_to_server(HealthCheck(), server)
  port = os.environ.get('PORT', "8080")
  logger.info("listening on port: "+port)
  server.add_insecure_port('[::]:'+port)
  server.start()

  # recive SendOrderConfirmation requests from Kafka
  addr = os.getenv("EMAIL_KAFKA_ADDR", "kafka:9092")
  topic = os.getenv("EMAIL_KAFKA_TOPIC", "order-confirmation")
  group = os.getenv("EMAIL_KAFKA_GROUP", "emailservice")

  consumer = KafkaConsumer(topic, bootstrap_servers=addr, group_id=group)
  killer = Killer()
  while not killer.shutdown_signal:
    try:
      for msg in consumer:
        send_order_confirmation = demo_pb2.SendOrderConfirmationRequest()
        send_order_confirmation = Parse(msg.value, send_order_confirmation, ignore_unknown_fields=True)
        service.send_order_confirmation(send_order_confirmation, None)
    except SystemExit:
      logger.info('shutting down...')
    finally:
      consumer.close()
      server.stop(0)

def initStackdriverProfiling():
  project_id = None
  try:
    project_id = os.environ["GCP_PROJECT_ID"]
  except KeyError:
    # Environment variable not set
    pass

  for retry in range(1,4):
    try:
      if project_id:
        googlecloudprofiler.start(service='email_server', service_version='1.0.0', verbose=0, project_id=project_id)
      else:
        googlecloudprofiler.start(service='email_server', service_version='1.0.0', verbose=0)
      logger.info("Successfully started Stackdriver Profiler.")
      return
    except (BaseException) as exc:
      logger.info("Unable to start Stackdriver Profiler Python agent. " + str(exc))
      if (retry < 4):
        logger.info("Sleeping %d to retry initializing Stackdriver Profiler"%(retry*10))
        time.sleep (1)
      else:
        logger.warning("Could not initialize Stackdriver Profiler after retrying, giving up")
  return


if __name__ == '__main__':
  logger.info('starting the email service in dummy mode.')

  # Profiler
  try:
    if "DISABLE_PROFILER" in os.environ:
      raise KeyError()
    else:
      logger.info("Profiler enabled.")
      initStackdriverProfiling()
  except KeyError:
      logger.info("Profiler disabled.")

  # Tracing
  try:
    if os.environ["ENABLE_TRACING"] == "1":
      otel_endpoint = os.getenv("COLLECTOR_SERVICE_ADDR", "localhost:4317")
      trace.set_tracer_provider(TracerProvider())
      trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
            endpoint = otel_endpoint,
            insecure = True
          )
        )
      )

  except (KeyError, DefaultCredentialsError):
      logger.info("Tracing disabled.")
  except Exception as e:
      logger.warn(f"Exception on Cloud Trace setup: {traceback.format_exc()}, tracing disabled.") 

  start(dummy_mode = True)
