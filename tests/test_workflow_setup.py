import unittest
from pathlib import Path


class WorkflowSetupTest(unittest.TestCase):
    def test_repository_workflow_is_installed_and_bound(self) -> None:
        required_paths = (
            Path("WORKFLOW.md"),
            Path(".workflow/github-setup-contract.json"),
            Path(".github/workflows/landing-ci.yml"),
            Path(".github/workflows/lifecycle.yml"),
            Path(".mergify.yml"),
        )

        for path in required_paths:
            with self.subTest(path=path):
                self.assertTrue(path.is_file())

        orientation = Path("AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("https://github.com/users/ashoka-bm/projects/2", orientation)
        self.assertIn(
            "Required status checks: `landing-evidence`, `landing-gate`",
            orientation,
        )
        self.assertIn("Assignment is the complete claim", orientation)


if __name__ == "__main__":
    unittest.main()
