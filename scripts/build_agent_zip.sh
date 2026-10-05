#!/usr/bin/env bash
# B9 direct code deployment — build a Linux/ARM64 Python zip on Windows without Docker,
# and without WSL. Fixes the pywin32 failure: uv's --python-platform makes it resolve
# dependency markers against the TARGET platform, not the Windows host running pip.
#
# Usage (Git Bash): bash scripts/build_agent_zip.sh [source-dir] [tag]
#   source-dir defaults to ./agent (expects main.py + requirements.txt there)
#   tag is a label only, used in the printed S3 version note
# Set BUILD_ONLY=true to build locally without uploading or replacing the live artifact.
source "$(dirname "$0")/_common.sh"

SRC="${1:-$REPO_ROOT/agent}"
TAG="${2:-v$(date +%Y%m%d%H%M%S)}"
BUILD="$REPO_ROOT/.build/agent_zip"
PKG="$BUILD/pkg"
ZIP="$BUILD/main.zip"

PY_VERSION="${AGENT_PYTHON_VERSION:-3.13}"   # must match infra var agent_code_runtime (PYTHON_3_13)
PY_PLATFORM="${AGENT_PY_PLATFORM:-aarch64-manylinux2014}"

[[ -f "$SRC/main.py" ]] || { fail "No $SRC/main.py. Pass the agent source dir as arg 1."; exit 1; }
[[ -f "$SRC/requirements.txt" ]] || { fail "No $SRC/requirements.txt"; exit 1; }
command -v uv >/dev/null 2>&1 || { fail "uv not found. Install: https://docs.astral.sh/uv/"; exit 1; }

echo "== Cleaning build dir =="
rm -rf "$BUILD"
mkdir -p "$PKG"

echo "== Installing dependencies for linux/$PY_PLATFORM, Python $PY_VERSION =="
# --python-platform is the fix for the Windows pywin32 problem: it tells uv to evaluate
# each package's platform markers (sys_platform == "win32", etc.) as if running on Linux
# ARM64, so Windows-only deps like pywin32 are correctly skipped, not installed.
uv pip install \
  --target="$PKG" \
  --python-platform "$PY_PLATFORM" \
  --python-version "$PY_VERSION" \
  --only-binary=:all: \
  -r "$SRC/requirements.txt"

