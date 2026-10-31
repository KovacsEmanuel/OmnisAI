#!/usr/bin/env python3
"""Repack the exact Redocly 1.34.20 distribution with the reviewed local patch.

No downloads, dependency installs or upstream lifecycle scripts are executed.
Requires Python >=3.12, GNU patch, and TMPDIR pointing at owned scratch storage.
"""
import argparse
import base64
import gzip
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

SOURCE_SRI = 'sha512-ypeBZ/6BKXR9+7/TtbKhbl4UgD7raHhPS12oknlKno2A8+lnFkxIwiE/Aklu6L2cd/ioH+fCWuMxi9/p3EyAPw=='
HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('upstream_tarball', type=Path)
    parser.add_argument('output_tarball', type=Path)
    args = parser.parse_args()
    source = args.upstream_tarball.read_bytes()
    sri = 'sha512-' + base64.b64encode(hashlib.sha512(source).digest()).decode()
    if sri != SOURCE_SRI:
        raise ValueError('Upstream tarball SRI mismatch; refusing to patch')
    with tempfile.TemporaryDirectory(prefix='omnis-openapi-', dir=os.environ['TMPDIR']) as temp:
        work = Path(temp)
        with tarfile.open(fileobj=io.BytesIO(source)) as archive:
            members = archive.getmembers()
            modes = {member.name: member.mode for member in members}
            if any(not m.isfile() or not m.name.startswith('package/') for m in members):
                raise ValueError('Unexpected upstream archive member')
            archive.extractall(work, filter='data')
        subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(HERE / 'matcher.patch')],
                       cwd=work, check=True)
        (work / 'package/tsconfig.tsbuildinfo').unlink()
        (work / 'package/OMNIS-PATCH.md').write_bytes((HERE / 'NOTICE.md').read_bytes())
        (work / 'package/LICENSE.md').write_bytes((HERE / 'LICENSE.md').read_bytes())
        with args.output_tarball.open('xb') as output:
            with gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=0, compresslevel=9) as compressed:
                with tarfile.open(fileobj=compressed, mode='w', format=tarfile.USTAR_FORMAT) as archive:
                    for path in sorted((work / 'package').rglob('*')):
                        if not path.is_file():
                            continue
                        data = path.read_bytes()
                        info = tarfile.TarInfo(path.relative_to(work).as_posix())
                        info.size = len(data)
                        info.mode = modes.get(info.name, 0o644)
                        archive.addfile(info, io.BytesIO(data))
    artifact = args.output_tarball.read_bytes()
    print('sha512-' + base64.b64encode(hashlib.sha512(artifact).digest()).decode())
    print('sha256-' + hashlib.sha256(artifact).hexdigest())


if __name__ == '__main__':
    main()
