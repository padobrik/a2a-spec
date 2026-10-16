{
  description = "Contract tests for agent handoffs: record, infer, check in CI without LLM calls.";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  };

  outputs =
    { nixpkgs, ... }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forSystems =
        f: nixpkgs.lib.genAttrs systems (system: f (import nixpkgs { inherit system; }));
    in
    {
      packages = forSystems (
        pkgs:
        let
          pythonPkgs = pkgs.python3.pkgs;
          # The version comes from pyproject.toml, so the flake cannot drift
          # from the package it builds.
          version = (builtins.fromTOML (builtins.readFile ./pyproject.toml)).project.version;
          agent-handshake = pythonPkgs.buildPythonPackage {
            pname = "agent-handshake";
            inherit version;
            format = "pyproject";

            src = nixpkgs.lib.cleanSourceWith {
              src = ./.;
              filter =
                path: type:
                baseNameOf path != ".git" && nixpkgs.lib.cleanSourceFilter path type;
            };

            nativeBuildInputs = [ pythonPkgs.hatchling ];

            dependencies = with pythonPkgs; [
              typer
              rich
              pyyaml
              pydantic
              jsonschema
              httpx
            ];

            # The full suite runs here: unit tests and the end-to-end scenarios.
            # The a2a interop test skips itself when a2a-sdk lacks
            # a2a.server.routes, which is the case for the nixpkgs build
            # (0.3.x); CI keeps its Python matrix as the a2a gate.
            nativeCheckInputs = with pythonPkgs; [
              pytestCheckHook
              pytest-asyncio
              a2a-sdk
              tree-sitter
              tree-sitter-typescript
            ] ++ [
              pkgs.git
            ];

            preCheck = ''
              export HANDSHAKE_BIN="$out/bin/handshake"
              export NO_COLOR=1
            '';

            doInstallCheck = false;
          };
        in
        {
          default = agent-handshake;
          inherit agent-handshake;
        }
      );

      devShells = forSystems (
        pkgs:
        {
          default = pkgs.mkShell {
            packages = [
              (pkgs.python3.withPackages (
                ps: with ps; [
                  typer
                  rich
                  pyyaml
                  pydantic
                  jsonschema
                  httpx
                  pytest
                  pytest-asyncio
                  pytest-cov
                  a2a-sdk
                  tree-sitter
                  tree-sitter-typescript
                ]
              ))
              pkgs.ruff
              pkgs.mypy
              pkgs.git
            ];
            shellHook = ''
              echo "agent-handshake dev shell: pip install -e '.[dev,typescript]' first,"
              echo "then: make lint / make test / make typecheck"
            '';
          };
        }
      );

      formatter = forSystems (pkgs: pkgs.nixpkgs-fmt);
    };
}
