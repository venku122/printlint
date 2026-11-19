# Set up PrintLint on your machine

PrintLint checks STL and 3MF files, inspects color and tool assignments, and
audits annotated slicer output. Use your own slicer, printer settings, and
filament inventory. The included default printer policy is for a Bambu Lab
X2D. It is suitable for the included smoke-test files.

The ZIP contains the source, pinned dependency declarations, setup script,
Dockerfile, and test models. Setup needs internet access to fetch public
dependencies. Keep the extracted folder together.

## macOS native setup

Install Git, Python 3.12, uv, and Node.js 22 or newer with npm. Open Terminal
in the extracted PrintLint folder and run:

```sh
./tools/setup.sh
uv run --locked printlint check tests/fixtures/cube.stl --json
uv run --locked printlint check tests/fixtures/core-colored.3mf --json
```

Both smoke tests should return exit code 0. For native slicing, separately
install Bambu Studio or stable OrcaSlicer in `/Applications`. Save a project
with your printer's actual machine, process, and filament profiles. Then run
`uv run --locked printlint slice project.3mf --slicer bambu --output ./new-slice`
or use `--slicer orca-stable`. The output directory must be empty. Supply
`--policy` for your printer when it differs from the X2D. See
[optional native Orca plugin setup](docs/slicer-integration.md#native-plugin)
for the separately validated experimental Orca build.

## Windows or Linux validation with Docker

Start Docker with Linux container support. From the extracted PrintLint
folder, build the pinned image:

```sh
docker build --tag printlint:local .
```

In PowerShell:

```powershell
$fixtures = (Resolve-Path .\tests\fixtures).Path
docker run --rm --network none --read-only --tmpfs /tmp:rw,nosuid,nodev,size=256m --mount "type=bind,source=$fixtures,target=/models,readonly" printlint:local check core-colored.3mf --json
```

In Linux or WSL:

```sh
docker run --rm --network none --read-only --tmpfs /tmp:rw,nosuid,nodev,size=256m \
  --mount "type=bind,source=$PWD/tests/fixtures,target=/models,readonly" \
  printlint:local check core-colored.3mf --json
```

A successful check returns exit code 0. Replace the mount source with your own
model folder and the last filename with the file you want to check. Put your
policy JSON in that folder and pass `--policy /models/local-printer.json`.
You can also use `colors`, `inspect-final`, or `dfam` in the container. Use
your desktop slicer for actual slicing and preview on Windows or Linux.
See [container details](docs/container.md).

## Adapt the policy before checking your own prints

Copy [the example policy](config/x2d.example.json) to a local file. For a K1C
or any other printer, verify and replace the printer name and profile,
build envelope, nozzle count and diameters, and tool reach. A single-tool
machine needs one nozzle entry and its own one-entry tool reach. Check
extrusion width, layer height, material, and the wall and overhang thresholds
against your active process. Replace the example provenance with your own
settings source.

If you use a material manifest, start with
[the example](config/filaments.example.json) and fill in only observed
assignments for your printer. Review the exact slicer preview, especially
the first layer, support contacts, and tool routing before manually sending
a job. To check required process values and compare the final G-code hash,
see [job-specific profile checks](README.md#job-specific-profile-checks-and-final-receipts).
