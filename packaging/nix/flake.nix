{
  description = "coredoc Linux diagnostics TUI";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in {
      packages = forAllSystems (pkgs: {
        default = pkgs.python3Packages.buildPythonApplication {
          pname = "coredoc";
          version = "0.2.0";
          src = ../..;
          pyproject = true;
          build-system = [ pkgs.python3Packages.setuptools pkgs.python3Packages.wheel ];
          dependencies = [ pkgs.python3Packages.textual ];
          doCheck = false;
        };
      });
    };
}
