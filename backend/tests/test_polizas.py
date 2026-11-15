import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base,Client,User,Product,Insurer,Policy,Prospector,PolicyProspectorAssignment,AgentAction
from services.auth import AccessProfile,PROMOTORIAS
from services import polizas as service
from services.renewal_ingestion import apply_source_rfc

class PolicyRegistryTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.Session=sessionmaker(bind=self.engine)
        self.patch=patch.object(service,'SessionLocal',self.Session);self.patch.start()
        self.profile=AccessProfile('owner@example.com','admin',tuple(PROMOTORIAS),'',(),{'polizas':'operacion'})
        with self.Session() as db:
            db.add_all([User(id='user',name='Owner',email='owner@example.com',role='admin'),Insurer(id='metlife',name='MetLife'),Insurer(id='sura',name='SURA')]);db.flush()
            db.add_all([Product(id='gmm',name='GMM',branch='GMM',insurer_id='metlife'),Product(id='sura',name='SURA',branch='GMM',insurer_id='sura'),Client(id='client',full_name='Cliente',rfc='AAAA800101AA1',responsible_user_id='user')]);db.commit()
        self.raw=dict(policy_number='001/26',rfc='AAAA800101AA1',product_id='gmm',effective_start_date='2026-01-01',effective_end_date='2027-01-01',premium_amount='1200.00',payment_frequency='annual')
    def tearDown(self):self.patch.stop();self.engine.dispose()
    def create(self,**updates):return service.create(service.PolicyInput(**{**self.raw,**updates}),self.profile)['id']

    def test_create_reuses_unique_rfc_preserves_number_and_blocks_duplicate(self):
        id=self.create(rfc=' aaaa800101aa1 ')
        with self.Session() as db:
            p=db.get(Policy,id);self.assertEqual(p.client_id,'client');self.assertEqual(p.policy_number,'001/26');self.assertEqual(db.query(Client).count(),1)
        with self.assertRaises(HTTPException):self.create()
        with self.assertRaises(HTTPException):self.create(policy_number='00126')
        with self.assertRaises(HTTPException):self.create(product_id='sura')

    def test_inventory_combines_branch_insurer_and_search_before_pagination(self):
        self.create()
        with self.Session() as db:
            db.add(Product(id='vida',name='Vida',branch='VIDA',insurer_id='metlife'));db.commit()
        self.create(policy_number='002/26',product_id='vida')
        self.create(policy_number='003/26',product_id='sura')
        def query(**filters):
            return service.inventory(**dict(dict(q='',review=False,insurer='',page=1,profile=self.profile,branch=''),**filters))
        self.assertEqual(query()['total'],3)
        self.assertEqual(query(branch='GMM')['total'],2)
        result=query(branch='GMM',insurer='metlife',q='001')
        self.assertEqual(result['inventory_total'],1)
        self.assertEqual(result['rows'][0]['policy_number'],'001/26')
        self.assertEqual(query(branch='VIDA')['rows'][0]['policy_number'],'002/26')
        self.assertEqual(query(branch='VIDA',insurer='sura')['total'],0)

    def test_unknown_or_ambiguous_rfc_creates_no_clients(self):
        with self.assertRaises(HTTPException):self.create(rfc='BBBB800101BB2')
        with self.Session() as db:
            db.add(Client(id='duplicate',full_name='Other',rfc='AAAA800101AA1',responsible_user_id='user'));db.commit()
        with self.assertRaises(HTTPException):self.create()
        with self.Session() as db:self.assertEqual(db.query(Policy).count(),0)

    def test_edit_preserves_assignments_and_has_history(self):
        id=self.create()
        with self.Session() as db:
            db.add(Prospector(id='pro',name='Prospector',normalized_name='prospector',created_by='test'));db.flush()
            db.add(PolicyProspectorAssignment(id='assignment',policy_id=id,prospector_id='pro',commission_rate=Decimal('.8'),effective_from=date(2026,1,1),created_by='test'));db.commit()
        detail=service.detail(id,self.profile)
        service.edit(id,service.PolicyEdit(fingerprint=detail['fingerprint'],data=service.PolicyInput(**{**self.raw,'premium_amount':'1500.00','insured_names':['Persona']})),self.profile)
        with self.Session() as db:
            assignment=db.get(PolicyProspectorAssignment,'assignment');self.assertEqual(assignment.commission_rate,Decimal('.8'));self.assertEqual(assignment.policy_id,id)
            self.assertEqual(db.get(Policy,id).client_id,'client')
            self.assertEqual(db.query(AgentAction).filter_by(action_type='policy_registry_change').count(),2)
        with self.assertRaises(HTTPException):service.edit(id,service.PolicyEdit(fingerprint=detail['fingerprint'],data=service.PolicyInput(**self.raw)),self.profile)

    def test_preview_then_apply_only_selected_and_prevent_repeat(self):
        self.create()
        request=service.ImportRequest(name='file.csv',rows=[{**self.raw,'premium_amount':'1500.00'},{**self.raw,'policy_number':'002/26'}])
        preview=service.import_preview(request,self.profile)
        self.assertEqual([r['kind'] for r in preview['rows']],['changes','new'])
        with self.Session() as db:self.assertEqual(db.query(Policy).count(),1)
        service.import_apply(preview['id'],service.ApplyRequest(indices=[0]),self.profile)
        service.import_apply(preview['id'],service.ApplyRequest(indices=[1]),self.profile)
        with self.Session() as db:self.assertEqual(db.query(Policy).count(),2)
        with self.assertRaises(HTTPException):service.import_apply(preview['id'],service.ApplyRequest(indices=[0]),self.profile)

    def test_conflict_blocks_and_does_not_reassign(self):
        id=self.create()
        with self.Session() as db:
            db.add(Client(id='other',full_name='Same name',rfc='BBBB800101BB2',responsible_user_id='user'));db.commit()
        preview=service.import_preview(service.ImportRequest(name='bad.csv',rows=[{**self.raw,'rfc':'BBBB800101BB2'}]),self.profile)
        self.assertEqual(preview['rows'][0]['kind'],'blocked')
        with self.assertRaises(HTTPException):service.import_apply(preview['id'],service.ApplyRequest(indices=[0]),self.profile)
        with self.Session() as db:self.assertEqual(db.get(Policy,id).client_id,'client')

    def test_permissions_and_no_scope_leaks(self):
        id=self.create();restricted=replace(self.profile,promotorias=('OTHER',),module_permissions={'polizas':'lectura'})
        with self.Session() as db:
            self.assertEqual(service.scoped(db,restricted).count(),0)
            with self.assertRaises(HTTPException):service.get_policy(db,restricted,id)
        with self.assertRaises(HTTPException):service.write_access(restricted)

    def test_dismiss_does_not_modify_existing_policy(self):
        id=self.create()
        preview=service.import_preview(service.ImportRequest(name='review',rows=[{**self.raw,'premium_amount':'2000.00'}]),self.profile)
        service.dismiss_import_rows(preview['id'],service.ApplyRequest(indices=[0]),self.profile)
        with self.assertRaises(HTTPException): service.import_apply(preview['id'],service.ApplyRequest(indices=[0]),self.profile)
        with self.Session() as db:self.assertEqual(db.get(Policy,id).premium_amount,Decimal('1200.00'))

    def test_normalized_rfc_duplicates_block_without_merging(self):
        with self.Session() as db:
            db.add(Client(id='formatted',full_name='Formatted',rfc='AAAA-800101-AA1',responsible_user_id='user'));db.commit()
        with self.assertRaises(HTTPException):self.create()

    def test_later_source_cannot_overwrite_existing_rfc(self):
        with self.Session() as db:
            c=db.get(Client,'client');self.assertFalse(apply_source_rfc(db,c,'BBBB800101BB2'));self.assertEqual(c.rfc,'AAAA800101AA1')

    def test_import_stale_after_edit_and_cross_user_rejected(self):
        id=self.create();preview=service.import_preview(service.ImportRequest(name='file',rows=[{**self.raw,'premium_amount':'3000.00'}]),self.profile)
        d=service.detail(id,self.profile)
        service.edit(id,service.PolicyEdit(fingerprint=d['fingerprint'],data=service.PolicyInput(**{**self.raw,'premium_amount':'2000.00'})),self.profile)
        with self.assertRaises(HTTPException):service.import_apply(preview['id'],service.ApplyRequest(indices=[0]),self.profile)
        with self.assertRaises(HTTPException):service.import_apply(preview['id'],service.ApplyRequest(indices=[0]),replace(self.profile,username='someone@example.com'))

if __name__=='__main__':unittest.main()
