import io
import os
import unittest
import yaml
import zipfile

import pytest
import responses

from ..source import GitHubSource
from ..source import LocalFolderSource
from cumulusci.core.config import BaseGlobalConfig
from cumulusci.core.config import BaseProjectConfig
from cumulusci.core.config import ServiceConfig
from cumulusci.core.keychain import BaseProjectKeychain
from cumulusci.tasks.release_notes.tests.utils import MockUtil
from cumulusci.utils import temporary_dir
from cumulusci.utils import touch


class TestGitHubSource(unittest.TestCase, MockUtil):
    def setUp(self):
        self.repo_api_url = "https://api.github.com/repos/TestOwner/TestRepo"
        global_config = BaseGlobalConfig()
        self.project_config = BaseProjectConfig(global_config)
        self.project_config.set_keychain(BaseProjectKeychain(self.project_config, None))
        self.project_config.keychain.set_service(
            "github",
            ServiceConfig(
                {
                    "username": "TestUser",
                    "password": "TestPass",
                    "email": "testuser@testdomain.com",
                }
            ),
        )

    @responses.activate
    def test_resolve__latest(self):
        responses.add(
            method=responses.GET,
            url=self.repo_api_url,
            json=self._get_expected_repo(owner="TestOwner", name="TestRepo"),
        )
        responses.add(
            "GET",
            "https://api.github.com/repos/TestOwner/TestRepo/releases/latest",
            json=self._get_expected_release("release/1.0"),
        )
        responses.add(
            "GET",
            f"https://api.github.com/repos/TestOwner/TestRepo/git/refs/tags/release/1.0",
            json=self._get_expected_tag_ref("release/1.0", "tag_sha"),
        )

        source = GitHubSource(
            self.project_config, {"github": "https://github.com/TestOwner/TestRepo.git"}
        )
        assert (
            repr(source)
            == "<GitHubSource GitHub: TestOwner/TestRepo @ tags/release/1.0 (tag_sha)>"
        )

    @responses.activate
    def test_resolve__no_release(self):
        responses.add(
            method=responses.GET,
            url=self.repo_api_url,
            json=self._get_expected_repo(owner="TestOwner", name="TestRepo"),
        )
        responses.add(
            "GET",
            "https://api.github.com/repos/TestOwner/TestRepo/releases/latest",
            status=404,
        )
        responses.add(
            "GET",
            f"https://api.github.com/repos/TestOwner/TestRepo/git/refs/heads/master",
            json=self._get_expected_ref("heads/master", "abcdef"),
        )

        source = GitHubSource(
            self.project_config, {"github": "https://github.com/TestOwner/TestRepo.git"}
        )
        assert (
            repr(source)
            == "<GitHubSource GitHub: TestOwner/TestRepo @ master (abcdef)>"
        )

    @responses.activate
    def test_resolve__commit(self):
        responses.add(
            method=responses.GET,
            url=self.repo_api_url,
            json=self._get_expected_repo(owner="TestOwner", name="TestRepo"),
        )

        source = GitHubSource(
            self.project_config,
            {"github": "https://github.com/TestOwner/TestRepo.git", "commit": "abcdef"},
        )
        assert repr(source) == "<GitHubSource GitHub: TestOwner/TestRepo @ abcdef>"

    @responses.activate
    def test_resolve__ref(self):
        responses.add(
            method=responses.GET,
            url=self.repo_api_url,
            json=self._get_expected_repo(owner="TestOwner", name="TestRepo"),
        )
        responses.add(
            "GET",
            f"https://api.github.com/repos/TestOwner/TestRepo/git/refs/master",
            json=self._get_expected_ref("master", "abcdef"),
        )

        source = GitHubSource(
            self.project_config,
            {"github": "https://github.com/TestOwner/TestRepo.git", "ref": "master"},
        )
        assert (
            repr(source)
            == "<GitHubSource GitHub: TestOwner/TestRepo @ master (abcdef)>"
        )

    @responses.activate
    def test_resolve__branch(self):
        responses.add(
            method=responses.GET,
            url=self.repo_api_url,
            json=self._get_expected_repo(owner="TestOwner", name="TestRepo"),
        )
        responses.add(
            "GET",
            f"https://api.github.com/repos/TestOwner/TestRepo/git/refs/heads/master",
            json=self._get_expected_ref("master", "abcdef"),
        )

        source = GitHubSource(
            self.project_config,
            {"github": "https://github.com/TestOwner/TestRepo.git", "branch": "master"},
        )
        assert (
            repr(source)
            == "<GitHubSource GitHub: TestOwner/TestRepo @ master (abcdef)>"
        )

    @responses.activate
    def test_fetch(self):
        responses.add(
            method=responses.GET,
            url=self.repo_api_url,
            json=self._get_expected_repo(owner="TestOwner", name="TestRepo"),
        )
        responses.add(
            "GET",
            "https://api.github.com/repos/TestOwner/TestRepo/releases/latest",
            json=self._get_expected_release("release/1.0"),
        )
        responses.add(
            "GET",
            f"https://api.github.com/repos/TestOwner/TestRepo/git/refs/tags/release/1.0",
            json=self._get_expected_tag_ref("release/1.0", "tag_sha"),
        )
        f = io.BytesIO()
        zf = zipfile.ZipFile(f, "w")
        zfi = zipfile.ZipInfo("toplevel/")
        zf.writestr(zfi, "")
        zf.writestr(
            "toplevel/cumulusci.yml",
            yaml.dump(
                {
                    "project": {
                        "package": {"name_managed": "Test Product", "namespace": "ns"}
                    }
                }
            ),
        )
        zf.close()
        responses.add(
            "GET",
            "https://api.github.com/repos/TestOwner/TestRepo/zipball/tag_sha",
            body=f.getvalue(),
            content_type="application/zip",
        )

        source = GitHubSource(
            self.project_config, {"github": "https://github.com/TestOwner/TestRepo.git"}
        )
        with temporary_dir() as d:
            project_config = source.fetch()
            assert isinstance(project_config, BaseProjectConfig)
            assert project_config.repo_root == os.path.join(
                os.path.realpath(d), ".cci", "projects", "TestRepo", "tag_sha"
            )

    @responses.activate
    def test_resolve__tag(self):
        responses.add(
            method=responses.GET,
            url=self.repo_api_url,
            json=self._get_expected_repo(owner="TestOwner", name="TestRepo"),
        )
        responses.add(
            "GET",
            f"https://api.github.com/repos/TestOwner/TestRepo/git/refs/tags/release/1.0",
            json=self._get_expected_tag_ref("release/1.0", "abcdef"),
        )

        source = GitHubSource(
            self.project_config,
            {
                "github": "https://github.com/TestOwner/TestRepo.git",
                "tag": "release/1.0",
            },
        )
        assert (
            repr(source)
            == "<GitHubSource GitHub: TestOwner/TestRepo @ tags/release/1.0 (abcdef)>"
        )

    @responses.activate
    def test_hash(self):
        responses.add(
            method=responses.GET,
            url=self.repo_api_url,
            json=self._get_expected_repo(owner="TestOwner", name="TestRepo"),
        )
        responses.add(
            "GET",
            "https://api.github.com/repos/TestOwner/TestRepo/releases/latest",
            json=self._get_expected_release("release/1.0"),
        )
        responses.add(
            "GET",
            f"https://api.github.com/repos/TestOwner/TestRepo/git/refs/tags/release/1.0",
            json=self._get_expected_tag_ref("release/1.0", "tag_sha"),
        )

        source = GitHubSource(
            self.project_config, {"github": "https://github.com/TestOwner/TestRepo.git"}
        )
        assert hash(source) == hash(
            ("https://github.com/TestOwner/TestRepo", "tag_sha")
        )

    @responses.activate
    def test_frozenspec(self):
        responses.add(
            method=responses.GET,
            url=self.repo_api_url,
            json=self._get_expected_repo(owner="TestOwner", name="TestRepo"),
        )
        responses.add(
            "GET",
            "https://api.github.com/repos/TestOwner/TestRepo/releases/latest",
            json=self._get_expected_release("release/1.0"),
        )
        responses.add(
            "GET",
            f"https://api.github.com/repos/TestOwner/TestRepo/git/refs/tags/release/1.0",
            json=self._get_expected_tag_ref("release/1.0", "tag_sha"),
        )

        source = GitHubSource(
            self.project_config, {"github": "https://github.com/TestOwner/TestRepo.git"}
        )
        assert source.frozenspec == {
            "github": "https://github.com/TestOwner/TestRepo",
            "commit": "tag_sha",
            "description": "tags/release/1.0",
        }


class TestLocalFolderSource:
    def test_fetch(self):
        project_config = BaseProjectConfig(BaseGlobalConfig())
        with temporary_dir() as d:
            touch("cumulusci.yml")
            source = LocalFolderSource(project_config, {"path": d})
            project_config = source.fetch()
            assert project_config.repo_root == os.path.realpath(d)

    def test_hash(self):
        project_config = BaseProjectConfig(BaseGlobalConfig())
        with temporary_dir() as d:
            source = LocalFolderSource(project_config, {"path": d})
            assert hash(source) == hash((source.path,))

    def test_repr(self):
        project_config = BaseProjectConfig(BaseGlobalConfig())
        with temporary_dir() as d:
            source = LocalFolderSource(project_config, {"path": d})
            assert repr(source) == f"<LocalFolderSource Local folder: {d}>"

    def test_frozenspec(self):
        project_config = BaseProjectConfig(BaseGlobalConfig())
        with temporary_dir() as d:
            source = LocalFolderSource(project_config, {"path": d})
            with pytest.raises(NotImplementedError):
                source.frozenspec
