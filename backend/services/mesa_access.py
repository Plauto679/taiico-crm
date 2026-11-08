"""Private Mesa pilot: a single configured account, fail closed by default."""
import os


def mesa_available(profile):
    owner = os.getenv('MESA_OWNER_USERNAME', '').strip().casefold()
    return bool(owner and profile.username.strip().casefold() == owner
                and profile.role in {'admin', 'agente'} and profile.can_read('pendientes'))
