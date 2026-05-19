# Dynamically pull the absolute latest stable release of Music Assistant
FROM ghcr.io/music-assistant/server:latest

# Overlay custom providers into the venv (Python minor version varies: 3.13, 3.14, …)
COPY music_providers/ytmusic /tmp/overlay/ytmusic
COPY music_providers/zing /tmp/overlay/zing

RUN PYDIR=$(ls -d /app/venv/lib/python3.* 2>/dev/null | head -1) \
    && test -n "$PYDIR" || (echo "ERROR: no python3.* venv under /app/venv/lib" && exit 1) \
    && PROVIDERS="${PYDIR}/site-packages/music_assistant/providers" \
    && echo "Overlaying providers into ${PROVIDERS}" \
    && rm -rf "${PROVIDERS}/ytmusic" \
    && cp -a /tmp/overlay/ytmusic "${PROVIDERS}/ytmusic" \
    && cp -a /tmp/overlay/zing "${PROVIDERS}/zing" \
    && rm -rf /tmp/overlay \
    && ! grep -q "User does not have Youtube Music Premium" "${PROVIDERS}/ytmusic/__init__.py"
