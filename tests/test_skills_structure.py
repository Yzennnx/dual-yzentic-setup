import unittest
import re
from pathlib import Path

class TestSkillsStructure(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent
        self.skills_dir = self.root / ".agents" / "skills"
        self.archive_dir = self.root / ".agents" / "skills-archive"

    def test_required_skills_exist(self):
        required_skills = ["fast-track", "tailor-setup", "wayfinder", "workflow", "multi-agent-handoff", "qa-break", "demo-seed-data"]
        for skill_name in required_skills:
            skill_file = self.skills_dir / skill_name / "SKILL.md"
            if not skill_file.exists() and self.archive_dir.exists():
                skill_file = self.archive_dir / skill_name / "SKILL.md"
            self.assertTrue(skill_file.exists(), f"Skill file {skill_file} must exist in active or archive")
            content = skill_file.read_text(encoding="utf-8")
            
            # Verify YAML frontmatter
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
            self.assertIsNotNone(match, f"{skill_name}/SKILL.md must have valid YAML frontmatter")
            fm = match.group(1)
            self.assertIn("name:", fm)
            self.assertIn("description:", fm)

    def test_all_skills_have_valid_frontmatter(self):
        active_dirs = [p for p in self.skills_dir.iterdir() if p.is_dir() and not p.name.startswith("_")]
        archived_dirs = [p for p in self.archive_dir.iterdir() if p.is_dir() and not p.name.startswith("_")] if self.archive_dir.exists() else []
        all_dirs = active_dirs + archived_dirs
        self.assertGreaterEqual(len(all_dirs), 7, "Should have the 7 workflow skills")
        for skill_dir in all_dirs:
            skill_file = skill_dir / "SKILL.md"
            self.assertTrue(skill_file.exists(), f"Each skill folder must have SKILL.md: {skill_dir.name}")
            content = skill_file.read_text(encoding="utf-8")
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
            self.assertIsNotNone(match, f"{skill_dir.name}/SKILL.md must have valid YAML frontmatter")
            fm = match.group(1)
            self.assertIn("name:", fm, f"{skill_dir.name}/SKILL.md frontmatter must include name")
            self.assertIn("description:", fm, f"{skill_dir.name}/SKILL.md frontmatter must include description")

    def test_staging_directory_is_excluded_from_active_catalog(self):
        staging_dir = self.skills_dir / "_staging"
        self.assertTrue(staging_dir.exists(), ".agents/skills/_staging directory must exist")
        skill_dirs = [p for p in self.skills_dir.iterdir() if p.is_dir() and not p.name.startswith("_")]
        self.assertNotIn(staging_dir, skill_dirs)

if __name__ == "__main__":
    unittest.main()
