"""Bounded local OCR worker; document bytes never go to a remote OCR service."""
from __future__ import annotations
import json
import os
import subprocess
import tempfile
import threading
from pathlib import Path
from fastapi import HTTPException

_SLOTS = threading.BoundedSemaphore(2)
DEFAULT_BINARY = Path(__file__).resolve().parents[2] / '.runtime/mesa-ocr/recognize'


def binary_path():
    return Path(os.getenv('MESA_OCR_BINARY', str(DEFAULT_BINARY)))


def available():
    return binary_path().is_file() and os.access(binary_path(), os.X_OK)


def read_pages(content):
    if len(content) > 4 * 1024 * 1024:
        raise HTTPException(413, 'La lectura admite archivos de hasta 4 MB.')
    if not available():
        raise HTTPException(503, 'La lectura de escaneos no está habilitada en este servidor. Puedes completar los datos manualmente.')
    if not _SLOTS.acquire(blocking=False):
        raise HTTPException(429, 'Hay otras lecturas de escaneos en curso. Inténtalo en un momento.')
    try:
        with tempfile.TemporaryDirectory(prefix='taiico-ocr-') as directory:
            source = Path(directory) / 'document'
            source.write_bytes(content)
            source.chmod(0o600)
            completed = subprocess.run([str(binary_path()), str(source)], capture_output=True, timeout=90, check=False)
        if completed.returncode != 0 or len(completed.stdout) > 1500000:
            raise ValueError('OCR failed')
        data = json.loads(completed.stdout)
        pages = data['pages']
        if not pages or len(pages) > 30 or sum(len(p['text']) for p in pages) > 100000:
            raise ValueError('OCR limits')
        if any(p['page'] != index + 1 for index, p in enumerate(pages)):
            raise ValueError('invalid page order')
        return pages
    except subprocess.TimeoutExpired:
        raise HTTPException(504, 'La lectura tardó demasiado. Divide el PDF en archivos más pequeños y vuelve a intentar.') from None
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(422, 'No se pudo reconocer el escaneo. Prueba con una imagen más nítida o completa los datos manualmente.') from None
    finally:
        _SLOTS.release()
