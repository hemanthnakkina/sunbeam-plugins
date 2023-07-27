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

import click
from packaging.version import Version

from sunbeam.plugins.interface.v1.base import EnableDisablePlugin


class TestPlugin(EnableDisablePlugin):
    version = Version("0.0.1")

    def __init__(self) -> None:
        self.name = "test"
        super().__init__(self.name)

    def run_enable_plans(self):
        click.echo(f"Test plugin enabled")

    def run_disable_plans(self):
        click.echo(f"Test plugin disabled")

    @click.command()
    def enable_plugin(self):
        """Enable Test."""
        super().enable_plugin()

    @click.command()
    def disable_plugin(self):
        """Disable Test."""
        super().disable_plugin()
