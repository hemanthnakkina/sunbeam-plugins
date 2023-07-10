# Copyright (c) 2023 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

import click
from packaging.version import Version

from sunbeam.commands.openstack import OPENSTACK_MODEL
from sunbeam.plugins.interface.v1.openstack import (
    TERRAFORM_PLAN_LOCATION,
    OpenStackControlPlanePlugin,
)

LOG = logging.getLogger(__name__)


class OpenstackCPPlugin(OpenStackControlPlanePlugin):
    version = Version("0.0.1")

    def __init__(self) -> None:
        super().__init__(
            name="openstackcp", tf_plan_location=TERRAFORM_PLAN_LOCATION.PLUGIN_REPO
        )

    def set_application_names(self) -> list:
        """Application names handled by the terraform plan."""
        apps = ["openstackcp", "openstackcp-mysql-router"]
        if self.get_database_topology() == "multi":
            apps.append("openstackcp-mysql")

    def set_tfvars_on_enable(self) -> dict:
        """Set terraform variables to enable the application."""
        return {
            "model": OPENSTACK_MODEL,
            "openstack-channel": "2023.1/edge",
            "many-mysql": self.get_database_topology() == "multi",
            "enable-openstackcp": True,
        }

    def set_tfvars_on_disable(self) -> dict:
        """Set terraform variables to disable the application."""
        return {"enable-openstackcp": False}

    def set_tfvars_on_resize(self) -> dict:
        """Set terraform variables to resize the application."""
        return {}

    @click.command()
    def enable_plugin(self) -> None:
        """Enable OpenStack Test application."""
        super().enable_plugin()

    @click.command()
    def disable_plugin(self) -> None:
        """Disable OpenStack Test application."""
        super().disable_plugin()
