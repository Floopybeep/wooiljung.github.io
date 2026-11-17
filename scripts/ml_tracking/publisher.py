"""Allowlisted public progress feed. No model, audio, transcript, or client access."""
import argparse,datetime,fcntl,json,math,os,subprocess,time
from pathlib import Path

def read(path,default=None):
    try:return json.loads(Path(path).read_text())
    except (OSError,ValueError):return default if default is not None else {}
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def number(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def clean(source,identity):
    """Generic summary protocol; drop unknown fields and limit all public strings."""
    statuses={'queued','running','complete','failed','interrupted','unknown'}
    completed=source.get('completed',0);total=source.get('total',0)
    completed=max(0,int(completed)) if number(completed) else 0
    total=max(completed,int(total)) if number(total) else completed
    metrics={str(k)[:48]:float(v) for k,v in source.get('metrics',{}).items() if number(v)}
    return {'id':identity['id'],'label':identity['label'],'status':source.get('status') if source.get('status') in statuses else 'unknown',
            'stage':str(source.get('stage','Awaiting updates'))[:120],'completed':completed,'total':total,
            'unit':str(source.get('unit','steps'))[:24],'metrics':metrics}
def alive(status):
    pid=status.get('pid')
    if not isinstance(pid,int):return False
    try:os.kill(pid,0);return True
    except OSError:return False

def fl_run(spec,base):
    root=base/spec['path'];status=read(root/'status.json')
    if not status:return clean({'status':'queued','total':len(spec['arms'])*spec['rounds'],'unit':'rounds'},spec)
    state=status.get('state','unknown');stage=status.get('stage','unknown')
    if state=='running' and not alive(status):state='interrupted'
    completed=0;metrics={}
    for arm in spec['arms']:
        folder=root/arm;rounds=sorted(folder.glob('round_*.json'))
        completed+=min(spec['rounds'],max([read(p).get('round',0) for p in rounds],default=0))
        summaries=sorted(folder.glob('validation_round_*/summary.json'))
        if summaries:
            result=read(summaries[-1]);r=int(summaries[-1].parent.name.rsplit('_',1)[1])
            if number(result.get('overall',{}).get('wer')):metrics[f'{arm} WER % (r{r})']=100*result['overall']['wer']
            if number(result.get('worst_group_wer')):metrics[f'{arm} worst WER % (r{r})']=100*result['worst_group_wer']
        if stage=='FL_'+arm:
            pending=[p for p in sorted(folder.glob('validation_round_*/progress.json')) if not (p.parent/'summary.json').exists()]
            if pending:
                p=read(pending[-1]);stage=f"{arm}: validation {p.get('completed',0):,}/{p.get('total',0):,} clips"
    if stage=='central_training':
        finished=len(list((root/'central').glob('validation_epoch_*/summary.json')))
        stage=f'Central training / validation · {finished}/3 epochs evaluated'
    if state=='complete':stage='Complete'
    return clean({'status':state,'stage':stage,'completed':completed,'total':len(spec['arms'])*spec['rounds'],'unit':'rounds','metrics':metrics},spec)

def snapshot(config):
    pipelines=[]
    for item in config['pipelines']:
        base=Path(item.get('base_dir','.'))
        if item['adapter']=='faist_fl':runs=[fl_run(spec,base) for spec in item['runs']]
        elif item['adapter']=='summary_json':runs=[clean(read(base/spec['path']),spec) for spec in item['runs']]
        else:raise ValueError('Unknown adapter')
        states={r['status'] for r in runs}
        status=('failed' if 'failed' in states else 'interrupted' if 'interrupted' in states else 'complete' if states=={'complete'} else 'running' if 'running' in states else 'queued' if states=={'queued'} else 'unknown')
        pipelines.append({'id':item['id'],'label':item['label'],'description':item.get('description',''), 'status':status,'runs':runs})
    return {'schema_version':1,'generated_at':utc(),'refresh_seconds':config.get('interval_seconds',120),'pipelines':pipelines}

def github(method,path,payload):
    p=subprocess.run(['gh','api','--method',method,path,'--input','-'],input=json.dumps(payload),text=True,capture_output=True,timeout=60)
    if p.returncode:raise RuntimeError(f'GitHub update failed (exit {p.returncode}); retrying without exposing response details')
    return json.loads(p.stdout)
def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--once',action='store_true');p.add_argument('--publish',action='store_true');args=p.parse_args()
    config=read(args.config);state_dir=args.config.parent/'publisher_state';state_dir.mkdir(exist_ok=True)
    lock=(state_dir/'publisher.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    failures=0
    while True:
        try:
            config=read(args.config);data=snapshot(config)
            output=Path(config['snapshot_path']);output.parent.mkdir(parents=True,exist_ok=True)
            tmp=output.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(output)
            if args.publish:
                feed=read(state_dir/'feed.json')
                payload={'files':{'ml-status.json':{'content':json.dumps(data)}}}
                if not feed:
                    response=github('POST','/gists',dict(payload,description='ML training progress — aggregate status only',public=False))
                    feed={'gist_id':response['id'],'raw_url':f"https://gist.githubusercontent.com/{response['owner']['login']}/{response['id']}/raw/ml-status.json"}
                    (state_dir/'feed.json').write_text(json.dumps(feed,indent=2)+'\n')
                else:github('PATCH','/gists/'+feed['gist_id'],payload)
            failures=0
            (state_dir/'status.json').write_text(json.dumps({'state':'published' if args.publish else 'snapshot_only','updated_at':utc(),'pid':os.getpid()})+'\n')
            if args.once:break
        except Exception as e:
            failures+=1
            (state_dir/'status.json').write_text(json.dumps({'state':'retrying','updated_at':utc(),'pid':os.getpid(),'error':type(e).__name__})+'\n')
            if args.once:raise
        time.sleep(min(900,config.get('interval_seconds',120)*max(1,failures)))
if __name__=='__main__':main()
