#!/bin/bash
set -euo pipefail
umask 077
bundle=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=/opt/discuss
operation=install
allow_development=false
plan=false
provision_only=false
while (($#)); do
    case "$1" in
        --root) root=$2; shift 2;;
        --operation) operation=$2; shift 2;;
        --allow-development) allow_development=true; shift;;
        --plan) plan=true; shift;;
        --provision-only) provision_only=true; shift;;
        *) echo 'Unknown argument' >&2; exit 2;;
    esac
done
[[ "$root" =~ ^/[A-Za-z0-9_./-]+$ && "$root" != / && "$root" != *..* ]] || { echo 'Unsafe install root' >&2; exit 2; }
[[ "$operation" =~ ^(install|rollback|uninstall)$ ]] || exit 2
probe=$root
while [[ "$probe" != / ]]; do
    [[ ! -L "$probe" ]] || { echo 'Managed root cannot contain symlinks' >&2; exit 2; }
    probe=$(dirname "$probe")
done
config=$root/config.json
state=$root/state
unit=/etc/systemd/system/discuss.service
if [[ "$operation" == install ]]; then
    (cd "$bundle" && sha256sum --check --status BUNDLE_SHA256SUMS)
    grep -q '"platform": "linux-x64"' "$bundle/manifest.json" || exit 2
    if ! $allow_development; then grep -q '"qualified_dependency": true' "$bundle/manifest.json" || { echo 'Unqualified development bundle' >&2; exit 2; }; fi
fi
if $plan; then
    printf 'operation=%s\nroot=%s\nidentity=discuss\nstartup=system-level systemd\npython=3.12.15\nstate=%s\n' "$operation" "$root" "$state"
    exit 0
fi
[[ $EUID == 0 ]] || { echo 'Run as root; --plan is read-only' >&2; exit 2; }
if [[ -e "$unit" ]]; then
    grep -Fxq "# DisCuss managed root=$root" "$unit" && [[ -f "$root/current.json" ]] || { echo 'Existing service is unrelated' >&2; exit 2; }
fi
for path in "$config" "$state" "$root/releases" "$root/backups" "$root/current.json" "$root/previous.json" "$root/python" "$root/tools"; do
    [[ ! -L "$path" ]] || { echo 'Managed path cannot be a symlink' >&2; exit 2; }
done
mkdir -p "$root" "$root/backups"
chmod 755 "$root"
chmod 700 "$root/backups"
was_active=false
systemctl is-active --quiet discuss.service && was_active=true
saved_unit=$(mktemp "$root/backups/unit.XXXXXX")
[[ ! -f "$unit" ]] || cp -- "$unit" "$saved_unit"
saved_current=$(mktemp "$root/backups/current.XXXXXX")
[[ ! -f "$root/current.json" ]] || cp -- "$root/current.json" "$saved_current"
if [[ -f "$unit" ]]; then systemctl stop discuss.service; fi
switched=false
activated=false
restore_registration() {
    if ! $switched; then
        systemctl stop discuss.service 2>/dev/null || true
        if $activated && [[ -n "${current_python:-}" && -f "${snapshot:-}/statistics.sqlite3" ]]; then
            "$current_python" "$(dirname "$(dirname "$(dirname "$current_python")")")/manage_state.py" restore --config "$config" --state "$state" --snapshot "$snapshot"
            chown discuss:discuss "$config" "$state/statistics.sqlite3"
        fi
        if [[ -s "$saved_current" ]]; then cp -- "$saved_current" "$root/current.json"; fi
        if [[ -s "$saved_unit" ]]; then cp -- "$saved_unit" "$unit"; else rm -f -- "$unit"; fi
        systemctl daemon-reload
        if $was_active; then systemctl reset-failed discuss.service; systemctl start discuss.service; fi
    fi
}
trap restore_registration EXIT
if [[ "$operation" == uninstall ]]; then
    systemctl disable discuss.service 2>/dev/null || true
    rm -f -- "$unit"
    systemctl daemon-reload
    switched=true
    echo 'Startup removed; config/state/models/releases/recovery snapshots retained.'
    exit 0
