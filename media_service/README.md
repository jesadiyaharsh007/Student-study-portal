# Video service

The website on Vercel cannot stream YouTube videos itself (YouTube blocks data-center addresses and serverless
functions forget everything between requests). Until you run this service, the live site plays videos through
YouTube's official embed, which works but has YouTube's own controls and cannot play videos whose owners disallow
embedding.

This service is a small always-on server that does the streaming. With it, the live site plays videos with the
portal's own player (quality menu, speed, captions, downloads) exactly like on your computer.

## Deploy on Render.com (Recommended Free Cloud Hosting)

If your website is hosted on Vercel (`https://studentstudyportal-wheat.vercel.app`), you can deploy `media_service` on Render as a free Web Service:

1. In [Render.com](https://render.com), click **New +** → **Web Service** and connect this repository.
2. Fill out the service settings:
   - **Name**: `student-media-service` (or any name)
   - **Region**: `Singapore` (or nearest region)
   - **Branch**: `main`
   - **Root Directory**: *(leave blank)*
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r media_service/requirements.txt`
   - **Start Command**: `uvicorn media_service.app:app --host 0.0.0.0 --port $PORT`
   - **Plan**: `Free`
3. Add Environment Variables in Render:
   - `MEDIA_SERVICE_SECRET` = `studysecret_2026_xyz_secure`
   - `ALLOWED_ORIGINS` = `https://studentstudyportal-wheat.vercel.app`
   - `PYTHON_VERSION` = `3.11.8`
4. Connect Vercel to Render:
   - Once Render finishes deploying and is Live, copy the Render URL (e.g. `https://student-media-service.onrender.com`).
   - In your **Vercel Project Settings** → **Environment Variables**, add:
     - `MEDIA_SERVICE_URL` = `https://student-media-service.onrender.com`
     - `MEDIA_SERVICE_SECRET` = `studysecret_2026_xyz_secure`
   - Redeploy Vercel.

---

## Alternative: Self-Hosted Docker Server

### 1. Get a server

Any small Linux server with a public IP: Hetzner, DigitalOcean, Vultr, an Oracle free VM, and so on (1 GB of RAM
is enough). A home-style or less commonly blocked address works best with YouTube. Point a domain name such as
`media.yourdomain.com` at it (an A record).

## 2. Install Docker and copy the project

```bash
curl -fsSL https://get.docker.com | sh
git clone https://github.com/<you>/Student-study-portal.git && cd Student-study-portal
```

## 3. Settings

Make a secret and write `media_service/.env`:

```bash
openssl rand -hex 32
```

```
MEDIA_SERVICE_SECRET=<the secret you just made>
ALLOWED_ORIGINS=https://<your-vercel-site>.vercel.app
```

Edit `media_service/Caddyfile` and put your video domain in place of `media.example.com`.

## 4. Start it

```bash
docker compose -f media_service/docker-compose.yml up -d --build
curl https://media.yourdomain.com/health          # should answer {"ok":true,...}
```

yt-dlp updates itself every time the container starts. Restart it daily so it stays current:

```bash
( crontab -l 2>/dev/null; echo "0 4 * * * docker restart \$(docker ps -qf name=video)" ) | crontab -
```

## 5. Tell the website about it

In the Vercel project (Settings, Environment Variables), add the same two values and redeploy:

```
MEDIA_SERVICE_URL=https://media.yourdomain.com
MEDIA_SERVICE_SECRET=<the same secret>
```

The website now gives the player a signed pass that is good for two hours, and the player talks to your video
service directly. If the service cannot get a particular video, the player falls back to YouTube's embed for that
video, so something always plays.

## Notes

- If videos suddenly stop working, run `docker compose ... up -d --build` again to get the latest yt-dlp.
- To try it on your own computer first: `uvicorn media_service.app:app --port 8080` with the same two environment variables.
