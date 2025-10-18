import subprocess


def main() -> int:

    args = ["uv", "run", "chainlit", "run", "src/agent_core/main.py", "-w"]

    return subprocess.run(args).returncode