fi
getent passwd discuss >/dev/null || useradd --system --home-dir "$state" --shell /usr/sbin/nologin discuss
mkdir -p "$state"
chmod 700 "$state"
chown discuss:discuss "$state"
snapshot=$root/backups/$(date -u +%Y%m%dT%H%M%S)-$RANDOM
current_python=
previous_config_ready=false
if [[ -f "$root/current.json" ]]; then
    current_python=$(sed -n 's/.*"python": "\([^"]*\)".*/\1/p' "$root/current.json")
    [[ "$current_python" == "$root/releases/"*/venv/bin/python && -x "$current_python" ]] || exit 2
    "$current_python" -m discuss.cli --config "$config" doctor >/dev/null && previous_config_ready=true
    "$current_python" "$(dirname "$(dirname "$(dirname "$current_python")")")/manage_state.py" backup --config "$config" --state "$state" --snapshot "$snapshot"
    cp -- "$saved_unit" "$snapshot/service.unit"
fi
if [[ "$operation" == rollback ]]; then
    [[ -n "$current_python" && -f "$root/previous.json" ]] || { echo 'No previous recovery snapshot' >&2; exit 2; }
    previous=$root/previous.json
    python=$(sed -n 's/.*"python": "\([^"]*\)".*/\1/p' "$previous")
    helper=$(sed -n 's/.*"helper": "\([^"]*\)".*/\1/p' "$previous")
    recovery=$(sed -n 's/.*"snapshot": "\([^"]*\)".*/\1/p' "$previous")
    [[ "$python" == "$root/releases/"*/venv/bin/python && "$helper" == "$root/releases/"*/manage_state.py && "$recovery" == "$root/backups/"* ]] || exit 2
    "$python" "$helper" restore --config "$config" --state "$state" --snapshot "$recovery"
    candidate=$previous
