import http.client
import json
import socket
import tempfile
import threading
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from cwmp import CwmpEngine, CwmpServers, SOAP, local
from controller import Manager, USER1, PASS1, WAN_TELNET, PERIOD, INFORM_ENABLE, numeric_nv
from network_services import allowed_dns, ntp_reply, EthernetServices

ROOT=Path(__file__).resolve().parent

def soap(engine, method, contents='', ident='cpe-test'):
    root,node=engine.envelope(method,ident)
    if contents:
        fragment=ET.fromstring('<fragment>'+contents+'</fragment>');node.extend(fragment)
    return ET.tostring(root)

def method(data):
    return local(ET.fromstring(data).find(f'{{{SOAP}}}Body')[0].tag)

class TemporaryTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT,prefix='app-test-')
    def tearDown(self):
        assert Path(self.temp.name).resolve().is_relative_to(ROOT)
        self.temp.cleanup()

class CwmpTests(TemporaryTest):
    def setUp(self):
        super().setUp();self.engine=CwmpEngine(peer='127.0.0.1')

    def inform(self):
        return self.engine.handle(soap(self.engine,'Inform','<DeviceId><Manufacturer>ZTE</Manufacturer><ProductClass>MF297D</ProductClass><SerialNumber>TEST-DEVICE</SerialNumber></DeviceId>'))

    def test_device_and_boolean_value_parsing(self):
        self.assertEqual(method(self.inform()),'InformResponse')
        rpc=self.engine.submit('GetParameterValues',['test.Enable'])
        self.assertEqual(method(self.engine.handle(b'')),'GetParameterValues')
        reply=soap(self.engine,'GetParameterValuesResponse','<ParameterList><ParameterValueStruct><Name>test.Enable</Name><Value>0</Value></ParameterValueStruct></ParameterList>',rpc.ident)
        self.engine.handle(reply)
        self.assertTrue(rpc.event.is_set());self.assertEqual(rpc.result,{'test.Enable':'0'})

    def test_wrong_device_and_wrong_rpc_id_rejected(self):
        with self.assertRaises(PermissionError):
            self.engine.handle(soap(self.engine,'Inform','<DeviceId><Manufacturer>Other</Manufacturer><ProductClass>OTHER</ProductClass><SerialNumber>X</SerialNumber></DeviceId>'))
        self.inform();self.engine.submit('GetRPCMethods');self.engine.handle(b'')
        with self.assertRaises(ValueError):self.engine.handle(soap(self.engine,'GetRPCMethodsResponse','<MethodList/>','wrong'))

    def test_rpc_timeout_cancels_unsent_write(self):
        with self.assertRaises(TimeoutError):
            self.engine.call('SetParameterValues',{WAN_TELNET:('1','xsd:boolean')},timeout=0.01)
        self.assertFalse(self.engine.queue)
        self.assertEqual(self.engine.handle(b''),b'')

    def test_firmware_and_reset_rpc_are_not_supported(self):
        for name in ('Download','FactoryReset','Reboot','ExecuteCommand'):
            with self.assertRaises(ValueError):self.engine.submit(name,{})

    def test_http_upload_is_token_scoped_and_exact(self):
        servers=CwmpServers(self.engine,'127.0.0.1',self.temp.name,http_port=0,https_port=None)
        servers.start();port=servers.servers[0].server_address[1]
        try:
            token,ticket=self.engine.upload_ticket(Path(self.temp.name)/'backup.CFG')
            conn=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
            conn.request('PUT','/upload/wrong',b'bad');r=conn.getresponse();self.assertEqual(r.status,403);r.read();conn.close()
            conn=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
            conn.request('PUT','/upload/'+token,b'telnet_lan_enable=1\n');r=conn.getresponse();self.assertEqual(r.status,201);r.read();conn.close()
            self.assertTrue(ticket['event'].wait(1));self.assertEqual(ticket['bytes'],20)
            conn=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
            conn.request('PUT','/upload/'+token,b'telnet_lan_enable=1\n');r=conn.getresponse();self.assertEqual(r.status,201);r.read();conn.close()
            self.assertEqual(ticket['error'],'')
        finally:servers.stop()

class PacketTests(unittest.TestCase):
    def test_dns_is_limited_to_acs_and_ntp(self):
        for name in ['acs.superonline.net.','CPENTP.SUPERONLINE.NET','europe.pool.ntp.org']:
            self.assertTrue(allowed_dns(name))
        for name in ['accounts.google.com','app.notion.com','acs.superonline.net.attacker.test','localhost']:
            self.assertFalse(allowed_dns(name))

    def test_ntp_echoes_origin_timestamp(self):
        request=bytearray(48);request[0]=0x23;request[40:48]=b'12345678'
        reply=ntp_reply(request,now=1700000000)
        self.assertEqual(len(reply),48);self.assertEqual(reply[24:32],b'12345678');self.assertEqual(reply[0]&7,4)
        self.assertIsNone(ntp_reply(b'short'))

    def test_wrong_nic_source_and_other_client_are_not_answered(self):
        from scapy.layers.l2 import Ether
        from scapy.layers.inet import IP,UDP
        from scapy.layers.dns import DNS,DNSQR
        service=EthernetServices('Test','00:11:22:33:44:55')
        service.interface='test'
        request=lambda mac,ip,name:Ether(src=mac)/IP(src=ip,dst='1.1.1.1')/UDP(sport=50000,dport=53)/DNS(id=1,qd=DNSQR(qname=name))
        with patch('scapy.sendrecv.sendp') as send:
            service._handle(request('aa:bb:cc:dd:ee:ff','192.168.5.240','acs.superonline.net'));send.assert_not_called()
            service._handle(request('aa:bb:cc:dd:ee:ff','192.168.50.2','accounts.google.com'));send.assert_not_called()
            service._handle(request('aa:bb:cc:dd:ee:ff','192.168.50.2','acs.superonline.net'));self.assertEqual(send.call_count,1)
            service._handle(request('aa:bb:cc:dd:ee:00','192.168.50.2','acs.superonline.net'));self.assertEqual(send.call_count,1)

