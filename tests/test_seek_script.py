import unittest
import shutil
import tempfile
from pathlib import Path
import sys

# Add script directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
# An archived skill (npm run skill:disable) moves to .agents/skills-archive and keeps working there.
seek_script_dir = root_dir / ".agents" / "skills" / "skill-seeker" / "scripts"
if not seek_script_dir.exists():
    seek_script_dir = root_dir / ".agents" / "skills-archive" / "skill-seeker" / "scripts"
if str(seek_script_dir) not in sys.path:
    sys.path.insert(0, str(seek_script_dir))

try:
    import seek
except ImportError:
    seek = None


class TestSeekScript(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.staging_dir = self.temp_dir / "_staging"
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.target_dir = self.temp_dir / "active_skills"
        self.target_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_module_exists(self):
        self.assertIsNotNone(seek, "seek module must be importable from .agents/skills/skill-seeker/scripts/seek.py")

    def test_validate_skill_directory_success(self):
        valid_dir = self.temp_dir / "valid_skill"
        valid_dir.mkdir()
        skill_md = valid_dir / "SKILL.md"
        skill_md.write_text(
            "---\nname: valid-skill\ndescription: Test description for valid skill\n---\n# Content\n",
            encoding="utf-8"
        )
        is_valid, errors = seek.validate_skill_directory(valid_dir)
        self.assertTrue(is_valid, f"Expected valid, got errors: {errors}")
        self.assertEqual(len(errors), 0)

    def test_validate_skill_directory_missing_skill_md(self):
        invalid_dir = self.temp_dir / "no_file"
        invalid_dir.mkdir()
        is_valid, errors = seek.validate_skill_directory(invalid_dir)
        self.assertFalse(is_valid)
        self.assertTrue(any("Missing SKILL.md" in err for err in errors))

    def test_validate_skill_directory_missing_frontmatter_fields(self):
        invalid_dir = self.temp_dir / "bad_fm"
        invalid_dir.mkdir()
        skill_md = invalid_dir / "SKILL.md"
        skill_md.write_text("---\nname: bad-skill\n---\n# Content\n", encoding="utf-8")
        is_valid, errors = seek.validate_skill_directory(invalid_dir)
        self.assertFalse(is_valid)
        self.assertTrue(any("description" in err for err in errors))

    def test_list_staged_skills(self):
        (self.staging_dir / ".gitkeep").touch()
        (self.staging_dir / "skill-a").mkdir()
        (self.staging_dir / "skill-b").mkdir()
        staged = seek.list_staged_skills(self.staging_dir)
        self.assertEqual(sorted(staged), ["skill-a", "skill-b"])

    def test_promote_staged_skill(self):
        staged_skill = self.staging_dir / "promoted-skill"
        staged_skill.mkdir()
        (staged_skill / "SKILL.md").write_text(
            "---\nname: promoted-skill\ndescription: Valid description\n---\n# Hello\n",
            encoding="utf-8"
        )
        success, msg = seek.promote_staged_skill("promoted-skill", self.staging_dir, self.target_dir)
        self.assertTrue(success, f"Promotion failed: {msg}")
        self.assertTrue((self.target_dir / "promoted-skill" / "SKILL.md").exists())
        self.assertFalse(staged_skill.exists())

    def test_promote_collision_without_force(self):
        (self.target_dir / "existing").mkdir()
        staged_skill = self.staging_dir / "existing"
        staged_skill.mkdir()
        (staged_skill / "SKILL.md").write_text(
            "---\nname: existing\ndescription: Valid description\n---\n# Hello\n",
            encoding="utf-8"
        )
        success, msg = seek.promote_staged_skill("existing", self.staging_dir, self.target_dir, force=False)
        self.assertFalse(success)
        self.assertIn("already exists", msg)


if __name__ == "__main__":
    unittest.main()
