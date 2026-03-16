"""CLI runner — spawns one fresh subprocess per agent turn."""

import shlex
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class RunResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False
    error: Optional[str] = None  # set if command not found or OS-level error


def run_agent(
    command: str,
    prompt: str,
    working_directory: Optional[str] = None,
    timeout: int = 300,
) -> RunResult:
    """Run one agent turn.

    Send the full prompt via stdin. Capture stdout/stderr/exit code.
    Uses shlex.split(command) to parse the command string into args.
    Raises no exceptions — all errors are returned in RunResult.
    """
    try:
        args = shlex.split(command)
    except ValueError as e:
        return RunResult(
            stdout="",
            stderr="",
            exit_code=-1,
            error=f"Invalid command string: {e}",
        )

    try:
        result = subprocess.run(
            args,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_directory,
        )
        return RunResult(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
        )
    except subprocess.TimeoutExpired:
        return RunResult(
            stdout="",
            stderr="",
            exit_code=-1,
            timed_out=True,
            error=f"Agent timed out after {timeout}s",
        )
    except FileNotFoundError:
        # Covers both "command not found" and "working_directory not found"
        # when the working_directory does not exist, subprocess raises FileNotFoundError too.
        # We disambiguate by checking if the executable exists separately — but the spec
        # says to return "Command not found: <command>" for a missing executable and
        # "Invalid working directory: <working_directory>" for a bad cwd.
        # subprocess raises FileNotFoundError for the executable; a missing cwd also
        # raises FileNotFoundError on some platforms and NotADirectoryError on others.
        # Since both raise the same exception for a missing executable, we check cwd first.
        if working_directory is not None:
            import os
            if not os.path.isdir(working_directory):
                return RunResult(
                    stdout="",
                    stderr="",
                    exit_code=-1,
                    error=f"Invalid working directory: {working_directory}",
                )
        return RunResult(
            stdout="",
            stderr="",
            exit_code=-1,
            error=f"Command not found: {command}",
        )
    except NotADirectoryError:
        return RunResult(
            stdout="",
            stderr="",
            exit_code=-1,
            error=f"Invalid working directory: {working_directory}",
        )
    except OSError as e:
        return RunResult(
            stdout="",
            stderr="",
            exit_code=-1,
            error=str(e),
        )
