"""Adapter factory — creates the right adapter implementation from configuration."""

import os

from azure.identity import DefaultAzureCredential

from .arc_adapter import ArcAdapter
from .defender_adapter import DefenderAdapter
from .glpi_adapter import GlpiAdapter
from .patch_adapter import PatchAdapter


def get_arc_adapter() -> ArcAdapter:
    credential = DefaultAzureCredential()
    subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
    return ArcAdapter(credential=credential, subscription_id=subscription_id)


def get_defender_adapter() -> DefenderAdapter:
    credential = DefaultAzureCredential()
    subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
    return DefenderAdapter(credential=credential, subscription_id=subscription_id)


def get_itsm_adapter() -> GlpiAdapter:
    return GlpiAdapter(
        base_url=os.environ["GLPI_BASE_URL"],
        app_token=os.environ["GLPI_APP_TOKEN"],
        user_token=os.environ["GLPI_USER_TOKEN"],
    )


def get_cmdb_adapter() -> GlpiAdapter:
    return get_itsm_adapter()


def get_patch_adapter() -> PatchAdapter:
    credential = DefaultAzureCredential()
    subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
    return PatchAdapter(credential=credential, subscription_id=subscription_id)
