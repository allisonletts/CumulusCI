import os


class LocalFolderSource:
    def __init__(self, project_config, spec):
        self.project_config = project_config
        self.spec = spec
        self.path = self.spec["path"]

    def __repr__(self):
        return f"<LocalFolderSource {str(self)}>"

    def __str__(self):
        return f"Local folder: {self.path}"

    def __hash__(self):
        return hash((self.path,))

    def fetch(self):
        """Construct a project config referencing the specified path."""
        project_config = self.project_config.__class__(
            self.project_config.global_config_obj,
            repo_info={"root": os.path.realpath(self.path)},
            included_sources=self.project_config.included_sources,
        )
        return project_config

    @property
    def frozenspec(self):
        raise NotImplementedError("Cannot construct frozenspec for local folder")
