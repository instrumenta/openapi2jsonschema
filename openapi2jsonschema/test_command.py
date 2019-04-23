import os
import pytest  # type: ignore
from click.testing import CliRunner

from openapi2jsonschema.command import default

FIXTURE_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../fixtures")


@pytest.mark.datafiles(os.path.join(FIXTURE_DIR, "petstore.yaml"))
def test_command(datafiles):
    runner = CliRunner()
    for spec in datafiles.listdir():
        result = runner.invoke(default, ["file://%s" % spec])
        assert result.exit_code == 0


def test_version():
    runner = CliRunner()
    result = runner.invoke(default, ["--help"])
    assert result.exit_code == 0
