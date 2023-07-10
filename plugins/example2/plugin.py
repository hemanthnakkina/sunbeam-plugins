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
import shutil
from pathlib import Path
from typing import Optional

import click
from packaging.version import Version
from rich.console import Console
from rich.status import Status
from snaphelpers import Snap

from sunbeam.clusterd.client import Client
from sunbeam.clusterd.service import ConfigItemNotFoundException
from sunbeam.commands.juju import JujuStepHelper
from sunbeam.commands.openstack import (
    OPENSTACK_MODEL,
    determine_target_topology_at_bootstrap,
)
from sunbeam.commands.terraform import (
    TerraformException,
    TerraformHelper,
    TerraformInitStep,
)
from sunbeam.jobs.common import (
    BaseStep,
    Result,
    ResultType,
    read_config,
    run_plan,
    update_config,
)
from sunbeam.jobs.juju import JujuHelper, JujuWaitException, TimeoutException, run_sync
from sunbeam.plugins.interface.v1.base import EnableDisablePlugin

LOG = logging.getLogger(__name__)
console = Console()

APPLICATION_DEPLOY_TIMEOUT = 1200  # 15 minutes
CONFIG_KEY = "TerraformVarsOpenstackCP"


class EnableOpenstackCPApplicationStep(BaseStep, JujuStepHelper):
    """Enable OpenStack Heat application using Terraform"""

    _CONFIG = CONFIG_KEY

    def __init__(
        self,
        tfhelper: TerraformHelper,
        jhelper: JujuHelper,
    ):
        super().__init__("Enable OpenStack Heat", "Enabling OpenStack Heat application")
        self.tfhelper = tfhelper
        self.jhelper = jhelper
        self.model = OPENSTACK_MODEL
        self.client = Client()

    def has_prompts(self) -> bool:
        """Returns true if the step has prompts that it can ask the user."""
        return False

    def is_skip(self, status: Optional[Status] = None) -> Result:
        """Determines if the step should be skipped or not.

        :return: ResultType.SKIPPED if the Step should be skipped,
                ResultType.COMPLETED or ResultType.FAILED otherwise
        """
        return Result(ResultType.COMPLETED)

    def run(self, status: Optional[Status] = None) -> Result:
        """Apply terraform configuration to deploy openstack heat"""
        database = determine_target_topology_at_bootstrap()

        try:
            tfvars = read_config(self.client, self._CONFIG)
        except ConfigItemNotFoundException:
            tfvars = {}
        tfvars.update(
            {
                "model": self.model,
                "openstack-channel": "2023.1/edge",
                "many-mysql": database == "multi",
                "enable-openstackcp": True,
            }
        )
        update_config(self.client, self._CONFIG, tfvars)
        self.tfhelper.write_tfvars(tfvars)

        try:
            self.tfhelper.apply()
        except TerraformException as e:
            return Result(ResultType.FAILED, str(e))

        apps = ["openstackcp", "openstackcp-mysql-router"]
        if database == "multi":
            apps.append("openstackcp-mysql")

        LOG.debug(f"Application monitored for readiness: {apps}")
        try:
            run_sync(
                self.jhelper.wait_until_active(
                    self.model,
                    apps,
                    timeout=APPLICATION_DEPLOY_TIMEOUT,
                )
            )
        except (JujuWaitException, TimeoutException) as e:
            LOG.warning(str(e))
            return Result(ResultType.FAILED, str(e))

        return Result(ResultType.COMPLETED)


class DisableOpenstackCPApplicationStep(BaseStep, JujuStepHelper):
    """Disable OpenStack Heat application using Terraform"""

    _CONFIG = CONFIG_KEY

    def __init__(
        self,
        tfhelper: TerraformHelper,
        jhelper: JujuHelper,
    ):
        super().__init__(
            "Disable OpenStack Heat", "Removing OpenStack Heat application"
        )
        self.tfhelper = tfhelper
        self.jhelper = jhelper
        self.model = OPENSTACK_MODEL
        self.client = Client()

    def has_prompts(self) -> bool:
        """Returns true if the step has prompts that it can ask the user."""
        return False

    def is_skip(self, status: Optional[Status] = None) -> Result:
        """Determines if the step should be skipped or not.

        :return: ResultType.SKIPPED if the Step should be skipped,
                ResultType.COMPLETED or ResultType.FAILED otherwise
        """
        return Result(ResultType.COMPLETED)

    def run(self, status: Optional[Status] = None) -> Result:
        """Apply terraform configuration to disable openstack heat"""
        database = determine_target_topology_at_bootstrap()

        tfvars = read_config(self.client, self._CONFIG)
        tfvars.update({"enable-openstackcp": False})
        update_config(self.client, self._CONFIG, tfvars)
        self.tfhelper.write_tfvars(tfvars)

        try:
            self.tfhelper.apply()
        except TerraformException as e:
            return Result(ResultType.FAILED, str(e))

        apps = ["openstackcp", "openstackcp-mysql-router"]
        if database == "multi":
            apps.append("openstackcp-mysql")

        # TODO(hemanth): Logic to check applicaitons are deleted
        """
        LOG.debug(f"Application monitored for readiness: {apps}")
        try:
            run_sync(
                self.jhelper.wait_until_active(
                    self.model,
                    apps,
                    timeout=APPLICATION_DEPLOY_TIMEOUT,
                )
            )
        except (JujuWaitException, TimeoutException) as e:
            LOG.warning(str(e))
            return Result(ResultType.FAILED, str(e))
        """

        return Result(ResultType.COMPLETED)


class OpenstackCPPlugin(EnableDisablePlugin):
    version = Version("0.0.1")

    def __init__(self) -> None:
        super().__init__(name="openstackcp")
        self.snap = Snap()
        self.tfplan = f"deploy-{self.name}"

    def pre_enable(self):
        src = Path(__file__).parent / "etc" / self.tfplan
        dst = self.snap.paths.user_common / "etc" / self.tfplan
        LOG.debug(f"Updating {dst} from {src}...")
        shutil.copytree(src, dst, dirs_exist_ok=True)

    def run_enable_plans(self):
        data_location = self.snap.paths.user_data
        tfhelper = TerraformHelper(
            path=self.snap.paths.user_common / "etc" / self.tfplan,
            plan="openstackcp-plan",
            backend="http",
            data_location=data_location,
        )
        jhelper = JujuHelper(data_location)
        plan = [
            TerraformInitStep(tfhelper),
            EnableOpenstackCPApplicationStep(tfhelper, jhelper),
        ]

        run_plan(plan, console)
        click.echo("OpenStack Test application enabled.")

    def pre_disable(self):
        self.pre_enable()

    def run_disable_plans(self):
        data_location = self.snap.paths.user_data
        tfhelper = TerraformHelper(
            path=self.snap.paths.user_common / "etc" / self.tfplan,
            plan="openstackcp-plan",
            backend="http",
            data_location=data_location,
        )
        jhelper = JujuHelper(data_location)
        plan = [
            TerraformInitStep(tfhelper),
            DisableOpenstackCPApplicationStep(tfhelper, jhelper),
        ]

        run_plan(plan, console)
        click.echo("OpenStack Test application disabled.")

    @click.command()
    def enable_plugin(self) -> None:
        """Enable OpenStack Test application."""
        super().enable_plugin()

    @click.command()
    def disable_plugin(self) -> None:
        """Disable OpenStack Test application."""
        super().disable_plugin()
