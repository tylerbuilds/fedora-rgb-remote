import importlib.util,json,threading,unittest,urllib.request,urllib.error
from unittest.mock import patch
from pathlib import Path
spec=importlib.util.spec_from_file_location('remote',Path(__file__).resolve().parents[1]/'server.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class RemoteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=m.Server(('127.0.0.1',0),m.Handler)
        m.PORT=cls.server.server_port
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def request(self,data=None,headers=None):
        url=f'http://127.0.0.1:{m.PORT}/api'
        req=urllib.request.Request(url,data=data,headers=headers or {})
        try:
            with urllib.request.urlopen(req,timeout=2) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:
            with e:return e.code,json.load(e)
    def headers(self):return {'Origin':f'http://127.0.0.1:{m.PORT}','X-RGB-CSRF':m.CSRF,'Content-Type':'application/json'}
    def test_missing_csrf_cannot_reach_hardware(self):
        with patch.object(m,'command') as hw:
            self.assertEqual(self.request(b'{"action":"off"}')[0],403);hw.assert_not_called()
    def test_bad_host_rejected(self):self.assertEqual(self.request(headers={'Host':'attacker.example'})[0],403)
    def test_invalid_requests_cannot_reach_hardware(self):
        with patch.object(m,'command') as hw:
            for body in [b'[]',b'{"action":"scan"}',b'{"action":"colour","colour":"bad"}',b'x'*512]:
                self.assertEqual(self.request(body,self.headers())[0],400)
            hw.assert_not_called()
    def test_on_off_and_colour_are_only_reviewed_commands(self):
        with patch.object(m,'command',return_value='') as hw,patch.object(m,'persist_colour'):
            for action,colour in [('off',None),('on',None),('colour','#123456')]:
                self.assertEqual(self.request(json.dumps({'action':action,'colour':colour}).encode(),self.headers())[0],200)
            for call in hw.call_args_list:
                args=call.args[0]
                self.assertNotIn('--save-profile',args);self.assertNotIn('--save',args)
                self.assertEqual(args[args.index('--mode')+1],'Static')
            self.assertIn('000000',hw.call_args_list[0].args[0])
    def test_unapproved_binary_rejected_before_subprocess(self):
        with patch.object(m.Path,'read_bytes',return_value=b'unapproved'),patch.object(m.subprocess,'run') as run:
            with self.assertRaises(RuntimeError):m.command([])
            run.assert_not_called()
if __name__=='__main__':unittest.main()
