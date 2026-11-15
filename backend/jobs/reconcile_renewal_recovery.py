"""Reconcile a saved priority manifest against MetLife before retrying delivery.

Uses the normal job lock and durable delivery protections. No payment or
insurance transaction is performed. Evidence is saved after each query.
"""
from __future__ import annotations
import argparse
import fcntl
import json
from datetime import date, datetime
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jobs import run_renewal_agent as job
from adapters.metlife_gmm_collection import check_metlife_gmm_collection, collection_result_to_dict
from database import SessionLocal, PolicyDocumentRetrievalTask, Policy, Renewal, AgentAction


def reconcile(manifest: Path, *, deliver: bool = False):
    rows=json.loads(manifest.read_text())
    output=manifest.with_suffix('.results.json')
    results=[]
    job.state_path().parent.mkdir(parents=True,exist_ok=True)
    with job.state_path().with_suffix('.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        for row in rows:
            with SessionLocal() as db:
                task=db.query(PolicyDocumentRetrievalTask).filter_by(
                    insurer_id='metlife', product_branch='GMM', policy_number=row['policy_number'],
                    renewal_deadline=date.fromisoformat(row['deadline'])).one()
                db.expunge(task)
            job.emit('reconciliation_started',policy=task.policy_number)
            result=check_metlife_gmm_collection(job.MetLifeGmmPortalTask(
                id=task.id,policy_number=task.policy_number,rfc=task.rfc or '',client_name=task.client_name,
                renewal_deadline=task.renewal_deadline,original_policy_number=task.original_policy_number),headless=False)
            evidence=collection_result_to_dict(result)
            succeeded=result.status=='completed' and result.paid_until is not None
            job.persist_collection_check(task.id,paid_until=result.paid_until or job.COLLECTION_FAILURE_DATE,
                succeeded=succeeded,error=result.error_message)
            item={'policy':task.policy_number,'deadline':str(task.renewal_deadline),'evidence':evidence,'delivery':'not_attempted'}
            # A paid period extending beyond the renewal deadline is evidence of
            # continuity, not proof that the full annual premium has been paid.
            if succeeded and result.paid_until > task.renewal_deadline:
                item['outcome']='payment_beyond_renewal_deadline'
                with SessionLocal() as db:
                    policies=db.query(Policy).filter_by(insurer_id='metlife',policy_number=task.policy_number).all()
                    for policy in policies:
                        for renewal in db.query(Renewal).filter_by(original_policy_id=policy.id,renewal_deadline=task.renewal_deadline).all():
                            metadata=dict(renewal.requested_modifications or {})
                            metadata['metlife_reconciliation']=evidence
                            renewal.requested_modifications=metadata
                    db.add(AgentAction(agent_name='renewal_agent',action_type='renewal_reconciliation',status='completed',
                        input_payload={'task_id':task.id,'policy_number':task.policy_number},output_payload=evidence))
                    db.commit()
            elif succeeded:
                item['outcome']='no_payment_beyond_renewal_deadline'
                eligible={t.id for t in job.selected_tasks(task.renewal_deadline,start_date=task.renewal_deadline)}
                if deliver and task.id in eligible:
                    run_id=job.create_run([task],task.renewal_deadline)
                    delivery,failed=job.process_one_subprocess(run_id,task.id)
                    item['delivery']=delivery
                    with SessionLocal() as db:
                        run=db.get(job.PolicyDocumentRetrievalRun,run_id)
                        run.status='completed' if delivery['status']=='completed' else 'completed_with_errors'
                        run.completed_at=datetime.utcnow(); db.commit()
                elif task.id not in eligible:
                    item['delivery']='protected_previous_delivery_or_manual_review'
            else:
                item['outcome']='unverified'
            results.append(item)
            output.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
            job.emit('reconciliation_finished',policy=task.policy_number,outcome=item['outcome'],paid_until=str(result.paid_until),delivery=item['delivery'])
            if job.is_portal_failure(evidence) or 'mfa' in str(result.error_message or '').lower():
                job.emit('reconciliation_aborted',reason='portal_unavailable'); break
    return results

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('manifest',type=Path); parser.add_argument('--deliver',action='store_true')
    args=parser.parse_args(); reconcile(args.manifest,deliver=args.deliver)
