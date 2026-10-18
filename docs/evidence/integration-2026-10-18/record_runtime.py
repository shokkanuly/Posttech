import json, subprocess, ast, os
from pathlib import Path
root=Path(__file__).resolve().parent
base=['docker','compose','-p','janamen-int-20261018','--env-file',os.environ['JANAMEN_DEMO_ENV']]
summary={}
for name in ('smoke-first','smoke-repeat','outage-pending','outage-recovered'):
    p=root/(name+'.txt')
    if p.exists():
        summary[name]=ast.literal_eval(p.read_text().splitlines()[-1])
codes=list({v['request_code'] for v in summary.values()})
script='''import json
from sqlalchemy import text
from app.database import SessionLocal
from app.models.request import Request, RequestEvent
from app.models.notification import Notification
from app.models.integration import IntegrationOutbox
from app.models.audit import AuditEvent
with SessionLocal() as db:
    result={'core_head':db.scalar(text('SELECT version_num FROM alembic_version')),'requests':[]}
    for code in CODES:
        req=db.query(Request).filter_by(request_code=code).one()
        jobs=db.query(IntegrationOutbox).filter_by(request_id=req.id).all()
        notices=db.query(Notification).filter_by(reference_id=code,title='MOCK document registered').count()
        audits=db.query(AuditEvent).filter_by(target_id=code,action='INTEGRATION_REGISTERED').count()
        result['requests'].append({'request_code':code,'business_status':req.status.value,'integration_status':req.integration_status,'outbox_count':len(jobs),'outbox_status':jobs[0].status,'registration_notices':notices,'registration_audits':audits})
        assert len(jobs)==notices==audits==1 and req.integration_status=='REGISTERED'
    print(json.dumps(result))
'''.replace('CODES',repr(codes))
r=subprocess.run(base+['exec','-T','web','python','-c',script],capture_output=True,text=True)
assert r.returncode==0, r.stderr
summary['core']=json.loads(r.stdout)
script='''import json
from sqlalchemy import text
from app.gateway.config import GatewaySettings
from app.gateway.runtime import GatewayRuntime
from app.gateway.models import GatewayJob, MockDocument
r=GatewayRuntime(GatewaySettings())
with r.sessions() as db:
    keys=KEYS
    jobs=db.query(GatewayJob).filter(GatewayJob.idempotency_key.in_(keys)).all()
    count=db.query(MockDocument).filter(MockDocument.idempotency_key.in_(keys)).count()
    total=db.query(GatewayJob).count()
    assert len(jobs)==count==2
    assert all(j.status=='REGISTERED' for j in jobs)
    print(json.dumps({'gateway_schema':db.scalar(text('SELECT version FROM gateway_schema_version')),'scope':'happy and outage scenarios','total_gateway_jobs':total,'jobs':len(jobs),'documents':count,'unique_keys':len({j.idempotency_key for j in jobs}),'statuses':[j.status for j in jobs],'callbacks':[j.callback_status for j in jobs]}))
r.engine.dispose()
'''.replace('KEYS',repr([code+':v1' for code in codes]))
r=subprocess.run(base+['exec','-T','gateway','python','-c',script],capture_output=True,text=True)
assert r.returncode==0,r.stderr
summary['gateway']=json.loads(r.stdout)
r=subprocess.run(base+['ps','--format','json'],capture_output=True,text=True,check=True)
services=[json.loads(x) for x in r.stdout.splitlines() if x]
summary['services']=[{k:s.get(k) for k in ('Service','State','Health','Ports')} for s in services]
summary['gateway_exposed_image_ports']=next(s.get('Publishers') or [] for s in services if s['Service']=='gateway')
summary['gateway_host_ports']=[p for p in summary['gateway_exposed_image_ports'] if p.get('PublishedPort',0)>0]
assert not summary['gateway_host_ports']
(root/'runtime-journey.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
