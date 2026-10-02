# Deploying the dashboard (SYNTHETIC demo)

The image builds the synthetic warehouse at build time (`python -m src.build`, profile `demo`), then serves the Dash app with gunicorn.
No secrets, no external data.

## Local
```bash
make all && make app            # http://localhost:8050
# or
docker build -t gaw . && docker run -p 7860:7860 gaw
```

## Render
1. Push the repo (already on GitHub), then in Render choose **New > Blueprint** and select the repository; `render.yaml` configures a free Docker web service.
2. First build takes a few minutes (data generation + model training).

## Hugging Face Spaces
1. Create a Space with SDK **Docker**; add `app_port: 7860` to the Space's README front matter.
2. Push this repository to the Space (`git remote add space https://huggingface.co/spaces/<user>/growth-analytics-warehouse && git push space main`).

Hosted deployment was **not** performed by the automated build because no Render / Hugging Face credentials were available in the environment.
