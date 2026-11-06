"""Bounded, read-only access to explicitly associated client folders."""
from __future__ import annotations

import io
import os
import re
import time
from contextlib import contextmanager

from fastapi import HTTPException
from google.auth import default
from google.auth.transport.requests import AuthorizedSession

from services.client_folders import client_folders_parent_id, normalize_rfc, valid_client_rfc

FOLDER = 'application/vnd.google-apps.folder'
API = 'https://www.googleapis.com/drive/v3/files'
MAX_FILES = 150
MAX_BYTES = 4 * 1024 * 1024


@contextmanager
def drive_session():
    credentials, _ = default(scopes=['https://www.googleapis.com/auth/drive.readonly'])
    with AuthorizedSession(credentials) as session:
        yield session


def get_json(session, path='', **params):
    response = session.get(API + path, params={**params, 'supportsAllDrives': 'true'}, timeout=12)
    response.raise_for_status()
    return response.json()


def literal(value):
    return str(value).replace('\\', '\\\\').replace("'", "\\'")


def roots():
    return [("Drive nuevo", client_folders_parent_id()),
            ("Drive antiguo", os.getenv('PLAUTO_LEGACY_DRIVE_ROOT_ID', '').strip())]


def client_folders(session, client):
    """Never search all of Drive or infer identity from a partial name."""
    folders = []
    rfc = normalize_rfc(client.rfc)
    for label, root in roots():
        if not root:
            continue
        # Linked current folder is authoritative, but verify that it is actually
        # directly under the configured client root. Never follow shortcuts.
        if label == 'Drive nuevo' and client.drive_folder_id:
            item = get_json(session, '/' + client.drive_folder_id, fields='id,name,mimeType,parents,trashed')
            if not item.get('trashed') and item.get('mimeType') == FOLDER and root in item.get('parents', []):
                folders.append((label, item['id']))
                continue
        if not valid_client_rfc(rfc):
            continue
        data = get_json(session, q=f"'{literal(root)}' in parents and trashed=false and mimeType='{FOLDER}' and name contains '{literal(rfc)}'",
                        fields='nextPageToken,files(id,name)', pageSize=100, includeItemsFromAllDrives='true')
        matches = [item for item in data.get('files', [])
                   if re.match(r'^' + re.escape(rfc) + r'(?:\s|[-_]|$)', item['name'], re.I)]
        # Ambiguous RFC folders need explicit linking, never merge identities.
        if len(matches) == 1 and not data.get('nextPageToken'):
            folders.append((label, matches[0]['id']))
    return folders


def inventory(session, client):
    return folder_inventory(session, client_folders(session, client))


def folder_inventory(session, folders):
    pending = [(label, folder, 0) for label, folder in folders]
    results, visited = [], set()
    started = time.monotonic()
    partial = False
    while pending and len(visited) < 20 and len(results) < MAX_FILES and time.monotonic() - started < 25:
        label, parent, depth = pending.pop(0)
        if parent in visited:
            continue
        visited.add(parent)
        data = get_json(session, q=f"'{literal(parent)}' in parents and trashed=false",
                        fields='nextPageToken,files(id,name,mimeType,size,modifiedTime)',
                        pageSize=100, includeItemsFromAllDrives='true', orderBy='modifiedTime desc')
        partial |= bool(data.get('nextPageToken'))
        for item in data.get('files', []):
            if item['mimeType'] == FOLDER:
                if depth < 4:
                    pending.append((label, item['id'], depth + 1))
                else:
                    partial = True
            elif item['mimeType'] != 'application/vnd.google-apps.shortcut':
                results.append({**item, 'source': label, 'url': f"https://drive.google.com/file/d/{item['id']}/view"})
                if len(results) >= MAX_FILES:
                    partial = True
                    break
    return results, partial or bool(pending)


def search_documents(client, query=''):
    with drive_session() as session:
        files, partial = inventory(session, client)
    terms = query.casefold().split()
    matches = [f for f in files if all(term in f['name'].casefold() for term in terms)]
    return {'documents': matches[:25], 'partial': partial or len(matches) > 25,
            'legacy_configured': bool(os.getenv('PLAUTO_LEGACY_DRIVE_ROOT_ID')), 'searches': 'Nombres de documentos dentro del expediente; no búsqueda exhaustiva por contenido.'}


def read_document(client, file_id):
    with drive_session() as session:
        files, _ = inventory(session, client)
        item = next((f for f in files if f['id'] == file_id), None)
        if not item:
            raise HTTPException(404, 'Documento no disponible en este expediente autorizado.')
        return read_file(session, item)


