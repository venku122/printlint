# Portable validation container

The static validation stack can run in a Linux Docker image. Actual installed macOS Bambu Studio/OrcaSlicer executables and the native Orca Python plugin remain on the Mac. A container complements the native uv/setup script; it does not replace native slicer or plugin acceptance.

## Build and run

From the repository root:

```sh
docker build -t printlint:0.1.0 .
docker run --rm --network none --read-only --tmpfs /tmp:rw,nosuid,nodev,size=256m \
  --mount "type=bind,src=$PWD/tests/fixtures,dst=/models,readonly" \
  printlint:0.1.0 check cube.stl --json
docker run --rm --network none --read-only --tmpfs /tmp:rw,nosuid,nodev,size=256m \
  --mount "type=bind,src=$PWD/tests/fixtures,dst=/models,readonly" \
  printlint:0.1.0 check core-colored.3mf --json
docker run --rm --network none --read-only --tmpfs /tmp:rw,nosuid,nodev,size=256m \
  --mount "type=bind,src=$PWD/tests/fixtures,dst=/models,readonly" \
  printlint:0.1.0 colors painted.3mf --json
```

Replace the bind source with the model directory. Models remain read-only; stdout can be redirected to a host report. Policies/manifests can be mounted read-only and supplied with paths inside the container. The image runs as UID/GID 65532 and needs a writable temporary directory for package/MCP inspection. It exposes no ports and requires no printer/network access at runtime. Image construction downloads pinned public dependencies and requires network access.

## Reproducibility and scope

Python 3.12.16, Node 26.13.0 and uv 0.13.6 image inputs are pinned by immutable multi-platform digests in `Dockerfile`. The frozen uv lockfile, source revisions and upstream npm lockfile pin application dependencies. Builder OS packages such as Git/CA certificates use the Debian repository and are not snapshot-pinned, so a rebuild is dependency-reproducible rather than guaranteed byte-for-byte identical. The built image ID identifies the exact local artifact; do not reuse a mutable tag as a provenance guarantee.

The build runs the official MCP tests/build and all portable PrintLint tests. Native application integration and full native doctor tests skip on Linux. `printlint doctor` in this image intentionally reports missing macOS slicers; it does not claim the complete desktop workflow is installed. `slice` likewise cannot launch the Mac apps from Linux. No Linux slicer is bundled or claimed equivalent.

The optional community advisory source is included. The runtime contains no npm/uv executable, Git, slicer apps or credentials; Node plus the built MCP and Python environment are enough for static checks. Vendor license files remain in their source trees. No image is pushed to a registry by default.

Local Docker engine requests timed out during the initial setup; the Dockerfile is verified through the repository CI when that run passes. No local image-build success is implied by the native tests.

Verified Linux/amd64 acceptance: [GitHub CI run](https://github.com/venku122/printlint/actions/runs/41232202815) for source commit `1d30e440ca522c30a45434d012118e0363ba14ac`. Official MCP: 18 tests passed; portable PrintLint: 48 passed, 4 native-only skips. Image build and read-only/no-network STL, standard/vendor 3MF and painted-color smoke checks passed. CI image ID: `sha256:77c402bfae678de195abeb71af22069c46352f9a804057d4dae96754d47d48cf`. This image was not published to a registry. Linux/arm64 execution remains unverified.
