# Render's native (non-Docker) Python runtime doesn't grant root access
# during the build, so `playwright install --with-deps chromium` fails
# trying to install Chromium's OS-level shared libraries (confirmed: it
# tries `su` to root and gets "Authentication failure"). Microsoft's
# official Playwright Python image ships Chromium and all of its OS deps
# already installed, so no such step is needed here at all.
#
# Keep this image tag and the `playwright` version pinned in
# requirements-amd-server.txt in lockstep -- a mismatch between the
# pip-installed playwright Python package and the browser binaries baked
# into this image can make the browser fail to launch at runtime.
FROM mcr.microsoft.com/playwright/python:v1.62.0-noble

WORKDIR /app

COPY requirements-amd-server.txt .
RUN pip install --no-cache-dir -r requirements-amd-server.txt

COPY . .

CMD ["sh", "-c", "uvicorn amd_inference_server:app --host 0.0.0.0 --port ${PORT:-8000}"]
