#!/usr/bin/env bash
set -euo pipefail
# Keep the Python host runtime separate from ESP-IDF's own Python environment.
cd "$(dirname "$0")/../.."
python3.15 -m venv build/venv/python
build/venv/python/bin/python -m pip install -r host/python/requirements.txt
mkdir -p build/host/python
for spec in 'esp-con2:control.py' 'esp-con2-mcp:mcp_server.py'; do
  name="${spec%%:*}"; source="${spec#*:}"
  cat > "build/host/python/$name" <<SCRIPT
#!/usr/bin/env bash
set -euo pipefail
root="\$(cd "\$(dirname "\$0")/../../.." && pwd)"
exec "\$root/build/venv/python/bin/python" "\$root/host/python/$source" "\$@"
SCRIPT
  chmod +x "build/host/python/$name"
done
