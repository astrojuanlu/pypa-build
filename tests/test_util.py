# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.metadata
import importlib.util
import re
import sys
import unittest.mock

import pytest
import pytest_mock

import build.util


pytestmark = pytest.mark.filterwarnings('ignore:project_wheel_metadata is deprecated:DeprecationWarning')


@pytest.mark.pypy3323bug
@pytest.mark.parametrize('isolated', [False, pytest.param(True, marks=[pytest.mark.network, pytest.mark.isolated])])
def test_wheel_metadata(package_test_setuptools: str, isolated: bool) -> None:
    metadata = build.util.wheel_metadata(package_test_setuptools, isolated)

    # Setuptools < v69.0.3 (https://github.com/pypa/setuptools/pull/4159) normalized this to dashes
    assert metadata['name'].replace('-', '_') == 'test_setuptools'
    assert metadata['version'] == '1.0.0'


@pytest.mark.network
@pytest.mark.pypy3323bug
def test_wheel_metadata_isolation(package_test_flit: str) -> None:
    if importlib.util.find_spec('flit_core'):
        pytest.xfail('flit_core is available -- we want it missing!')  # pragma: no cover

    metadata = build.util.wheel_metadata(package_test_flit)

    assert metadata['name'] == 'test_flit'
    assert metadata['version'] == '1.0.0'

    with pytest.raises(
        build.BuildBackendException,
        match=re.escape("Backend 'flit_core.buildapi' is not available."),
    ):
        build.util.wheel_metadata(package_test_flit, isolated=False)


@pytest.mark.network
@pytest.mark.pypy3323bug
def test_with_get_requires(package_test_metadata: str) -> None:
    metadata = build.util.wheel_metadata(package_test_metadata)

    # Setuptools < v69.0.3 (https://github.com/pypa/setuptools/pull/4159) normalized this to dashes
    assert metadata['name'].replace('-', '_') == 'test_metadata'
    assert str(metadata['version']) == '1.0.0'
    assert metadata['summary'] == 'hello!'


@pytest.fixture
def metadata(mocker: pytest_mock.MockerFixture) -> unittest.mock.MagicMock:
    return mocker.patch('build.util._wheel_metadata')


@pytest.fixture
def builder(mocker: pytest_mock.MockerFixture) -> unittest.mock.MagicMock:
    builder = mocker.create_autospec(build.ProjectBuilder, instance=True)
    mocker.patch('build.util.ProjectBuilder', return_value=builder)
    return builder


@pytest.fixture
def isolated_env(mocker: pytest_mock.MockerFixture) -> tuple[unittest.mock.MagicMock, unittest.mock.MagicMock]:
    env = mocker.MagicMock()
    env_cm = mocker.MagicMock()
    env_cm.__enter__.return_value = env
    env_cm.__exit__.return_value = False
    mocker.patch('build.util.DefaultIsolatedEnv', return_value=env_cm)

    builder = mocker.create_autospec(build.ProjectBuilder, instance=True)
    builder.build_system_requires = {'dep1'}
    builder.get_requires_for_build.return_value = {'dep2'}
    mocker.patch('build.util.ProjectBuilder.from_isolated_env', return_value=builder)
    return env, builder


@pytest.mark.usefixtures('isolated_env')
def test_project_wheel_metadata_is_deprecated(mocker: pytest_mock.MockerFixture) -> None:
    result = mocker.patch('build.util._project_wheel_metadata')

    with pytest.warns(DeprecationWarning, match='use build.util.wheel_metadata'):
        assert build.util.project_wheel_metadata('/tmp/project') is result.return_value


@pytest.mark.pypy3323bug
def test_project_wheel_metadata_non_isolated(package_test_setuptools: str) -> None:
    with pytest.warns(DeprecationWarning, match='use build.util.wheel_metadata'):
        metadata = build.util.project_wheel_metadata(package_test_setuptools, isolated=False)

    # Setuptools < v69.0.3 (https://github.com/pypa/setuptools/pull/4159) normalized this to dashes
    assert metadata['Name'].replace('-', '_') == 'test_setuptools'
    assert metadata['Version'] == '1.0.0'


@pytest.mark.parametrize(
    ('check_dependencies', 'validated'),
    [
        pytest.param(True, True, id='opt-in-validates'),
        pytest.param(False, False, id='default-skips-check'),
    ],
)
def test_wheel_metadata_returns_metadata_when_satisfied(
    builder: unittest.mock.MagicMock,
    metadata: unittest.mock.MagicMock,
    check_dependencies: bool,
    validated: bool,
) -> None:
    builder.check_dependencies.return_value = set()

    result = build.util.wheel_metadata('/tmp/project', isolated=False, check_dependencies=check_dependencies)

    assert result is metadata.return_value
    assert builder.check_dependencies.called is validated


def test_wheel_metadata_raises_on_unmet_dependencies(
    builder: unittest.mock.MagicMock, metadata: unittest.mock.MagicMock
) -> None:
    builder.check_dependencies.return_value = {('dep1',), ('dep2', 'dep2-extra')}

    with pytest.raises(build.DependencyError) as exc_info:
        build.util.wheel_metadata('/tmp/project', isolated=False, check_dependencies=True)

    assert exc_info.value.unmet == {('dep1',), ('dep2', 'dep2-extra')}
    metadata.assert_not_called()


def test_wheel_metadata_check_dependencies_ignored_when_isolated(
    isolated_env: tuple[unittest.mock.MagicMock, unittest.mock.MagicMock], metadata: unittest.mock.MagicMock
) -> None:
    _, builder = isolated_env

    assert build.util.wheel_metadata('/tmp/project', isolated=True, check_dependencies=True) is metadata.return_value

    builder.check_dependencies.assert_not_called()


@pytest.mark.parametrize(
    ('chain', 'installed_version', 'expected'),
    [
        pytest.param(('foo>=1.0',), None, '\n\tfoo>=1.0\n\t\twanted: >=1.0\n\t\tfound: not installed', id='not-installed'),
        pytest.param(('bar>=2.0',), '1.0.0', '\n\tbar>=2.0\n\t\twanted: >=2.0\n\t\tfound: 1.0.0', id='version-mismatch'),
        pytest.param(
            ('matplotlib>=2.2', 'kiwisolver'),
            None,
            '\n\tmatplotlib>=2.2 -> kiwisolver\n\t\twanted: any\n\t\tfound: not installed',
            id='chain-without-specifier',
        ),
    ],
)
def test_dependency_error_message(
    mocker: pytest_mock.MockerFixture, chain: tuple[str, ...], installed_version: str | None, expected: str
) -> None:
    if installed_version is None:
        mocker.patch('build._compat.importlib.metadata.distribution', side_effect=importlib.metadata.PackageNotFoundError)
    else:
        mocker.patch('build._compat.importlib.metadata.distribution', return_value=mocker.MagicMock(version=installed_version))

    error = build.DependencyError({chain})

    assert str(error) == f'Unmet dependencies (checked against {sys.executable}):{expected}'


def test_wheel_metadata_installs_build_requires(
    isolated_env: tuple[unittest.mock.MagicMock, unittest.mock.MagicMock],
    metadata: unittest.mock.MagicMock,
    mocker: pytest_mock.MockerFixture,
) -> None:
    env, _ = isolated_env

    assert build.util.wheel_metadata('/tmp/project') is metadata.return_value

    assert env.install.call_args_list == [
        mocker.call({'dep1'}, _fresh=True),
        mocker.call({'dep2'}),
    ]
