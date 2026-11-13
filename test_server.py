import tempfile, os, subprocess, time, urllib.request, urllib.error, json, sys, base64
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
        helper=root/'skills/thumbnail-lab/scripts/library.py'
        image=Path(tmp)/'pixel.png'
        image.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jA1sAAAAASUVORK5CYII='))
        command=[sys.executable,str(helper),'--url','http://127.0.0.1:18769']
        result=subprocess.run(command+['list'],capture_output=True,text=True,check=True)
        assert json.loads(result.stdout)[0]['id']=='test'
        args=['import','--channel','test','--batch-id','agent-test','--topic','自動登録テスト','--images']+[str(image)]*5
        subprocess.run(command+args,capture_output=True,text=True,check=True)
        saved=json.loads(request()[1])['data']['channels'][0]
        assert len(saved['batches'])==1 and len(saved['batches'][0]['images'])==5
        assert saved['batches'][0]['adopted'] is None
        duplicate=subprocess.run(command+args,capture_output=True,text=True)
        assert duplicate.returncode!=0
        assert len(json.loads(request()[1])['data']['channels'][0]['batches'])==1
        snap=json.loads(request()[1])
        chan=snap['data']['channels'][0]
        ref={**chan['batches'][0]['images'][0],'favorite':True}
        updated={**snap['data'],'channels':[{**chan,'refs':[ref],'batches':[{**chan['batches'][0],'adopted':2,'reason':'読みやすい','remember':True}]}]}
        assert request(data={'version':snap['version'],'data':updated})[0]==200
        result=subprocess.run(command+['context','--channel','test','--out',str(Path(tmp)/'refs')],capture_output=True,text=True,check=True)
        context=json.loads(result.stdout)
        assert Path(context['references'][0]).read_bytes()==image.read_bytes()
        assert context['memories'][0]['reason']=='読みやすい'
        print('PASS: agent import of five images, duplicate rejection, reference export, preference context')
        print('PASS: persistence, stale update rejection, origin guard, path isolation, HTML response')
    finally:
        process.terminate();process.wait(timeout=5)
