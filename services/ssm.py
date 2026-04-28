"""
services/ssm.py — AWS SSM port-forwarding session management.

Responsible for:
  - Augmenting PATH so GUI .app bundles can find the aws CLI binary.
  - Locating the aws CLI executable.
  - Launching a detached AWS-StartPortForwardingSessionToRemoteHost session
    with strict input validation to prevent command injection.
"""
import os
import re
import shutil
import subprocess
import time
import logging

logger = logging.getLogger(__name__)

# Stable absolute paths for system utilities (avoids PATH look-up in routes)
_LSOF = '/usr/sbin/lsof'
_KILL = '/bin/kill'

_MACOS_EXTRA_PATHS = [
    '/usr/local/bin',     # Homebrew (Intel)
    '/opt/homebrew/bin',  # Homebrew (Apple Silicon)
    '/usr/bin',
    '/bin',
    '/usr/sbin',
    '/sbin',
]


def augment_path() -> None:
    """Prepend common macOS binary directories to PATH if not already present.

    Called once at startup so that GUI .app bundles launched without a login
    shell can still find aws, lsof, etc.
    """
    current = os.environ.get('PATH', '')
    additions = [p for p in _MACOS_EXTRA_PATHS if p not in current]
    if additions:
        os.environ['PATH'] = ':'.join(additions) + ':' + current


def find_aws() -> str:
    """Return the absolute path to the aws CLI executable.

    Raises FileNotFoundError if the binary cannot be located.
    """
    found = shutil.which('aws')
    if found:
        return found
    raise FileNotFoundError(
        "AWS CLI not found. Install it with: brew install awscli"
    )


def start_ssm_session(
    target: str,
    profile: str,
    local_port: int,
    remote_port: int,
    host: str,
) -> subprocess.Popen:
    """Start a detached AWS SSM port-forwarding session.

    All parameters are validated before being passed to the subprocess to
    prevent command injection.

    Returns the Popen object for the running session.
    Raises ValueError for invalid inputs, FileNotFoundError if aws is missing.
    """
    if not re.match(r'^i-[a-f0-9]{8,17}$', str(target)):
        raise ValueError("Invalid target: must be a valid AWS instance ID")
    if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', str(profile)):
        raise ValueError("Invalid profile name")
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]{0,253}[a-zA-Z0-9]$', str(host)):
        raise ValueError("Invalid host")
    local_port_int = int(local_port)
    remote_port_int = int(remote_port)
    if not (1 <= local_port_int <= 65535) or not (1 <= remote_port_int <= 65535):
        raise ValueError("Port out of range (1-65535)")

    aws_bin = find_aws()
    cmd = [
        aws_bin,
        'ssm', 'start-session',
        '--target', str(target),
        '--profile', str(profile),
        '--document-name', 'AWS-StartPortForwardingSessionToRemoteHost',
        '--parameters',
        f'{{"portNumber":["{remote_port_int}"],'
        f'"localPortNumber":["{local_port_int}"],'
        f'"host":["{host}"]}}',
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        shell=False,
        env=os.environ.copy(),
    )
    time.sleep(3)
    if process.poll() is not None:
        _, stderr_bytes = process.communicate()
        stderr_text = stderr_bytes.decode(errors='replace').strip() if stderr_bytes else ''
        logger.error(
            "SSM process exited immediately (code %s) for %s -> localhost:%s. stderr: %s",
            process.returncode, host, local_port_int, stderr_text or '(none)',
        )
        raise RuntimeError(
            f"SSM tunnel failed to start for {host}:{remote_port_int} -> localhost:{local_port_int}. "
            f"Exit code: {process.returncode}. "
            "Check: (1) session-manager-plugin installed? "
            "(2) AWS credentials valid? "
            "(3) SSM target instance reachable?"
        )
    logger.debug("SSM session spawned: PID=%s  %s -> localhost:%s", process.pid, host, local_port_int)
    return process