def read_file(session, item):
    file_id = item['id']
    mime = item['mimeType']
    if int(item.get('size', 0)) > MAX_BYTES:
        return {'document': item, 'text': '', 'notice': 'El documento supera el límite de lectura (4 MB). Abre la fuente.'}
    if mime == 'application/vnd.google-apps.document':
        url, params = API + '/' + file_id + '/export', {'mimeType': 'text/plain'}
    elif mime == 'application/pdf' or mime.startswith('text/'):
        url, params = API + '/' + file_id, {'alt': 'media', 'supportsAllDrives': 'true'}
    else:
        return {'document': item, 'text': '', 'notice': 'Formato sin lectura de contenido en esta versión. Abre la fuente.'}
    with session.get(url, params=params, timeout=15, stream=True) as response:
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                return {'document': item, 'text': '', 'notice': 'El documento supera el límite de lectura.'}
    if mime == 'application/pdf':
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        text = '\n'.join(page.extract_text() or '' for page in reader.pages[:20])
        partial = len(reader.pages) > 20 or len(text) > 18000
    else:
        text = data.decode('utf-8', errors='replace')
        partial = len(text) > 18000
    return {'document': item, 'text': text[:18000], 'partial': partial,
            'notice': '' if text.strip() else 'Sin texto extraíble; puede requerir OCR. No se ha interpretado su contenido.'}

def legacy_root():
    return os.getenv('PLAUTO_LEGACY_DRIVE_ROOT_ID', '').strip()


def under_legacy_root(session, folder_id, cache=None):
    """Validate ancestry on every request; shortcuts never grant access."""
    root = legacy_root()
    if not root or folder_id == root:
        return False
    current, seen = folder_id, set()
    cache = {} if cache is None else cache
    for _ in range(10):
        if current in seen:
            return False
        seen.add(current)
        if current not in cache:
            cache[current] = get_json(session, '/' + current, fields='id,mimeType,parents,trashed')
        item = cache[current]
        if item.get('trashed') or item.get('mimeType') != FOLDER:
            return False
        parents = item.get('parents', [])
        if root in parents:
            return True
        if len(parents) != 1:
            return False
        current = parents[0]
    return False


def search_legacy_folders(query):
    """Name search within a verified subtree, for central administrators only."""
    if not legacy_root():
        return {'folders': [], 'notice': 'Drive antiguo pendiente de conexión.'}
    term = query.strip()[:180]
    if len(term) < 3:
        return {'folders': [], 'notice': 'Escribe al menos tres caracteres para buscar en Drive antiguo.'}
    with drive_session() as session:
        root = get_json(session, '/' + legacy_root(), fields='id,driveId')
        params = {'corpora': 'drive', 'driveId': root['driveId']} if root.get('driveId') else {}
        data = get_json(session, q=f"trashed=false and mimeType='{FOLDER}' and name contains '{literal(term)}'",
                        fields='nextPageToken,files(id,name)', pageSize=20, includeItemsFromAllDrives='true', **params)
        folders, cache = [], {}
        started, partial = time.monotonic(), bool(data.get('nextPageToken'))
        for item in data.get('files', []):
            if time.monotonic() - started > 20:
                partial = True
                break
            if under_legacy_root(session, item['id'], cache):
                folders.append({**item, 'source': 'Drive antiguo · Administrativos',
                                'url': 'https://drive.google.com/drive/folders/' + item['id']})
        return {'folders': folders, 'partial': partial,
                'notice': 'Coincidencias por nombre de carpeta. No acreditan identidad; verifica el expediente original.'}


def legacy_documents(folder_id):
    with drive_session() as session:
        if not under_legacy_root(session, folder_id):
            raise HTTPException(404, 'Carpeta no disponible en el archivo antiguo autorizado.')
        files, partial = folder_inventory(session, [('Drive antiguo · Administrativos', folder_id)])
    return {'documents': files[:25], 'partial': partial or len(files) > 25,
            'notice': 'Documentos dentro de la carpeta elegida; verifica la identidad del cliente en la fuente.'}


def read_legacy_document(folder_id, file_id):
    with drive_session() as session:
        if not under_legacy_root(session, folder_id):
            raise HTTPException(404, 'Carpeta antigua no autorizada.')
        files, _ = folder_inventory(session, [('Drive antiguo · Administrativos', folder_id)])
        item = next((item for item in files if item['id'] == file_id), None)
        if not item:
            raise HTTPException(404, 'Documento no disponible dentro de esta carpeta.')
        return read_file(session, item)
