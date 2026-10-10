#!/usr/bin/env python3
"""Extract an operator-supplied, exact pinned Fedora RPM; no install or hardware access."""
import hashlib, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
EXPECTED='40853a60de8e31a7bb009ccc2435a705be875facfd77842771e04ed14da86890'
if len(sys.argv)!=2:raise SystemExit('Usage: python3 prepare-runtime.py /path/to/pinned-openrgb.rpm')
rpm=Path(sys.argv[1]).resolve()
if hashlib.sha256(rpm.read_bytes()).hexdigest()!=EXPECTED:raise SystemExit('RPM hash mismatch; refusing extraction')
# Only the required executable is extracted to stdout; no archive paths are written.
archive=subprocess.run(['rpm2cpio',str(rpm)],capture_output=True,check=True)
result=subprocess.run(['cpio','-i','--to-stdout','./usr/bin/openrgb'],input=archive.stdout,capture_output=True,check=True)
if not result.stdout.startswith(b'\x7fELF'):raise SystemExit('Expected ELF executable')
target=ROOT/'vendor/usr/bin/openrgb'
target.parent.mkdir(parents=True,exist_ok=True)
target.write_bytes(result.stdout);target.chmod(0o755)
print('Pinned runtime prepared; no hardware commands were issued.')
