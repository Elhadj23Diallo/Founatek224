"""File-based admission control for paid wallet purchases."""

import argparse
import errno
import os
from collections.abc import Mapping
from contextlib import ExitStack, contextmanager
from functools import wraps
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import monotonic, sleep

if os.name == "nt":
    import msvcrt
else:
    import fcntl


CAN_SPEND_ON_THIS_RELEASE = True


class WalletLockBusy(Exception):
    pass


def control_directory():
    return Path(os.environ.get("FOUNATEK_WALLET_CONTROL_DIR") or Path.home() / ".founatek-wallet")


@contextmanager
def _lock(path, timeout=0):
    deadline = monotonic() + timeout
    with path.open("r+b") as handle:
        while True:
            try:
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as error:
                if error.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                if monotonic() >= deadline:
                    raise WalletLockBusy(path.name) from error
                sleep(0.05)
        yield
        # Closing the descriptor releases the lock, including on exceptions.


def _is_open(directory):
    try:
        return (directory / "state").read_bytes() == b"open\n"
    except OSError:
        return False


def _set_state(directory, state):
    file = NamedTemporaryFile(dir=directory, delete=False)
    temporary = Path(file.name)
    try:
        with file:
            file.write(state)
            file.flush()
            os.fsync(file.fileno())
        # Replace only the marker, never either lock file.
        os.replace(temporary, directory / "state")
    finally:
        temporary.unlink(missing_ok=True)


def control(action, timeout=60):
    if action not in ("pause", "status", "resume"):
        raise ValueError("Commande Wallet inconnue.")
    directory = control_directory()
    if not directory.is_absolute():
        raise ValueError("Le répertoire de contrôle Wallet doit être absolu.")
    operation_lock = directory / "operations.lock"
    admin_lock = directory / "admin.lock"
    if action == "status":
        if not admin_lock.is_file() or not operation_lock.is_file():
            return "closed-uninitialized"
        with _lock(admin_lock):
            opened = _is_open(directory)
            if opened and not CAN_SPEND_ON_THIS_RELEASE:
                return "closed-release"
            try:
                with _lock(operation_lock):
                    return "open" if opened else "paused-drained"
            except WalletLockBusy:
                return "open-busy" if opened else "paused-draining"
    if action == "resume" and not CAN_SPEND_ON_THIS_RELEASE:
        raise ValueError("Cette version de secours ne peut pas rouvrir les achats Wallet.")
    if action == "pause":
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        for path in (operation_lock, admin_lock):
            path.touch(mode=0o600, exist_ok=True)
    with _lock(admin_lock, timeout):
        if action == "pause":
            _set_state(directory, b"paused\n")
        with _lock(operation_lock, timeout):
            if action == "resume":
                _set_state(directory, b"open\n")
                return "open"
            return "paused-drained"


def wallet_purchase_guard(is_paid_purchase):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            from django.http import JsonResponse

            if not is_paid_purchase(request):
                return view(request, *args, **kwargs)

            def paused():
                return JsonResponse({
                    "code": "wallet_paused",
                    "error": "Les achats Wallet sont temporairement suspendus.",
                }, status=503, headers={"Cache-Control": "no-store"})

            directory = control_directory()
            if not CAN_SPEND_ON_THIS_RELEASE or not directory.is_absolute() or not _is_open(directory):
                return paused()
            with ExitStack() as stack:
                try:
                    stack.enter_context(_lock(directory / "operations.lock"))
                except WalletLockBusy:
                    if not _is_open(directory):
                        return paused()
                    return JsonResponse({
                        "code": "wallet_busy",
                        "error": "Une opération Wallet est en cours. Réessaie avec la même clé.",
                    }, status=409, headers={"Cache-Control": "no-store"})
                except OSError:
                    return paused()
                if not _is_open(directory):
                    return paused()
                return view(request, *args, **kwargs)
        return wrapped
    return decorate


def is_mobile_wallet_purchase(request):
    from .utils import PLAN_PRICES

    if not isinstance(request.data, Mapping):
        return False
    plan = request.data.get("plan", "free")
    return isinstance(plan, str) and PLAN_PRICES.get(plan, 0) > 0


def is_web_wallet_purchase(request):
    from .utils import PLAN_PRICES

    return (
        request.method == "POST"
        and request.POST.get("action") not in ("cancel_at_period_end", "reactivate")
        and request.POST.get("provider") == "wallet"
        and PLAN_PRICES.get(request.POST.get("plan"), 0) > 0
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("pause", "status", "resume"))
    args = parser.parse_args()
    try:
        print(control(args.action))
    except (OSError, ValueError, WalletLockBusy) as error:
        parser.exit(1, f"Contrôle Wallet non confirmé : {error}\n")
