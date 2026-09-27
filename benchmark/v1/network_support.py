"""Use small explicit subnets for this experiment; preserve all existing networks."""
import hashlib
import docker_runtime


def enable():
    original = docker_runtime.docker
    if getattr(original, '_small_pool', False):
        return

    def docker(context, *args, **kwargs):
        if args[:2] != ('network', 'create'):
            return original(context, *args, **kwargs)
        start = int(hashlib.sha256(str(args[-1]).encode()).hexdigest()[:4], 16) % 256
        for offset in range(256):
            subnet = f'10.231.{(start + offset) % 256}.0/24'
            try:
                return original(context, 'network', 'create', '--subnet', subnet, *args[2:], **kwargs)
            except docker_runtime.CommandError as exc:
                if 'overlaps' not in exc.stderr.lower():
                    raise
        raise RuntimeError('No free subnet in the experiment pool')
    docker._small_pool = True
    docker_runtime.docker = docker
