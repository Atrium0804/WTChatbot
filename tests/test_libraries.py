import contextlib
import io
import runpy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mistralai.client.libraries import Libraries


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "libraries.py"


def library(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name, model_dump_json=lambda **_: name)


class LibraryScriptTests(unittest.TestCase):
    def run_script(self, pages: list[SimpleNamespace]) -> tuple[str, list[str]]:
        output = io.StringIO()
        with (
            patch.dict("os.environ", {"MISTRAL_API_KEY": "test-key"}),
            patch("dotenv.load_dotenv"),
            patch.object(Libraries, "list", autospec=True, side_effect=pages),
            patch.object(Libraries, "create", autospec=True) as create,
            contextlib.redirect_stdout(output),
        ):
            runpy.run_path(str(SCRIPT), run_name="__main__")
        return output.getvalue(), [kwargs["name"] for _, kwargs in create.call_args_list]

    def test_creates_missing_libraries_with_supported_sdk_argument(self) -> None:
        output, calls = self.run_script(
            [SimpleNamespace(data=[], next_page_token=None)]
        )

        self.assertIn("number of libraries: 0", output)
        self.assertEqual(calls, ["KWNU", "REGIO", "CLUB"])

    def test_checks_every_page_by_library_name(self) -> None:
        output, calls = self.run_script(
            [
                SimpleNamespace(data=[library("KWNU")], next_page_token="next"),
                SimpleNamespace(
                    data=[library("REGIO"), library("CLUB")], next_page_token=None
                ),
            ]
        )

        self.assertIn("number of libraries: 3", output)
        self.assertIn("All required libraries exist", output)
        self.assertEqual(calls, [])

    def test_creates_only_missing_libraries(self) -> None:
        _, calls = self.run_script(
            [SimpleNamespace(data=[library("REGIO")], next_page_token=None)]
        )

        self.assertEqual(calls, ["KWNU", "CLUB"])


if __name__ == "__main__":
    unittest.main()
