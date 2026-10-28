import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

ACTIVE_SKILLS = ["tailor-setup", "fast-track", "caveman", "ponytail", "alpha", "beta"]
ARCHIVED_SKILLS = ["gamma"]

VALID_PROJECT = {
    "name": "AI Flow Canvas",
    "description": "Visual canvas for chaining AI steps",
    "archetype": "custom",
    "source_rules": "docs/rules/README.md",
    "stack": {"runtime": "Python 3.12 CLI"},
    "developer": "Steve",
    "skills": ["alpha", "gamma"],
    "verify": {"test": "npm test", "test_scoped": "npm test -- {scope}", "build": "npm run build"},
    "roadmap": [
        {"id": "1.1", "title": "Canvas shell", "priority": "P0", "description": "Drag and drop nodes.", "features": ["canvas"]},
        {"id": "2.1", "title": "Seed flows", "priority": "P1", "description": "Three demo flows.", "features": ["canvas", "arch"]},
    ],
}


def _write_skill(base, name):
    skill_dir = base / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\ndescription: fixture skill\n---\n", encoding="utf-8")


def make_repo(tmp, project=None, status="uninitialized"):
    """Build a minimal fixture repo under tmp and return its root."""
    root = Path(tmp)
    for name in ACTIVE_SKILLS:
        _write_skill(root / ".agents" / "skills", name)
    (root / ".agents" / "skills" / "_staging").mkdir()
    for name in ARCHIVED_SKILLS:
        _write_skill(root / ".agents" / "skills-archive", name)

    sync_dir = root / ".agents" / "sync"
    sync_dir.mkdir()
    (sync_dir / "handoff.json").write_text("{}", encoding="utf-8")
    (sync_dir / "handoff.md").write_text("# Handoff\n", encoding="utf-8")

    (root / "docs" / "specs").mkdir(parents=True)
    (root / "docs" / "PLAN.md").write_text("ORIGINAL PLAN\n", encoding="utf-8")
    (root / "docs" / "specs" / "demo-design.md").write_text("# Demo design\n", encoding="utf-8")

    package = {"name": "template", "description": "template", "scripts": {"tailor": "node scripts/tailor.mjs"}}
    (root / "package.json").write_text(json.dumps(package, indent=2), encoding="utf-8")

    rules = root / "docs" / "rules"
    (rules / "features").mkdir(parents=True)
    (rules / "README.md").write_text("# Rules" + chr(10), encoding="utf-8")
    (rules / "features" / "canvas.md").write_text(chr(10).join(["---", "owns: []", "---", "# Canvas", ""]), encoding="utf-8")

    blueprint = {"status": status, "project": VALID_PROJECT if project is None else project, "rules": {"source": ["src/**/*.ts"]}}
    (root / "project-blueprint.json").write_text(json.dumps(blueprint, indent=2), encoding="utf-8")
    return root


def make_template_repo(tmp, skills=True):
    """Build a fixture repo shaped like this template: real blueprint and package.json, stub skills by real name unless skills=False."""
    root = Path(tmp)
    for name in ("project-blueprint.json", "package.json"):
        shutil.copyfile(REPO_ROOT / name, root / name)

    for folder in ("skills", "skills-archive"):
        (root / ".agents" / folder).mkdir(parents=True)
        source = REPO_ROOT / ".agents" / folder
        if skills and source.is_dir():
            for skill in sorted(source.iterdir()):
                if skill.is_dir() and not skill.name.startswith("_"):
                    _write_skill(root / ".agents" / folder, skill.name)
    (root / ".agents" / "skills" / "_staging").mkdir()

    sync_dir = root / ".agents" / "sync"
    sync_dir.mkdir()
    (sync_dir / "handoff.json").write_text("{}", encoding="utf-8")
    (sync_dir / "handoff.md").write_text("# Handoff\n", encoding="utf-8")

    (root / "docs").mkdir()
    (root / "docs" / "PLAN.md").write_text("ORIGINAL PLAN\n", encoding="utf-8")
    (root / ".gitignore").write_text(
        ".agents/sync/*\n!.agents/sync/session.md\n!.agents/sync/.gitkeep\n", encoding="utf-8"
    )
    return root


def git_init(root):
    """Turn root into a git repo with one commit of everything in it."""
    def git(*args):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)

    git("init", "-q")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.com")
    git("config", "commit.gpgsign", "false")
    git("add", "-A")
    git("commit", "-q", "-m", "fixture")
    return root


def run_node(code):
    """Evaluate an ES module snippet from the real repo root, so imports use ./scripts/..."""
    cmd = ["node", "--input-type=module", "-e", code]
    return subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)


def skill_dirs(root, folder="skills"):
    base = Path(root) / ".agents" / folder
    return {p.name for p in base.iterdir() if p.is_dir()}
