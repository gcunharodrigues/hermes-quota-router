# Implements decisions/product-spec.md, section 9; decisions/hqr-20-amendment.md, section 4 and AC-20.
"""Private local JSON storage using descriptor-relative, no-follow operations."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import stat


# decisions/s3-delivery.md, SEC-S3-01: retain directory descriptors and reject symlinks/unsafe owner or mode at every ancestor.
@contextmanager
def directory(path, *, create=False):
    path = Path(os.path.abspath(path))
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for index, part in enumerate(path.parts[1:]):
            final = index == len(path.parts) - 2
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, 0o700, dir_fd=fd)
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.fchmod(child, 0o700)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            if info.st_uid not in (0, os.geteuid()) or stat.S_IMODE(info.st_mode) & 0o022:
                raise OSError('Unsafe storage ancestor')
            if final and (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700):
                raise OSError('Unsafe private storage directory')
        yield fd
    finally:
        os.close(fd)


# decisions/s3-delivery.md, SEC-S3-01: private records require one regular, owner-only file, not a special file or hard link.
def regular(fd):
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
        raise OSError('Unsafe private storage file')
    return fd


def open_record(fd, name, flags=os.O_RDONLY):
    if Path(name).name != name or name in ('.', '..'):
        raise OSError('Invalid record name')
    result = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=fd)
    try:
        regular(result)
        return result
    except BaseException:
        os.close(result)
        raise


def read(fd, name, default):
    try:
        handle = open_record(fd, name)
    except FileNotFoundError:
        return default
    with os.fdopen(handle, 'r', encoding='utf-8') as stream:
        return json.load(stream)


# decisions/hqr-20-amendment.md, AC-20: fsync both the temporary record and its directory around atomic replacement.
def publish(fd, name, value):
    try:
        old = open_record(fd, name)
    except FileNotFoundError:
        pass
    else:
        os.close(old)
    temporary = '.pending-' + secrets.token_hex(16)
    handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
    try:
        os.fchmod(handle, 0o600)
        regular(handle)
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            handle = None
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, name, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        if handle is not None:
            os.close(handle)
        try:
            os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError:
            pass
