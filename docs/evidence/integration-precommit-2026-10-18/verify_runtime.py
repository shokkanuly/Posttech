"""Read owned synthetic state and prove health does not debit the business quota."""

import argparse
import ast
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--session-dir", type=Path, required=True)
args = parser.parse_args()
root = args.session_dir
values = dotenv_values(root / "demo.env")
base = ["docker", "compose", "--env-file", str(root / "demo.env")]
result = {
    "observed_at_utc": datetime.now(timezone.utc).isoformat(),
    "availability": "Session observation only; not guaranteed for future runs",
    "project": values["COMPOSE_PROJECT_NAME"],
    "web_port": int(values["WEB_PORT"]),
    "postgres_port": int(values["POSTGRES_PORT"]),
    "private_environment_path": str(root / "demo.env"),
    "mode": "MOCK",
    "scenarios": {},
}
for name in ("smoke-first", "smoke-repeat", "outage-pending", "outage-recovered"):
    result["scenarios"][name] = ast.literal_eval((root / (name + ".txt")).read_text().splitlines()[-1])
first, repeat = (result["scenarios"][name] for name in ("smoke-first", "smoke-repeat"))
assert first["request_code"] == repeat["request_code"]
assert first["external_ref"] == repeat["external_ref"]
assert not first["reused_request"] and repeat["reused_request"]
codes = sorted({row["request_code"] for row in result["scenarios"].values()})

core = '''
import json
from sqlalchemy import text
from app.database import SessionLocal
from app.models.request import Request
from app.models.notification import Notification
from app.models.integration import IntegrationOutbox
from app.models.audit import AuditEvent
with SessionLocal() as db:
    result={'migration_head':db.scalar(text('SELECT version_num FROM alembic_version')),'requests':[]}
    for code in CODES:
        req=db.query(Request).filter_by(request_code=code).one()
        jobs=db.query(IntegrationOutbox).filter_by(request_id=req.id).all()
        notices=db.query(Notification).filter_by(reference_id=code,title='MOCK document registered').count()
        audits=db.query(AuditEvent).filter_by(target_id=code,action='INTEGRATION_REGISTERED').count()
        assert len(jobs)==notices==audits==1
        assert req.status.value=='Approved' and req.integration_status=='REGISTERED'
        result['requests'].append({'request_code':code,'outbox_count':len(jobs),'registration_notices':notices,'registration_audits':audits,'outbox_status':jobs[0].status})
    profile=req.user.profile
    approved=db.query(Request).filter_by(user_id=req.user_id,leave_balance_confirmed=False).all()
    charged=sum(r.charged_leave_days or 0 for r in approved if r.status.value=='Approved')
    # The fresh demo accounts may be provisioned after the scheduled snapshot
    # sync. Their existing provisioner starts at 24 days until the first sync.
    baseline=profile.source_balance_days if profile.source_balance_days is not None else 24
    assert profile.leave_balance_days==baseline-charged
    assert db.query(Request).filter_by(user_id=req.user_id).count()==2
    result['business_requests_count']=2
    result['leave_debit_matches_unique_approvals']=True
    print(json.dumps(result))
'''.replace("CODES", repr(codes))
response = subprocess.run(base + ["exec", "-T", "web", "python", "-c", core], capture_output=True, text=True, check=True)
result["core"] = json.loads(response.stdout)

gateway = '''
import hashlib,json
from pathlib import Path
import httpx
from sqlalchemy import text
from app.gateway.config import GatewaySettings
from app.gateway.runtime import GatewayRuntime
from app.gateway.models import GatewayJob,GatewayRateLimit,MockDocument
from app.integrations import signing
config=GatewaySettings(); runtime=GatewayRuntime(config)
identity=config.APP_KEY_ID.encode()
business=hashlib.sha256(identity).hexdigest()
health=hashlib.sha256(b'\\x00health\\x00'+identity).hexdigest()
with runtime.sessions() as db:
    row=db.get(GatewayRateLimit,business)
    before=(row.window_start,row.requests)
with httpx.Client(base_url='http://127.0.0.1:9000',timeout=10,trust_env=False) as client:
    for _ in range(2):
        headers=signing.sign(config.APP_KEY_ID,config.APP_KEY,'GET','/health',b'')
        assert client.get('/health',headers=headers).status_code==200
with runtime.sessions() as db:
    row=db.get(GatewayRateLimit,business)
    after=(row.window_start,row.requests)
    assert before==after and db.get(GatewayRateLimit,health) is not None
    jobs=db.query(GatewayJob).all()
    assert len(jobs)==db.query(MockDocument).count()==2
    assert all(j.status=='REGISTERED' and j.callback_status=='DELIVERED' for j in jobs)
    result={'schema_version':db.scalar(text('SELECT version FROM gateway_schema_version')),'jobs':2,'documents':2,'callbacks_delivered':2,'health_probes':2,'business_quota_unchanged':True,'business_limit':config.REQUESTS_PER_MINUTE,'health_limit':config.HEALTH_REQUESTS_PER_MINUTE,'source_hashes':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ['app/gateway/main.py','app/gateway/runtime.py','app/gateway/config.py']}}
    print(json.dumps(result))
runtime.engine.dispose()
'''
response = subprocess.run(base + ["exec", "-T", "gateway", "python", "-c", gateway], capture_output=True, text=True, check=True)
result["gateway"] = json.loads(response.stdout)
for file, digest in result["gateway"]["source_hashes"].items():
    assert hashlib.sha256(Path(file).read_bytes()).hexdigest() == digest
result["gateway"]["runtime_source_matches_checkout"] = True
assert result["core"]["migration_head"] == "0011_merge_profile_updates"
assert result["gateway"]["schema_version"] == 3
response = subprocess.run(base + ["ps", "--format", "json"], capture_output=True, text=True, check=True)
services = [json.loads(line) for line in response.stdout.splitlines() if line]
result["services"] = [{k: row.get(k) for k in ("Service", "State", "Health", "Ports")} for row in services]
result["gateway_published_ports"] = [port for row in services if row["Service"] == "gateway" for port in row.get("Publishers", []) if port.get("PublishedPort", 0) > 0]
assert not result["gateway_published_ports"]
(root / "runtime-journey.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
