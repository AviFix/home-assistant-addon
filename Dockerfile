# Dynamically pull the absolute latest stable release of Music Assistant
FROM ghcr.io/music-assistant/server:latest

# Ensure the Python virtual environment target directory exists
RUN mkdir -p /app/venv/lib/python3.13/site-packages/music_assistant/providers/zing

# Copy the zing folder from your local addon directory straight into the container image
COPY music_providers/zing/ /app/venv/lib/python3.13/site-packages/music_assistant/providers/zing/