class FakeEngine:
    device={'serial':'TEST'}
    def __init__(self,username='sUser'):self.username=username;self.calls=[]
    def call(self,method,args,timeout=0):
        self.calls.append((method,args))
        if method=='GetParameterValues':return {USER1:self.username,PERIOD:'3600',INFORM_ENABLE:'1',WAN_TELNET:'0'}
        return {'status':'0'}

class RootClient:
    commands=[]
    def __init__(self,*args,**kwargs):pass
    def login(self,*args):return 'uid=0(root)'
    def command(self,command):
        self.commands.append(command)
        if command=='nv get telnet_lan_enable':return '\n1\n',0
        return '',0
    def close(self):pass

class ControllerTests(TemporaryTest):
    def manager(self):
        manager=Manager(self.temp.name);manager.engine=FakeEngine();manager.ready=True
        manager.original_period='3600';manager.original_inform_enable='1'
        return manager

    def test_success_closes_wan_and_keeps_recovery_record(self):
        manager=self.manager()
        with patch('controller.TelnetClient',RootClient):manager.provision('SyntheticPass123!',True)
        writes=[args for meth,args in manager.engine.calls if meth=='SetParameterValues']
        self.assertIn(PASS1,writes[0]);self.assertEqual(writes[0][WAN_TELNET][0],'1');self.assertEqual(writes[-1][WAN_TELNET][0],'0')
        self.assertFalse(manager.wan_pending)
        record=json.loads(manager.cleanup_file.read_text());self.assertFalse(record['wan_telnet_pending']);self.assertNotIn('SyntheticPass123!',manager.cleanup_file.read_text())

    def test_root_auth_failure_still_closes_wan(self):
        manager=self.manager()
        class BadClient(RootClient):
            def login(self,*args):raise PermissionError('Rejected')
        with patch('controller.TelnetClient',BadClient),patch('controller.time.sleep'):
            with self.assertRaises(RuntimeError):manager.provision('SyntheticPass123!',False)
        writes=[args for meth,args in manager.engine.calls if meth=='SetParameterValues']
        self.assertNotIn(PASS1,writes[0]);self.assertEqual(writes[-1][WAN_TELNET][0],'0');self.assertFalse(manager.wan_pending)

    def test_wrong_account_prevents_password_write(self):
        manager=self.manager();manager.ready=False;manager.engine=FakeEngine(username='admin');manager._bootstrap()
        self.assertFalse(manager.ready);self.assertEqual([m for m,a in manager.engine.calls],['GetParameterValues'])

    def test_nv_parser_does_not_accept_an_echoed_setting(self):
        self.assertFalse(numeric_nv('nv set telnet_lan_enable=1\nroot#',1));self.assertTrue(numeric_nv('nv get telnet_lan_enable\r\n1\r\nroot#',1))

    def test_busy_port_does_not_change_or_snapshot_nic(self):
        manager=Manager(self.temp.name)
        with patch('controller.windows_net.is_admin',return_value=True),patch('controller.socket.socket') as socket_mock,patch('controller.windows_net.snapshot') as snapshot,patch('controller.windows_net.set_ipv4') as change:
            socket_mock.return_value.bind.side_effect=OSError('busy')
            with self.assertRaises(RuntimeError):manager.start({'Name':'Test','MacAddress':'00-11-22-33-44-55'})
            snapshot.assert_not_called();change.assert_not_called()

    def test_failed_wan_cleanup_is_not_reported_as_success(self):
        manager=self.manager()
        old=manager.engine.call
        def call(method,args,timeout=0):
            if method=='SetParameterValues' and args.get(WAN_TELNET,())[0]=='0':raise TimeoutError('offline')
            return old(method,args,timeout)
        manager.engine.call=call
        with patch('controller.TelnetClient',RootClient):
            with self.assertRaisesRegex(RuntimeError,'WAN Telnet kapatma'):manager.provision('SyntheticPass123!',True)
        self.assertTrue(manager.wan_pending)
        self.assertTrue(json.loads(manager.cleanup_file.read_text())['wan_telnet_pending'])

    def test_wrong_adapter_cannot_replace_saved_network_recovery(self):
        saved={'name':'Original','mac':'AA-AA-AA-AA-AA-AA','index':1,'dhcp':True,'addresses':[],'gateway':None}
        path=Path(self.temp.name)/'original-network.json';path.write_text(json.dumps(saved))
        manager=Manager(self.temp.name)
        candidate=dict(saved,mac='BB-BB-BB-BB-BB-BB')
        with patch('controller.windows_net.is_admin',return_value=True),patch('controller.socket.socket'),patch('controller.EthernetServices.find_interface'),patch('controller.windows_net.snapshot',return_value=candidate):
            with self.assertRaises(RuntimeError):manager.start({'Name':'Wrong','MacAddress':candidate['mac']})
        self.assertEqual(manager.original_network['mac'],saved['mac']);self.assertEqual(json.loads(path.read_text()),saved)

if __name__=='__main__':unittest.main(verbosity=2)
