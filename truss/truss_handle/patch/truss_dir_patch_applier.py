import logging
from pathlib import Path
from typing import List

from truss.base.truss_config import TrussConfig
from truss.templates.control.control.helpers.custom_types import (
    Action,
    ConfigPatch,
    EnvVarPatch,
    ExternalDataPatch,
    ModelCodePatch,
    PackagePatch,
    Patch,
    PythonRequirementPatch,
    SystemPackagePatch,
)
from truss.templates.control.control.helpers.errors import UnsupportedPatch
from truss.templates.control.control.helpers.truss_patch.model_code_patch_applier import (
    apply_code_patch,
)
from truss.templates.control.control.helpers.truss_patch.requirement_name_identifier import (
    identify_requirement_name,
    reqs_by_name,
)
from truss.templates.control.control.helpers.truss_patch.system_packages import (
    system_packages_set,
)


class TrussDirPatchApplier:
    """Applies patches to a truss directory.
    This should be compatible with ModelContainerPatchApplier.

    Note: This class imported via old_build_setup.sh.jinja in the baseten
    repository
    """

    def __init__(self, truss_dir: Path, logger: logging.Logger) -> None:
        self._truss_dir = truss_dir
        self._truss_config_path = self._truss_dir / "config.yaml"
        self._truss_config = TrussConfig.from_yaml(self._truss_config_path)
        self._logger = logger

    def __call__(self, patches: List[Patch]):
        # Apply model code patches immediately
        # Aggregate config patches and apply at end
        reqs = reqs_by_name(self._truss_config.requirements)
        pkgs = system_packages_set(self._truss_config.system_packages)
        new_config = self._truss_config
        for patch in patches:
            self._logger.debug(f"Applying patch {patch.to_dict()}")
            action = patch.body.action
            if isinstance(patch.body, ModelCodePatch):
                model_code_patch: ModelCodePatch = patch.body
                model_module_dir = self._truss_dir / self._truss_config.model_module_dir
                apply_code_patch(model_module_dir, model_code_patch, self._logger)
            elif isinstance(patch.body, PythonRequirementPatch):
                py_req_patch: PythonRequirementPatch = patch.body
                req = py_req_patch.requirement
                req_name = identify_requirement_name(req)
                if action == Action.REMOVE:
                    del reqs[req_name]
                elif action == Action.ADD or Action.UPDATE:
                    reqs[req_name] = req
            elif isinstance(patch.body, SystemPackagePatch):
                sys_pkg_patch: SystemPackagePatch = patch.body
                pkg = sys_pkg_patch.package
                if action == Action.REMOVE:
                    pkgs.remove(pkg)
                elif action == Action.ADD or Action.UPDATE:
                    pkgs.add(pkg)
            elif isinstance(patch.body, ConfigPatch):
                new_config = TrussConfig.from_dict(patch.body.config)
            # Each of EnvVarPatch and ExternalDataPatch can be expressed through an
            # overwrite of the config, handled below.
            elif isinstance(patch.body, (EnvVarPatch, ExternalDataPatch)):
                pass
            elif isinstance(patch.body, PackagePatch):
                package_patch: PackagePatch = patch.body
                package_module_dir = (
                    self._truss_dir / self._truss_config.bundled_packages_dir
                )
                apply_code_patch(package_module_dir, package_patch, self._logger)
            else:
                raise UnsupportedPatch(f"Unknown patch type {patch.type}")

        new_config.write_to_yaml_file(self._truss_config_path)
