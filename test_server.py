import tempfile, os, subprocess, time, urllib.request, urllib.error, json, sys
from pathlib import Path
root=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as tmp:
    env={**os.environ,'THUMBNAIL_LAB_DB':tmp+'/test.sqlite3','THUMBNAIL_LAB_PORT':'18769'}
    process=subprocess.Popen([sys.executable,str(root/'server.py')],env=env,stdout=subprocess.DEVNULL)
    def request(path='/api/state',data=None,origin=None):
        headers={'X-Thumbnail-Lab':'1','Content-Type':'application/json'}
        if origin: headers['Origin']=origin
        req=urllib.request.Request('http://127.0.0.1:18769'+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=2) as result: return result.status,result.read()
        except urllib.error.HTTPError as error: return error.code,error.read()
    try:
        for _ in range(30):
            try:
                if request()[0]==200:break
            except OSError:time.sleep(.1)
        assert json.loads(request()[1])['version']==0
        state={'channels':[{'id':'test','name':'テスト','refs':[],'batches':[]}],'active':'test'}
        assert request(data={'version':0,'data':state})[0]==200
        assert json.loads(request()[1])['data']==state
        assert request(data={'version':0,'data':state})[0]==409
        assert request(data={'version':1,'data':state},origin='https://example.com')[0]==403
        assert request('/../server.py')[0]==404
        assert request('/')[0]==200
        print('PASS: persistence, stale update rejection, origin guard, path isolation, HTML response')
    finally:
        process.terminate();process.wait(timeout=5)
