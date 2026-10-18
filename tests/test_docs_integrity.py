import re
import subprocess
import unittest
from pathlib import Path

class TestDocsIntegrity(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent
        self.docs_ai = self.root / "docs" / "ai"

    def test_required_docs_exist(self):
        for doc_name in ["agent-handbook.md", "workflows.md", "architecture.md"]:
            doc_file = self.docs_ai / doc_name
            self.assertTrue(doc_file.exists(), f"Doc {doc_file} must exist")
            content = doc_file.read_text(encoding="utf-8")
            self.assertGreater(len(content.strip()), 100, f"Doc {doc_name} must not be empty")

    def test_specs_directory_exists(self):
        specs_dir = self.root / "docs" / "specs"
        self.assertTrue(specs_dir.exists(), "docs/specs/ directory must exist")

    def test_no_absolute_file_links(self):
        tracked = subprocess.run(
            ["git", "ls-files", "*.md"], cwd=self.root, capture_output=True, text=True, check=True
        ).stdout.splitlines()
        self.assertTrue(tracked, "git ls-files returned no Markdown files")
        for name in tracked:
            content = (self.root / name).read_text(encoding="utf-8")
            self.assertNotIn("](file://", content, f"Absolute file:// link in {name}")

    def test_markdown_links_are_valid(self):
        files_to_check = [
            self.root / "AGENTS.md",
            self.root / "CLAUDE.md",
            self.root / "GEMINI.md",
            self.docs_ai / "agent-handbook.md",
            self.docs_ai / "workflows.md",
            self.docs_ai / "architecture.md",
            self.root / "docs" / "rules" / "README.md",
            self.root / "README.md",
            self.root / "docs" / "PLAN.md",
            self.root / ".agents" / "skills" / "tailor-setup" / "SKILL.md",
        ]
        for f in files_to_check:
            self.assertTrue(f.exists(), f"File {f.name} must exist")
            content = f.read_text(encoding="utf-8")
            links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
            for text, url in links:
                if not url.startswith(("http://", "https://", "#", "mailto:")):
                    target = (f.parent / url.split("#")[0]).resolve()
                    # A link to an archived skill (npm run skill:disable) still resolves, in .agents/skills-archive.
                    archived = Path(str(target).replace(f"{Path('.agents', 'skills')}", f"{Path('.agents', 'skills-archive')}", 1))
                    self.assertTrue(target.exists() or archived.exists(), f"Broken relative link in {f.name}: {url}")

if __name__ == "__main__":
    unittest.main()
