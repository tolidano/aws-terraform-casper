from unittest import TestCase
from casper.state import CasperState

from unittest.mock import patch
import os
import shutil


@patch("casper.terraform.TerraformCommand.run_command")
class TestState(TestCase):
    root_dir = "temp"

    @classmethod
    def _make_dir(cls, path):
        os.makedirs(path, exist_ok=True)

    @classmethod
    def _make_file(cls, path):
        with open(path, "w") as f:
            f.write("test")

    def setUp(self) -> None:
        self.state = CasperState()
        self._make_dir(self.root_dir)

    @patch.object(CasperState, "save_state")
    def test_build_state_resources_state_management(self, mock_save, cmd):
        self._make_dir(os.path.join(self.root_dir, "main"))
        self._make_file(os.path.join(self.root_dir, "main", "real.tf"))

        self._make_dir(os.path.join(self.root_dir, "fake"))
        self._make_file(os.path.join(self.root_dir, "fake", "fake.txt"))

        self._make_dir(os.path.join(self.root_dir, "vars"))
        self._make_file(os.path.join(self.root_dir, "vars", "real1.tfvars"))

        self._make_dir(os.path.join(self.root_dir, ".git"))
        self._make_file(os.path.join(self.root_dir, ".git", "git.tf"))

        self.state.build_state_resources(start_dir=self.root_dir)
        self.assertEqual(
            1,
            cmd.call_count,
            "Should be called once times to list the resources in the only "
            "unexcluded directory with a .tf file",
        )
        mock_save.assert_called_once()

    @patch.object(CasperState, "save_state")
    def test_build_state_resource_state_management_exclude_specific_dir(self, _, cmd):
        self._make_dir(os.path.join(self.root_dir, "main"))
        self._make_file(os.path.join(self.root_dir, "main", "real.tf"))

        self._make_dir(os.path.join(self.root_dir, "exclude1"))
        self._make_file(os.path.join(self.root_dir, "exclude1", "exclude1.tf"))

        self._make_dir(os.path.join(self.root_dir, "exclude2"))
        self._make_file(os.path.join(self.root_dir, "exclude2", "exclude2.tf"))

        self.state.build_state_resources(
            start_dir=self.root_dir, exclude_directories={"exclude1", "exclude2"}
        )
        self.assertEqual(
            1,
            cmd.call_count,
            "Should be called once times to list the resources in the only "
            "unexcluded directory with a .tf file",
        )

    @patch.object(CasperState, "save_state")
    def test_build_state_resources_exclude_specific_state_resource(self, _, cmd):
        self._make_dir(os.path.join(self.root_dir, "main"))
        self._make_file(os.path.join(self.root_dir, "main", "real.tf"))

        cmd.side_effect = [
            {"success": True, "data": load_sample("state_specific_exclude.txt")},
            {"success": True, "data": load_sample("aws_lb.txt")},
        ]

        self.state.build_state_resources(
            start_dir=self.root_dir, exclude_state_res={"exclude_me"}
        )
        self.assertEqual(
            2,
            cmd.call_count,
            "Should be called two times, 1 to list the resource in the "
            "state, the other to show the only unexcluded resource in the state",
        )
        self.assertEqual(
            {"aws_alb": ["test-lb"],}, self.state.state_resources,
        )

    @patch.object(CasperState, "save_state")
    def test_build_state_resources(self, _, cmd):
        self._make_dir(os.path.join(self.root_dir, "main"))
        self._make_file(os.path.join(self.root_dir, "main", "real.tf"))

        cmd.side_effect = [
            {"success": True, "data": load_sample("state.txt")},
            {"success": True, "data": load_sample("aws_spot_instance_request.txt")},
            {"success": True, "data": load_sample("aws_instance.txt")},
            {"success": True, "data": load_sample("aws_lb.txt")},
        ]

        self.state.build_state_resources(start_dir=self.root_dir)
        self.assertEqual(
            4,
            cmd.call_count,
            "Should be called three times, 1 to list the resource in the "
            "state, the other to show the three resource in the state",
        )
        self.assertEqual(
            {
                "aws_alb": ["test-lb"],
                "aws_instance": ["i-0101522650aeaa2dd", "i-084699b83473e2c69"],
            },
            self.state.state_resources,
        )

    @patch.object(CasperState, "save_state")
    @patch("logging.Logger.warning")
    def test_build_state_resources_removed_resource(self, logger, _, cmd):
        self._make_dir(os.path.join(self.root_dir, "main"))
        self._make_file(os.path.join(self.root_dir, "main", "real.tf"))

        cmd.side_effect = [
            {"success": True, "data": load_sample("state_removed_resource.txt")},
            {"success": True, "data": load_sample("empty.txt")},
        ]

        self.state.build_state_resources(start_dir=self.root_dir)
        self.assertEqual(
            2,
            cmd.call_count,
            "Should be called two times, 1 to list the resource in the "
            "state, the other to show the only resource in the state",
        )
        logger.assert_called_with(
            "'aws_instance.empty' no longer exist in the state: temp/main"
        )

    @patch.object(CasperState, "save_state")
    @patch("logging.Logger.debug")
    def test_build_state_resources_unsupported_resource(self, logger, _, cmd):
        self._make_dir(os.path.join(self.root_dir, "main"))
        self._make_file(os.path.join(self.root_dir, "main", "real.tf"))

        cmd.side_effect = [
            {"success": True, "data": load_sample("state_unsupported_resource.txt")},
            {"success": True, "data": load_sample("fake_unsupported_resource.txt")},
        ]

        self.state.build_state_resources(start_dir=self.root_dir)
        self.assertEqual(
            2,
            cmd.call_count,
            "Should be called two times, 1 to list the resource in the "
            "state, the other to show the only resource in the state",
        )
        logger.assert_called_with(
            "State Handler for fake_unsupported_resource is not currently supported"
        )

    def tearDown(self):
        shutil.rmtree(self.root_dir, ignore_errors=True)


def load_sample(filename):
    filepath = os.path.join(os.getcwd(), "tests", "samples", filename)
    with open(filepath, "r") as fid:
        sample = fid.read()

    return sample
