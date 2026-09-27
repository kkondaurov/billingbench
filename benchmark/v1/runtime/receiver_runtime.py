"""Lifecycle of the small, evaluator-owned receiver beside a candidate container."""

import json
from pathlib import Path
import time
from urllib.request import urlopen

from docker_runtime import docker


class Receiver:
    def __init__(self, context, container):
        self.context, self.container = context, container

    @classmethod
    def create(cls, runtime):
        name = "billing-gl-" + runtime.token
        source = Path(__file__).with_name("receiver.py").resolve()
        result = docker(runtime.context, "run", "-d", "--name", name, "--network", runtime.network,
                        "--network-alias", "billing-gl", "--user", "1000:1000", "--read-only",
                        "--tmpfs", "/state:rw,uid=1000,gid=1000,mode=700,size=64m", "-p", "127.0.0.1::4100",
                        "--mount", f"type=bind,src={source},dst=/receiver.py,readonly",
                        "--entrypoint", "python3", runtime.image_id, "/receiver.py", "--state", "/state")
        receiver = cls(runtime.context, result.stdout.strip())
        try:
            mapping = docker(runtime.context, "port", receiver.container, "4100/tcp").stdout.strip()
            for _ in range(30):
                try:
                    with urlopen("http://" + mapping + "/health", timeout=2) as response:
                        if response.status == 200:
                            return receiver
                except OSError:
                    time.sleep(0.1)
            raise RuntimeError("local GL receiver did not start")
        except BaseException:
            receiver.destroy()
            raise

    def fault(self, name):
        if name not in ("before_accept", "after_accept", "unavailable"):
            raise ValueError("unknown receiver fault")
        docker(self.context, "exec", self.container, "python3", "-c",
               "from pathlib import Path;import sys;Path('/state/next-fault').write_text(sys.argv[1])", name)

    def accepted(self):
        result = docker(self.context, "exec", self.container, "python3", "-c",
                        "from pathlib import Path;p=Path('/state/accepted.json');print(p.read_text() if p.exists() else '{}')")
        return json.loads(result.stdout)

    def destroy(self):
        docker(self.context, "rm", "-f", self.container)
