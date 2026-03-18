"""Settings routes — agent profile management."""

from pathlib import Path
import shutil
import subprocess as _subprocess
import os

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AgentProfile, AgentRole, Workspace

router = APIRouter()
BASE_DIR = Path(__file__).parent.parent  # routes/ -> app/
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def get_provider_status():
    """Return a dict mapping provider name to status string."""
    statuses = {}

    # Claude
    claude_found = shutil.which("claude") is not None
    statuses["claude"] = "connected" if claude_found else "not_detected"

    # Codex
    codex_found = shutil.which("codex") is not None
    statuses["codex"] = "connected" if codex_found else "not_detected"

    # Gemini
    gemini_found = shutil.which("gemini") is not None
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not gemini_found:
        statuses["gemini"] = "not_detected"
    elif not gemini_key:
        statuses["gemini"] = "cli_only"  # binary present but no API key
    else:
        statuses["gemini"] = "connected"

    return statuses


@router.get("/api/cli-providers")
def cli_providers_status(db: Session = Depends(get_db)):
    """Return detected state for each built-in CLI provider."""
    providers = []
    for key, name, cmd in [
        ("claude_cli", "Claude CLI", "claude"),
        ("codex_cli", "Codex CLI", "codex"),
        ("gemini_cli", "Gemini CLI", "gemini"),
    ]:
        detected = shutil.which(cmd) is not None
        providers.append({
            "key": key,
            "name": name,
            "command": cmd,
            "detected": detected,
        })
    return providers


@router.post("/api/cli-providers/test")
async def test_cli_connection(command: str = Form(...)):
    """Run a quick test of the given CLI command."""
    import shlex
    try:
        cmd_parts = shlex.split(command)
        if not cmd_parts:
            return {"success": False, "output": "No command provided"}
        # Try --version or --help as a safe probe
        probe = cmd_parts + ["--version"]
        result = _subprocess.run(probe, capture_output=True, text=True, timeout=10)
        output = (result.stdout or result.stderr or "").strip()[:500]
        return {"success": result.returncode == 0, "output": output or "(no output)"}
    except _subprocess.TimeoutExpired:
        return {"success": False, "output": "Timed out"}
    except FileNotFoundError:
        return {"success": False, "output": "Command not found"}
    except Exception as e:
        return {"success": False, "output": str(e)}


@router.post("/settings/test-connection")
async def test_connection(
    provider: str = Form(...),
    command: str = Form(...),
    db: Session = Depends(get_db),
):
    """Test a provider CLI connection by running --version on the binary."""
    binary = command.split()[0]  # first word of command_template
    try:
        result = _subprocess.run(
            [binary, "--version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return {
                "success": True,
                "output": result.stdout.strip()[:200] or result.stderr.strip()[:200],
                "error": "",
            }
        else:
            return {
                "success": False,
                "output": result.stdout.strip()[:200],
                "error": result.stderr.strip()[:200],
            }
    except FileNotFoundError:
        return {"success": False, "output": "", "error": f"Binary '{binary}' not found on PATH"}
    except _subprocess.TimeoutExpired:
        return {"success": False, "output": "", "error": "Timed out after 10s"}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    builtins = (
        db.query(AgentProfile)
        .filter(AgentProfile.is_builtin == True)  # noqa: E712
        .order_by(AgentProfile.sort_order)
        .all()
    )
    custom_agents = (
        db.query(AgentProfile)
        .filter(AgentProfile.is_builtin == False)  # noqa: E712
        .order_by(AgentProfile.name)
        .all()
    )
    all_workspaces = db.query(Workspace).order_by(Workspace.updated_at.desc()).all()
    from_ws_id = request.query_params.get("from")
    back_workspace = None
    if from_ws_id:
        try:
            back_workspace = db.query(Workspace).filter(Workspace.id == int(from_ws_id)).first()
        except ValueError:
            pass
    builtin_roles = db.query(AgentRole).filter(AgentRole.is_builtin == True).order_by(AgentRole.sort_order).all()  # noqa: E712
    custom_roles = db.query(AgentRole).filter(AgentRole.is_builtin == False).order_by(AgentRole.name).all()  # noqa: E712
    provider_statuses = get_provider_status()
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "builtins": builtins,
            "custom_agents": custom_agents,
            "builtin_roles": builtin_roles,
            "custom_roles": custom_roles,
            "all_workspaces": all_workspaces,
            "back_workspace": back_workspace,
            "provider_statuses": provider_statuses,
        },
    )


