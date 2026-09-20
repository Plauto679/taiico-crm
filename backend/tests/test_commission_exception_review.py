from datetime import date
from decimal import Decimal
from unittest.mock import patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from services import cobranza_prospectadores as s


def test_review_resolves_pending_once_and_preserves_other_lines():
    engine = create_engine('sqlite:///:memory:')
    for model in (s.ProspectorCommissionPeriod, s.ProspectorCommissionBatch, s.ProspectorCommissionLine, s.ProspectorCommissionAllocation):
        model.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    db = factory()
    db.add(s.ProspectorCommissionPeriod(id='period', month=date(2026,8,1), created_by='test'))
    db.add(s.ProspectorCommissionBatch(id='batch', period_id='period', source='metlife', filename='test.xlsx', file_hash='hash', created_by='test', exception_count=2))
    for key,status in [('fixed','pendiente_asignacion'),('pending','pendiente_asignacion'),('ready','listo')]:
        db.add(s.ProspectorCommissionLine(id=key, batch_id='batch', source_key=key, policy_number=key, insurer_id='metlife', source_commission=100, status=status, movement_date=date(2026,8,1)))
    db.commit()
    def analyze(db, inputs, period):
        assert all(x['policy_number'] != 'ready' for x in inputs)
        return [{**x, 'status':'listo' if x['policy_number']=='fixed' else 'pendiente_asignacion', 'exception_reason':None if x['policy_number']=='fixed' else 'Missing', 'allocations': [{
            'prospector_id':'prospector', 'assignment_id':'assignment', 'commission_rate':'0.5',
            'calculation': s._json_value(s.calculate_allocation(Decimal('100'),Decimal('.5'),branch='GMM')),
        }] if x['policy_number']=='fixed' else []} for x in inputs]
    with patch.object(s,'SessionLocal',factory), patch.object(s,'analyze_import_lines',side_effect=analyze):
        assert s.review_period_exceptions('period') == {'reviewed':2,'resolved':1,'pending':1}
        assert s.review_period_exceptions('period') == {'reviewed':1,'resolved':0,'pending':1}
        db.expire_all()
        assert db.query(s.ProspectorCommissionAllocation).count()==1
        assert db.get(s.ProspectorCommissionBatch,'batch').exception_count==1
        assert db.query(s.ProspectorCommissionLine).count()==3
        db.get(s.ProspectorCommissionPeriod,'period').status='cerrado';db.commit()
        with pytest.raises(HTTPException) as error:
            s.review_period_exceptions('period')
        assert error.value.status_code==409
    db.close()
