FROM python:3.12-slim
WORKDIR /srv
COPY media_service/requirements.txt media_service/requirements.txt
RUN pip install --no-cache-dir -r media_service/requirements.txt
# only the video code is needed from the website's package
COPY dashboard/__init__.py dashboard/__init__.py
COPY dashboard/videos.py dashboard/videos.py
COPY media_service/app.py media_service/app.py
COPY media_service/__init__.py media_service/__init__.py
EXPOSE 8080
# YouTube changes often: update yt-dlp every time the container starts
CMD ["sh", "-c", "pip install -U --no-cache-dir yt-dlp && uvicorn media_service.app:app --host 0.0.0.0 --port 8080 --workers 2"]