@router.post("/settings/agents/new")
def create_custom_agent(
    request: Request,
    name: str = Form(...),
    provider_preset: str = Form(""),
    command_template: str = Form(""),
    db: Session = Depends(get_db),
):
    """Create a new custom (non-builtin) agent profile via modal form."""
    name = name.strip()
    command_template = command_template.strip()
    provider_preset = provider_preset.strip()

    # Derive provider from preset
    preset_providers = {
        "claude": "claude",
        "codex": "codex",
        "gemini": "gemini",
    }
    provider = preset_providers.get(provider_preset, "custom")

    # Auto-fill command_template from preset if empty
    preset_commands = {
        "claude": "claude --dangerously-skip-permissions",
        "codex": "codex exec -",
        "gemini": "gemini",
    }
    if not command_template and provider_preset in preset_commands:
        command_template = preset_commands[provider_preset]

    if not name:
        return RedirectResponse("/settings?tab=custom&error=name_required", status_code=303)
    if not command_template:
        return RedirectResponse("/settings?tab=custom&error=command_required", status_code=303)

    existing = db.query(AgentProfile).filter(AgentProfile.name == name).first()
    if existing:
        return RedirectResponse("/settings?tab=custom&error=name_exists", status_code=303)

    agent = AgentProfile(
        name=name,
        provider=provider,
        command_template=command_template,
        is_builtin=False,
    )
    db.add(agent)
    db.commit()
    return RedirectResponse("/settings?tab=custom", status_code=303)


@router.post("/settings/agents/{agent_id}/delete")
def delete_custom_agent(
    agent_id: int,
    db: Session = Depends(get_db),
):
    """Delete a custom (non-builtin) agent profile."""
    agent = db.query(AgentProfile).filter(
        AgentProfile.id == agent_id,
        AgentProfile.is_builtin == False,  # noqa: E712
    ).first()
    if agent:
        db.delete(agent)
        db.commit()
    return RedirectResponse("/settings?tab=custom", status_code=303)


@router.post("/settings/roles/new")
def create_custom_role(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    instruction_file: str = Form(...),
    db: Session = Depends(get_db),
):
    """Create a new custom (non-builtin) role."""
    name = name.strip()
    instruction_file = instruction_file.strip()
    description = description.strip()

    if not name:
        return RedirectResponse("/settings?tab=roles&error=name_required", status_code=303)
    if not instruction_file:
        return RedirectResponse("/settings?tab=roles&error=instruction_file_required", status_code=303)
    if not os.path.isfile(instruction_file):
        return RedirectResponse(f"/settings?tab=roles&error=file_not_found", status_code=303)

    existing = db.query(AgentRole).filter(AgentRole.name == name).first()
    if existing:
        return RedirectResponse("/settings?tab=roles&error=name_exists", status_code=303)

    role = AgentRole(
        name=name,
        description=description or None,
        instruction_file=instruction_file,
        is_builtin=False,
    )
    db.add(role)
    db.commit()
    return RedirectResponse("/settings?tab=roles", status_code=303)


@router.post("/settings/roles/{role_id}/delete")
def delete_custom_role(
    role_id: int,
    db: Session = Depends(get_db),
):
    """Delete a custom (non-builtin) role."""
    role = db.query(AgentRole).filter(AgentRole.id == role_id).first()
    if not role:
        return RedirectResponse("/settings?tab=roles", status_code=303)
    if role.is_builtin:
        return RedirectResponse("/settings?tab=roles&error=cannot_delete_builtin", status_code=303)
    db.delete(role)
    db.commit()
    return RedirectResponse("/settings?tab=roles", status_code=303)
