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

terraform {

  required_providers {
    juju = {
      source  = "juju/juju"
      version = ">= 0.7.0"
    }
  }

}

provider "juju" {}

data "juju_model" "sunbeam" {
  name = var.model
}

module "mysql" {
  count      = var.enable-openstackcp ? (var.many-mysql ? 1 : 0) : 0
  source     = "/home/ubuntu/snap/openstack/common/etc/deploy-openstack/modules/mysql"
  model      = data.juju_model.sunbeam.name
  name       = "mysql"
  channel    = var.mysql-channel
  scale      = var.ha-scale
  many-mysql = var.many-mysql
  services   = ["openstackcp"]
}

module "heat" {
  count                = var.enable-openstackcp ? 1 : 0
  source               = "/home/ubuntu/snap/openstack/common/etc/deploy-openstack/modules/openstack-api"
  charm                = "glance-k8s"
  name                 = "openstackcp"
  model                = data.juju_model.sunbeam.name
  channel              = var.openstack-channel
  rabbitmq             = "rabbitmq"
  mysql                = var.many-mysql ? module.mysql[0].name["openstackcp"] : "mysql"
  keystone             = "keystone"
  ingress-internal     = "traefik"
  ingress-public       = "traefik"
  scale                = var.os-api-scale
  mysql-router-channel = var.mysql-router-channel
}
