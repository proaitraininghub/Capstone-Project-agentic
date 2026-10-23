"""
agent_setup.py  --  BUILD THE AGENT (used by the Celery WORKER only)
====================================================================
The same client + agent you built in the course. It lives here, in the worker,
because ONLY the worker talks to the model. The API never imports this file,
so the API starts fast and stays small.
"""
import os

from azure.identity import AzureCliCredential, ManagedIdentityCredential
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework.openai import OpenAIChatClient

from tools import get_city_facts, search_wikipedia

USE_OPENAI = os.environ.get("USE_OPENAI", "false").lower() == "true"
RUNNING_IN_AZURE = os.environ.get("RUNNING_IN_AZURE", "false").lower() == "true"

_credential = None


def get_credential():
    """One credential object per worker process, so its login token is reused
    instead of being requested again for every single chat."""
    global _credential
    if _credential is None:
        if RUNNING_IN_AZURE:
            # In Azure: the app's MANAGED IDENTITY logs in. No keys, no passwords.
            _credential = ManagedIdentityCredential(client_id=os.environ.get("AZURE_CLIENT_ID"))
        else:
            # On your laptop: use the account you signed in with using az login
            _credential = AzureCliCredential()
    return _credential


def build_agent():
    if USE_OPENAI:
        client = OpenAIChatClient(api_key=os.environ["OPENAI_API_KEY"], model=os.environ["OPENAI_MODEL"])
    else:
        client = FoundryChatClient(
            project_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
            credential=get_credential(),
        )
    return Agent(
        client=client,
        name="TravelBuddy",
        instructions=(
            "You are Travel Buddy, a friendly travel helper. "
            "For cities we have saved, use get_city_facts. "
            "For anything else, use search_wikipedia. "
            "Never guess. Answer in two or three sentences."
        ),
        tools=[get_city_facts, search_wikipedia],
    )


def setup_monitoring(default_service_name):
    """Send traces and metrics to Application Insights (only when a connection string exists)."""
    if not os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        return
    os.environ.setdefault("OTEL_SERVICE_NAME", default_service_name)

    # IMPORTANT: stop a logging loop. The Azure Monitor sender writes a log line for every
    # request it sends. If those lines are INFO level and get captured and sent again, the
    # worker sends telemetry about its own telemetry, forever. Keep Azure libraries at WARNING.
    import logging
    for name in ("azure", "azure.core.pipeline.policies.http_logging_policy",
                 "azure.monitor.opentelemetry.exporter"):
        logging.getLogger(name).setLevel(logging.WARNING)

    from azure.monitor.opentelemetry import configure_azure_monitor
    from agent_framework.observability import create_resource, enable_instrumentation

    configure_azure_monitor(
        connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"],
        resource=create_resource(),
    )
    enable_instrumentation()
