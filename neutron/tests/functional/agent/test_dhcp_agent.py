# Copyright (c) 2014 Red Hat, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock
from oslo.config import cfg

from neutron.agent.common import config
from neutron.agent import dhcp_agent
from neutron.agent.linux import dhcp
from neutron.agent.linux import ovs_lib
from neutron.agent.linux import ip_lib
from neutron.common import utils as commonutils
from neutron.openstack.common import uuidutils
from neutron.tests.functional.agent.linux import base
from neutron.tests.functional.agent.linux import pinger

class DHCPAgentTestFramework(base.BaseOVSLinuxTestCase):

    TEST_MAC_ADDRESS = '24:77:03:7d:00:4c'
    TEST_IP_ADDRESS = '192.168.10.11'

    def setUp(self):
        super(DHCPAgentTestFramework, self).setUp()
        #donno if needed yet
        #self.check_sudo_enabled()
        self._configure()

    def _configure(self):
        dhcp_agent.register_options()
        cfg.CONF.set_override('debug', False)
        config.setup_logging()
        cfg.CONF.set_override(
            'interface_driver',
            'neutron.agent.linux.interface.OVSInterfaceDriver')
        cfg.CONF.set_override('ovs_use_veth', False)
        cfg.CONF.set_override('root_helper', self.root_helper, group='AGENT')
        cfg.CONF.set_override('use_namespaces', True)
        import pdb;pdb.set_trace()
        br_int = self.create_ovs_bridge()
        cfg.CONF.set_override('ovs_integration_bridge', br_int.br_name)
        self.agent = dhcp_agent.DhcpAgentWithStateReport('localhost')
        self.agent_manager = dhcp.DeviceManager(cfg.CONF, cfg.CONF.root_helper,
                                                mock.Mock())
        self.ovs = ovs_lib.BaseOVS(self.root_helper)

    def _create_network_dict(self, net_id, subnets=[], ports=[]):
        net_dict = dhcp.NetModel(True, {"id": net_id,
                                        "subnets": subnets,
                                        "ports": ports,
                                        "admin_state_up": True,
                                        "tenant_id": uuidutils.generate_uuid()})

    def _create_subnet_dict(self, net_id, enable_dhcp=True):
        sn_id = uuidutils.generate_uuid()
        sn_dict = dhcp.DictModel({"id": sn_id,
                            "network_id": net_id,
                            "ip_version": 4,
                            "cidr": '192.168.10.0/24',
                            "gateway_ip": '192.168.10.1',
                            "enable_dhcp": True,
                            "dns_nameservers": [],
                            "host_routes": []})
        return sn_dict

    def _create_port_dict(self, net_id):
        port_id = uuidutils.generate_uuid()
        device_id = commonutils.get_dhcp_agent_device_id(net_id, cfg.CONF.host)
        port_dict = dhcp.DictModel({"id": port_id,
                            "name": "foo",
                            "mac_address": self.TEST_MAC_ADDRESS,
                            "network_id": net_id,
                            "admin_state_up": True,
                            "device_id": device_id,
                            "device_owner": "foo",
                            "fixed_ips": [{"subnet_id": sn_id,
                                            "ip_address":
                                                    self.TEST_IP_ADDRESS}]})
        return port_dict

    def network_dict_for_dhcp(self, enable_dhcp=True):
        net_id = uuidutils.generate_uuid()
        sn_dict = self._create_subnet_dict(net_id, enable_dhcp)
        port_dict = self._create_port_dict(net_id)
        net_dict = self._create_net_dict(net_id, [sn_dict], [port_dict])
        return net_dict

    def configure_dhcp_for_network(self, network):
        self.agent.configure_dhcp_for_network(network)

    def assert_dhcp_interface_created(self, network, port)):
        dhcp_iface_name = self.agent_manager.get_interface_name(
                                                        network, port)
        self.assertTrue(self.ovs.port_exists(dhcp_iface_name))

    def assert_dhcp_namespace_created(self, namespace):
        ip = ip_lib.IPWrapper(self.root_helper, namespace)
        self.assertTrue(ip.netns.exists(namespace))

    def assert_dhcp_device_created(self, namespace):
        dev = ip_lib.IPDevice(dhcp_iface_name, self.root_helper, namespace)
        self.assertEqual(self.TEST_MAC_ADDRESS, dev.link.address)
        self.assertTrue(ip_lib.ensure_device_is_ready(dhcp_iface_name,
                                        self.root_helper, net_dict.namespace))

    def assert_ping_dhcp(self, namespace):
        pingy = pinger.Pinger(self)
        pingy.assert_ping_from_ns(namespace, self.TEST_IP_ADDRESS)

class DHCPAgentTestCase(DHCPAgentTestFramework):
    def test_create_subnet_with_dhcp(self):
        network = self.network_dict_for_dhcp()
        port = network.ports[0]
        self.configure_dhcp_for_network(network)
        self.assert_dhcp_interface_created(network, port)
        self.assert_dhcp_namespace_created(network.namespace)
        self.assert_dhcp_device_created(network.namespace)
        self.assert_ping_dhcp(network.namespace)

    def test_create_subnet_without_dhcp(self):

        #check if dhcp agent was started for subnet
        #check allocation ranges
        #dhcping?
