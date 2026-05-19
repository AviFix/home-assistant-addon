# Dynamically pull the absolute latest stable release of Music Assistant
FROM ghcr.io/music-assistant/server:latest
RUN rm -rf /app/venv/lib/python3.13/site-packages/music_assistant/providers/ytmusic

# Copy the zing folder from your local addon directory straight into the container image
COPY music_providers/zing/ /app/venv/lib/python3.13/site-packages/music_assistant/providers/zing/
COPY music_providers/ytmusic/ /app/venv/lib/python3.13/site-packages/music_assistant/providers/ytmusic/
