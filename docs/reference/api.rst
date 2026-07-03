###################
 API Documentation
###################

build provides a Python API for programmatic use in build tools, CI systems, and automation scripts.

.. note::

    When not using an isolated environment, the build backend must be installed in the current environment. When using
    :class:`DefaultIsolatedEnv <build.env.DefaultIsolatedEnv>`, you must explicitly install build dependencies into the
    isolated environment via :meth:`~build.env.DefaultIsolatedEnv.install` before calling
    :meth:`~build.ProjectBuilder.build` — the environment is created empty.

*************
 Basic Usage
*************

Building a package programmatically:

.. code-block:: python

    from build import ProjectBuilder

    builder = ProjectBuilder("path/to/project")
    builder.build("wheel", "dist/")

Building both sdist and wheel:

.. code-block:: python

    from build import ProjectBuilder

    builder = ProjectBuilder(".")
    builder.build("sdist", "dist/")
    builder.build("wheel", "dist/")

Using isolated environments (default):

``DefaultIsolatedEnv`` creates a clean virtual environment, but it is initially empty. You must install the project's
build dependencies before invoking the backend:

.. code-block:: python

    from build import ProjectBuilder
    from build.env import DefaultIsolatedEnv

    with DefaultIsolatedEnv() as env:
        builder = ProjectBuilder.from_isolated_env(env, ".")
        # Install build-system.requires (e.g., flit-core, setuptools, ...)
        env.install(builder.build_system_requires)
        # Install additional backend dependencies for the target distribution
        env.install(builder.get_requires_for_build("wheel"))
        builder.build("wheel", "dist/")

Pass ``path`` to create the environment at a fixed location instead of a temporary directory. The location must be
empty; ``DefaultIsolatedEnv`` removes it on a clean exit and keeps it when the block raises:

.. code-block:: python

    with DefaultIsolatedEnv(path=".build-env") as env:
        builder = ProjectBuilder.from_isolated_env(env, ".")
        env.install(builder.build_system_requires)
        builder.build("wheel", "dist/")

Disabling isolation:

.. code-block:: python

    from build import ProjectBuilder

    builder = ProjectBuilder(".", runner=lambda cmd, **kwargs: None)
    builder.build("wheel", "dist/")

Getting package metadata without building:

.. code-block:: python

    from build import ProjectBuilder
    import tempfile

    builder = ProjectBuilder(".")
    with tempfile.TemporaryDirectory() as tmpdir:
        metadata_dir = builder.metadata_path(tmpdir)
        # Read METADATA file from metadata_dir to extract package info

Accessing build dependencies:

.. code-block:: python

    from build import ProjectBuilder

    builder = ProjectBuilder(".")
    requires = builder.build_system_requires
    print(f"Build requires: {requires}")

    # Get additional dependencies for building a wheel
    wheel_requires = builder.get_requires_for_build("wheel")
    print(f"Wheel build requires: {wheel_requires}")

Reading metadata without isolation:

.. code-block:: python

    from build.util import wheel_metadata

    # Read metadata in the current environment, but first confirm the declared
    # build dependencies are present so you can trust the result. A missing
    # setuptools_scm, for example, would otherwise report the version as 0.0.0.
    metadata = wheel_metadata(".", isolated=False, check_dependencies=True)
    print(metadata["version"])

:func:`build.util.wheel_metadata` returns the metadata as a parsed, JSON-serialisable mapping (the same structure
``python -m build --metadata`` prints). Without ``check_dependencies=True``, a non-isolated call runs the backend
against whatever you have installed and can return wrong metadata; with it, ``wheel_metadata`` raises
:class:`build.DependencyError` listing the unmet dependencies. The flag does nothing when ``isolated`` is true, since
build installs the dependencies either way.

:func:`build.util.project_wheel_metadata` predates this and returns a :class:`email.message.Message`-style object; it is
deprecated in favour of ``wheel_metadata``.

Handling errors:

.. code-block:: python

    from build import ProjectBuilder
    from build import BuildException

    try:
        builder = ProjectBuilder(".")
        builder.build("wheel", "dist/")
    except BuildException as e:
        print(f"Build failed: {e}")

***********
 Reference
***********

******************
 ``build`` module
******************

.. automodule:: build
    :members:
    :undoc-members:
    :show-inheritance:

**********************
 ``build.env`` module
**********************

.. automodule:: build.env
    :members:
    :undoc-members:
    :show-inheritance:

***********************
 ``build.util`` module
***********************

.. automodule:: build.util
    :members:
    :undoc-members:
    :show-inheritance:
