"""Private Mesa pilot: owner and explicitly invited operators; fail closed."""
import os


def mesa_available(profile):
    owner = os.getenv('MESA_OWNER_USERNAME', '').strip().casefold()
    operators = {value.strip().casefold() for value in
                 os.getenv('MESA_OPERATOR_USERNAMES', '').split(',') if value.strip()}
    username = profile.username.strip().casefold()
    authorized = username == owner or (username in operators and profile.can_operate('pendientes'))
    return bool(owner and authorized
                and profile.role in {'admin', 'agente'} and profile.can_read('pendientes'))
