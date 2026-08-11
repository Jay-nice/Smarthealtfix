"""
publish_latest.py — draait als aparte stap ná het pushen naar GitHub (zodat
GitHub Pages de bestanden al kan serveren). Leest output/last_run.json (weg-
geschreven door run_pipeline.py) en publiceert die reel naar Instagram.
"""

import json
import os

from instagram_publish import publish_reel


def main():
    public_base_url = os.environ["PUBLIC_BASE_URL"].rstrip("/")

    with open("output/last_run.json") as f:
        last_run = json.load(f)

    video_url = f"{public_base_url}/{last_run['mp4']}"
    cover_url = f"{public_base_url}/{last_run['cover']}"

    print(f"Video URL:  {video_url}")
    print(f"Cover URL:  {cover_url}")

    media_id = publish_reel(video_url=video_url, cover_url=cover_url,
                             caption=last_run["caption"],
                             hashtags_comment=last_run.get("hashtags_comment"))
    print(f"Gepubliceerd, media_id={media_id}")


if __name__ == "__main__":
    main()
