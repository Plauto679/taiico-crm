"""Customer-safe renewal attachments, including nested insurer ZIP bundles."""
import io
import logging
import mimetypes
import re
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath

log = logging.getLogger(__name__)

class UnsafeRenewalDocuments(ValueError):
    pass

def is_agent_document(name):
    stem=Path(name.replace('\\','/')).stem.upper()
    stem=''.join(c for c in unicodedata.normalize('NFD',stem) if not unicodedata.combining(c))
    return bool(re.search(r'(?:^A(?:$|[_\-\s]|\d)|[_\-\s]A$|(?:^|[_\-\s])AGENTE(?:S)?(?:$|[_\-\s])|COMISION)',stem))

def customer_renewal_attachments(attachments, *, max_bytes=25*1024*1024, max_count=100):
    result=[];seen=set();expanded=0;members=0
    def visit(item,depth=0):
        nonlocal expanded,members
        name=str(item.get('name') or '').replace('\\','/')
        path=PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or not path.name or '\x00' in name:
            raise UnsafeRenewalDocuments('El paquete contiene una ruta insegura; requiere revisión.')
        if path.name.startswith('.') or '__MACOSX' in path.parts:return
        if is_agent_document(path.name):
            log.info('Excluded agent renewal document: %s',path.name)
            return
        content=item.get('content',b'')
        archive=zipfile.is_zipfile(io.BytesIO(content))
        if path.suffix.lower()=='.zip' and not archive:
            raise UnsafeRenewalDocuments('El ZIP de renovación no se puede validar; no se enviará.')
        if archive:
            if depth>=4:raise UnsafeRenewalDocuments('Demasiados ZIP anidados; requiere revisión.')
            with zipfile.ZipFile(io.BytesIO(content)) as bundle:
                for member in bundle.infolist():
                    if member.is_dir():continue
                    members+=1
                    if members>1000 or member.file_size>max_bytes or expanded+member.file_size>max_bytes:
                        raise UnsafeRenewalDocuments('El ZIP excede el límite seguro de documentos.')
                    if member.flag_bits & 1:raise UnsafeRenewalDocuments('ZIP protegido; requiere revisión antes de enviar.')
                    expanded+=member.file_size
                    visit({'name':member.filename,'content':bundle.read(member)},depth+1)
            return
        leaf=path.name
        if leaf.casefold() in seen:raise UnsafeRenewalDocuments('Hay documentos con nombres duplicados; requiere revisión.')
        seen.add(leaf)
        result.append({**item,'name':leaf,'content':content,'mime_type':item.get('mime_type') or mimetypes.guess_type(leaf)[0] or 'application/octet-stream'})
        if len(result)>max_count or sum(len(x['content']) for x in result)>max_bytes:
            raise UnsafeRenewalDocuments('Los documentos exceden el límite seguro de adjuntos.')
    for item in attachments:visit(item)
    if attachments and not result:raise UnsafeRenewalDocuments('Solo hay documentos del agente; falta la documentación del cliente.')
    return result

def extract_customer_documents(archive, destination):
    archive=Path(archive);destination=Path(destination)
    items=customer_renewal_attachments([{'name':archive.name,'content':archive.read_bytes()}])
    for item in items:(destination/item['name']).write_bytes(item['content'])
