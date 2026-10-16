{
  description = "agent-handshake: contract tests for agent handoffs";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs }:
    let
      inherit (nixpkgs) lib;
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = f: lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
      pyproject = lib.importTOML ./pyproject.toml;
      inherit (pyproject.project) optional-dependencies;

      # Python packages for requirement strings from pyproject.toml, so a
      # dependency added there is used here too: "typer>=0.12,<1.0" -> ps.typer.
      fromRequirements =
        ps: requirements:
        map (
          requirement: ps.${lib.toLower (lib.head (builtins.match "([A-Za-z0-9_.-]+).*" requirement))}
        ) requirements;

      # Only nixpkgs' default Python is built and cached by Hydra; CI tests
      # 3.11 to 3.13 with pip.
      python = pkgs: pkgs.python3;

      # Runtime dependencies and the typescript extra.
      dependencies =
        ps: fromRequirements ps (pyproject.project.dependencies ++ optional-dependencies.typescript);

      # The dev extra without a2a-sdk (1.x is not in nixpkgs; tests/test_a2a_interop.py
      # skips itself) and pre-commit (not a Python library in nixpkgs).
      devDependencies =
        ps:
        fromRequirements ps (
          lib.filter (
            r: !(lib.hasPrefix "a2a-sdk" r || lib.hasPrefix "pre-commit" r)
          ) optional-dependencies.dev
        );

      mkPackage =
        pkgs:
        let
          py = python pkgs;
        in
        py.pkgs.buildPythonApplication {
          pname = pyproject.project.name;
          inherit (pyproject.project) version;
          pyproject = true;

          src = lib.fileset.toSource {
            root = ./.;
            fileset = lib.fileset.unions [
              ./pyproject.toml
              ./README.md
              ./LICENSE
              ./src
              ./tests
              ./examples
              ./scripts
              ./CHANGELOG.md
            ];
          };

          build-system = [ py.pkgs.hatchling ];
          dependencies = dependencies py.pkgs;

          nativeCheckInputs = [
            pkgs.git
            py.pkgs.pytestCheckHook
            py.pkgs.pytest-asyncio
          ];
          # The e2e scenarios run the installed handshake command and pytest
          # with the package importable, as CI does against the wheel.
          preCheck = ''
            export HOME=$(mktemp -d)
            export PATH=$out/bin:$PATH
            export PYTHONPATH=$out/${py.sitePackages}:$PYTHONPATH
          '';
          pythonImportsCheck = [
            "agent_handshake"
            "agent_handshake.infer.ts_consumer"
          ];

          meta = {
            inherit (pyproject.project) description;
            homepage = pyproject.project.urls.Homepage;
            license = lib.licenses.asl20;
            mainProgram = "handshake";
          };
        };
    in
    {
      packages = forAllSystems (pkgs: rec {
        agent-handshake = mkPackage pkgs;
        default = agent-handshake;
      });

      # The package build runs the test suite.
      checks = self.packages;

      devShells = forAllSystems (
        pkgs:
        let
          py = python pkgs;
          tools = [
            pkgs.git
            pkgs.actionlint
            pkgs.zizmor
            pkgs.pre-commit
          ];
          # The checkout installed in editable mode: the handshake command and
          # the pytest plugin entry point run the code under ./src.
          editable = py.pkgs.mkPythonEditablePackage {
            pname = pyproject.project.name;
            inherit (pyproject.project) version scripts entry-points;
            root = "$AGENT_HANDSHAKE_ROOT/src";
            dependencies = dependencies py.pkgs;
          };
        in
        {
          # Everything from nixpkgs, no network needed.
          default = pkgs.mkShell {
            packages = [
              (py.withPackages (
                ps:
                [
                  editable
                  ps.build
                  ps.twine
                ]
                ++ devDependencies ps
              ))
            ]
            ++ tools;
            shellHook = ''
              export AGENT_HANDSHAKE_ROOT=$PWD
            '';
          };

          # The setup from CONTRIBUTING.md and CI: a .venv with the dev and
          # typescript extras from PyPI, so ruff, mypy and a2a-sdk match CI.
          # It is reinstalled only when pyproject.toml is newer than the .venv.
          uv = pkgs.mkShell {
            packages = [
              py
              pkgs.uv
            ]
            ++ tools;
            env.UV_PYTHON_DOWNLOADS = "never";
            shellHook = ''
              [ -d .venv ] || uv venv --quiet --python ${lib.getExe py} .venv
              if [ pyproject.toml -nt .venv/.agent-handshake-installed ]; then
                uv pip install --quiet --python .venv/bin/python -e ".[dev,typescript]" \
                  && touch .venv/.agent-handshake-installed \
                  || echo "agent-handshake: uv pip install failed; .venv may be out of date" >&2
              fi
              source .venv/bin/activate
            '';
          };
        }
      );

      formatter = forAllSystems (pkgs: pkgs.nixfmt-rfc-style);
    };
}
