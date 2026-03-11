{
  description = "Development shell for brianmicklethwait.com archive converters";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
    in {
      devShells.${system}.default = pkgs.mkShell {
        name = "brian-archive-converter";
        buildInputs = with pkgs; [
          python311
          uv
          ruff
        ];

        shellHook = ''
          export PATH="$(pwd):$PATH"
          echo "Converter development shell ready."
          echo "Run 'uv run convert_blog culture' or 'uv run audit_blog culture'."
        '';
      };
    };
}
