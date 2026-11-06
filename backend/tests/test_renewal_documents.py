import io
import zipfile
import pytest
from services.renewal_documents import customer_renewal_attachments, extract_customer_documents, UnsafeRenewalDocuments
from jobs.run_renewal_agent import attachment_payloads

def bundle(files):
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as z:
        for name,body in files.items():z.writestr(name,body)
    return data.getvalue()

def test_nested_real_naming_keeps_client_invoices_and_xml_only():
    inner=bundle({'AC/AVISO_RFC_123__A.pdf':b'commission','AC/AVISO_RFC_123__C.pdf':b'customer','Factura/FACT_RFC_NAME_A.pdf':b'commission','Factura/FACT_RFC_NAME_C.pdf':b'customer','Factura/FACT_RFC.xml':b'cfdi'})
    outer=bundle({'FACT_RFC.zip':inner,'123_Caratula.pdf':b'policy','123_AcuseSP.pdf':b'ack'})
    result=customer_renewal_attachments([{'name':'documents.zip','content':outer}])
    assert {a['name'] for a in result}=={'AVISO_RFC_123__C.pdf','FACT_RFC_NAME_C.pdf','FACT_RFC.xml','123_Caratula.pdf','123_AcuseSP.pdf'}
    assert all(a['content']!=b'commission' for a in result)

@pytest.mark.parametrize('name',['A123.pdf','a_123.PDF','AVISO_123__A.pdf','FACT_123_A.pdf','Detalle_Comisión.pdf'])
def test_existing_loose_agent_files_are_excluded(name):
    result=customer_renewal_attachments([{'name':name,'content':b'secret'},{'name':'C123.pdf','content':b'client'}])
    assert [x['name'] for x in result]==['C123.pdf']

def test_extraction_and_automatic_mail_use_same_filter(tmp_path):
    source=tmp_path/'download.zip';source.write_bytes(bundle({'AC/AVISO__A.pdf':b'secret','AC/AVISO__C.pdf':b'client'}))
    dest=tmp_path/'out';dest.mkdir();extract_customer_documents(source,dest)
    assert [p.name for p in dest.iterdir()]==['AVISO__C.pdf']
    (dest/'old_A.pdf').write_bytes(b'secret')
    assert [x['name'] for x in attachment_payloads(str(dest))]==['AVISO__C.pdf']

@pytest.mark.parametrize('files',[{'../escape.pdf':b'x'},{'A123.pdf':b'x'}])
def test_unsafe_or_agent_only_bundle_blocks_sending(files):
    with pytest.raises(UnsafeRenewalDocuments):customer_renewal_attachments([{'name':'bundle.zip','content':bundle(files)}])

def test_corrupt_and_oversized_archives_block_sending():
    with pytest.raises(UnsafeRenewalDocuments):customer_renewal_attachments([{'name':'bundle.zip','content':b'broken'}])
    with pytest.raises(UnsafeRenewalDocuments):customer_renewal_attachments([{'name':'bundle.zip','content':bundle({'C123.pdf':b'x'*100})}],max_bytes=10)