echo "== Copying entry point =="
cp "$SRC/main.py" "$PKG/"
# Copy any sibling modules the agent imports (tools.py, schema.py, guard.py, ...), if present.
if [[ ! -f "$SRC/runtime.py" ]]; then
  for extra in "$SRC"/*.py; do
    base="$(basename "$extra")"
    [[ "$base" == "main.py" ]] && continue
    cp "$extra" "$PKG/"
  done
fi

# Copy runtime packages only, never the harness or demo input files.
if [[ -f "$SRC/runtime.py" ]]; then
  mkdir -p "$PKG/agent" "$PKG/store" "$PKG/evidence"
  for module in __init__ knowledge runtime schema tools validation; do
    cp "$SRC/$module.py" "$PKG/agent/"
  done
  cp "$REPO_ROOT"/store/*.py "$PKG/store/"
  cp "$REPO_ROOT/evidence/__init__.py" "$REPO_ROOT/evidence/contract.py" "$PKG/evidence/"
fi

echo "== Removing __pycache__ (AgentCore rejects/ignores it; keeps the zip small) =="
find "$PKG" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

echo "== Replacing Windows .exe launchers in bin/ with Linux wrapper scripts =="
# `uv pip install --target` on Windows writes console-script launchers as bin/<name>.exe (Windows
# binaries). The runtime is Linux ARM64, so e.g. the `opentelemetry-instrument` entry point would
# not be found. Rebuild each launcher as the standard pip wrapper script from the package's own
# entry_points.txt ([console_scripts]).
"$PY" - "$PKG" <<'PYEOF'
import configparser, glob, os, sys

pkg = sys.argv[1]
bin_dir = os.path.join(pkg, "bin")
exes = {os.path.splitext(f)[0] for f in os.listdir(bin_dir) if f.lower().endswith(".exe")} if os.path.isdir(bin_dir) else set()
made = []
for ep in glob.glob(os.path.join(pkg, "*.dist-info", "entry_points.txt")):
    cp = configparser.ConfigParser(delimiters=("=",), interpolation=None)
    cp.optionxform = str  # keep names case-sensitive
    cp.read(ep, encoding="utf-8")
    if not cp.has_section("console_scripts"):
        continue
    for name, target in cp.items("console_scripts"):
        if name not in exes:
            continue
        module, _, func = target.strip().partition(":")
        func = func.split("[")[0].strip()  # drop any [extras] suffix
        script = (
            "#!/usr/bin/env python3\n"
            "# -*- coding: utf-8 -*-\n"
            "import re\nimport sys\n"
            f"from {module.strip()} import {func.split('.')[0]}\n"
            "if __name__ == '__main__':\n"
            "    sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])\n"
            f"    sys.exit({func}())\n"
        )
        with open(os.path.join(bin_dir, name), "w", encoding="utf-8", newline="\n") as fh:  # LF endings: CRLF breaks the shebang
            fh.write(script)
        os.remove(os.path.join(bin_dir, name + ".exe"))
        made.append(name)
print("wrapper scripts written:", sorted(made) or "none (no .exe launchers found)")
left = [f for f in (os.listdir(bin_dir) if os.path.isdir(bin_dir) else []) if f.lower().endswith(".exe")]
print("Windows .exe launchers left in bin/:", left or "none")
PYEOF

echo "== Zipping with forward-slash paths and POSIX permissions =="
# Plain `zip`/Compress-Archive on Windows can write backslash separators and lose the
# executable bit. Python's zipfile module lets us force both, which is what AgentCore's
# packaging guide specifies (644 files, 755 dirs, forward slashes).
"$PY" - "$PKG" "$ZIP" <<'PYEOF'
import os, stat, sys, zipfile

src, out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            full = os.path.join(root, name)
            arc = os.path.relpath(full, src).replace(os.sep, "/")
            info = zipfile.ZipInfo(arc)
            info.external_attr = (0o755 << 16) if os.access(full, os.X_OK) else (0o644 << 16)
            with open(full, "rb") as f:
                zf.writestr(info, f.read(), zipfile.ZIP_DEFLATED)
print(f"Wrote {out} ({os.path.getsize(out) / 1e6:.1f} MB)")
PYEOF

SIZE=$(stat -c%s "$ZIP" 2>/dev/null || stat -f%z "$ZIP")
if (( SIZE > 250 * 1024 * 1024 )); then
  fail "Zip is $((SIZE / 1024 / 1024)) MB; AgentCore's limit is 250 MB zipped."
  exit 1
fi
ok "Zipped: $ZIP ($((SIZE / 1024 / 1024)) MB)"

echo "== Checking for non-ARM64 native binaries (best-effort; real check happens on deploy) =="
if command -v file >/dev/null 2>&1; then
  BAD=0
  while IFS= read -r so; do
    if ! file "$so" | grep -qi "aarch64\|ARM aarch64"; then
      warn "Possibly non-ARM64: $so ($(file -b "$so"))"
      BAD=1
    fi
  done < <(find "$PKG" -name "*.so" 2>/dev/null)
  [[ $BAD -eq 0 ]] && ok "No obviously non-ARM64 .so files found."
fi

if [[ "${BUILD_ONLY:-false}" == "true" ]]; then
  ok "Local build only: $ZIP (not uploaded)"
  exit 0
fi

echo "== Uploading to S3 =="
BUCKET="$(tf_out data_bucket)"
KEY="$(terraform -chdir="$INFRA_DIR" output -raw agent_code_s3_uri | sed "s#^s3://$BUCKET/##")"
aws s3 cp "$ZIP" "s3://$BUCKET/$KEY"
VERSION_ID=$(aws s3api head-object --bucket "$BUCKET" --key "$KEY" --query VersionId --output text 2>/dev/null)

ok "Uploaded to s3://$BUCKET/$KEY (tag $TAG)"
if [[ -n "$VERSION_ID" && "$VERSION_ID" != "None" ]]; then
  echo "Bucket versioning is on. VersionId: $VERSION_ID"
  echo "To pin this exact build, set in terraform.tfvars:  agent_code_version_id = \"$VERSION_ID\""
else
  echo "Bucket versioning is off: AgentCore will always use the latest object at this key."
fi
echo "Next: set deploy_agent_runtime = true (deploy_mode already \"code\") and terraform apply."