else
    command -v curl >/dev/null
    mkdir -p "$root/tools"
    curl --fail --location --silent --show-error https://github.com/astral-sh/uv/releases/download/0.13.0/uv-x86_64-unknown-linux-gnu.tar.gz --output "$root/tools/uv.tar.gz"
    printf '%s  %s\n' 1468ebd5a5541121837c5a2817b9972ba6090fa6caa3d142620850a47fb75154 "$root/tools/uv.tar.gz" | sha256sum --check --status
    tar -xzf "$root/tools/uv.tar.gz" -C "$root/tools"
    uv=$root/tools/uv-x86_64-unknown-linux-gnu/uv
    export UV_PYTHON_INSTALL_DIR=$root/python UV_CACHE_DIR=$root/cache UV_PYTHON_BIN_DIR=$root/tools/python-bin
    "$uv" python install 3.12.15
    bootstrap=$("$uv" python find --managed-python 3.12.15)
    verify_args=()
    $allow_development && verify_args+=(--allow-development)
    "$bootstrap" "$bundle/manage_state.py" verify --bundle "$bundle" "${verify_args[@]}"
    version=$("$bootstrap" -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$bundle/manifest.json")
    [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+[A-Za-z0-9.+-]*$ ]] || exit 2
    release=$root/releases/$version
    if [[ -f "$release/manifest.json" ]]; then cmp -- "$release/manifest.json" "$bundle/manifest.json" || { echo 'Version collision' >&2; exit 2; }; fi
    mkdir -p "$release"
    cp -- "$bundle/manage_state.py" "$release/manage_state.py"
    python=$release/venv/bin/python
    [[ -x "$python" ]] || "$uv" venv --managed-python --python 3.12.15 "$release/venv"
    if [[ -z "$current_python" && ( -f "$config" || -f "$state/statistics.sqlite3" ) ]]; then "$python" "$release/manage_state.py" backup --config "$config" --state "$state" --snapshot "$snapshot"; fi
    binary_args=()
    if ! $allow_development; then binary_args+=(--only-binary :all:); fi
    "$uv" pip install --python "$python" --require-hashes -r "$bundle/runtime-requirements.txt" "${binary_args[@]}"
    wheels=("$bundle"/*.whl)
    [[ ${#wheels[@]} == 1 ]] || exit 2
    "$uv" pip install --python "$python" --no-deps "${wheels[0]}"
    "$python" -c 'import importlib.metadata,sys; assert importlib.metadata.version("discuss")==sys.argv[1]' "$version"
    "$python" -c 'import av,numpy,faster_whisper; from discord.opus import Decoder; Decoder(); import discuss.application'
    if [[ ! -f "$config" ]]; then "$python" -c 'import json,sys; d=json.load(open(sys.argv[1])); d["state_dir"]=sys.argv[2]; json.dump(d,open(sys.argv[3],"w"),indent=2)' "$bundle/config.example.json" "$state" "$config"; fi
    "$python" -c 'import json,pathlib,sys; p=pathlib.Path(json.load(open(sys.argv[1]))["state_dir"]); assert (p if p.is_absolute() else pathlib.Path(sys.argv[1]).parent/p).resolve()==pathlib.Path(sys.argv[2]).resolve(), "state_dir must resolve to managed state"' "$config" "$state"
    cp -- "$bundle/manifest.json" "$release/manifest.json"
    chmod -R go+rX "$root/python" "$root/releases"
    candidate=$release/installed.json
    "$python" -c 'import json,sys; json.dump(dict(python=sys.argv[1],helper=sys.argv[2],version=sys.argv[3],snapshot=sys.argv[4]),open(sys.argv[5],"w"),indent=2)' "$python" "$release/manage_state.py" "$version" "$snapshot" "$candidate"
    if [[ -n "$current_python" && "$current_python" != "$python" ]]; then "$python" -c 'import json,sys; d=json.load(open(sys.argv[1])); d["snapshot"]=sys.argv[2]; json.dump(d,open(sys.argv[3],"w"),indent=2)' "$root/current.json" "$snapshot" "$root/previous.json"; fi
fi
chmod 600 "$config"
chown discuss:discuss "$config"
if [[ -f "$state/statistics.sqlite3" ]]; then chown discuss:discuss "$state/statistics.sqlite3"; fi
if "$python" -m discuss.cli --config "$config" doctor >/dev/null; then
    "$python" -m discuss.cli --config "$config" doctor --runtime
elif $previous_config_ready; then
    echo 'Candidate rejects previously valid configuration; upgrade aborted' >&2
    exit 2
fi
if ! $provision_only; then
    cat > "$unit" <<UNIT
# DisCuss managed root=$root
[Unit]
Description=DisCuss single-process voice runtime
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=3
[Service]
Type=simple
User=discuss
Group=discuss
WorkingDirectory=$root
ExecStart=$python -m discuss.cli --config $config run
Restart=on-failure
RestartSec=30
TimeoutStopSec=60
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$state
[Install]
WantedBy=multi-user.target
UNIT
    chmod 644 "$unit"
    systemctl daemon-reload
    systemctl enable discuss.service
fi
cp -- "$candidate" "$root/current.json.tmp"
mv -- "$root/current.json.tmp" "$root/current.json"
if ! $provision_only; then
    # Explicit operator installs may legitimately restart several times in minutes;
    # reset the old burst counter, without changing automatic boot fault limits.
    systemctl reset-failed discuss.service
    activated=true
    systemctl start discuss.service
    sleep 2
    [[ $(systemctl show discuss.service --property=ExecMainStatus --value) == 0 ]] || { echo 'Candidate startup failed' >&2; exit 2; }
fi
switched=true
echo 'Installed. Edit protected config, prepare model explicitly, run doctor --runtime, then start service.'
