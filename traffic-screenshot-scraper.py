#!/usr/bin/env python3
import argparse, datetime, json, os, shutil, subprocess, itertools, sys
from pathlib import Path
from typing import Union

DEFAULT_KEEP_DAYS = 14
DEFAULT_FFMPEG_Q  = "2"  # lower = higher quality
SCRIPT_DIR = Path(__file__).resolve().parent

def expand_path(p):  # type: (Union[str, Path]) -> Path
    return Path(os.path.expanduser(os.path.expandvars(str(p)))).resolve()

def purge_older_than(root, days):  # type: (Path, int) -> None
    if days is None or days < 0:
        return
    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(days=days)
    for p in root.rglob("*.jpg"):
        try:
            if datetime.datetime.fromtimestamp(p.stat().st_mtime) < cutoff:
                p.unlink(missing_ok=True)
                print(f"🗑️  Purged old: {p}")
        except Exception as e:
            print(f"⚠️  Retention error for {p}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Capture timelapse frames for WV cams.")
    parser.add_argument("-n", "--limit", type=int, default=None,
                        help="Capture only the first N cams (testing). Omit for all cams.")
    parser.add_argument("--no-publish", action="store_true",
                        help="Do NOT copy files to publish dir; keep everything in staging and index there.")
    parser.add_argument("--keep-days", type=int, default=DEFAULT_KEEP_DAYS,
                        help=f"Retention window in days (default {DEFAULT_KEEP_DAYS}). Use -1 to disable.")
    parser.add_argument("--quality", type=str, default=DEFAULT_FFMPEG_Q,
                        help=f"ffmpeg -q:v value (lower = higher quality). Default {DEFAULT_FFMPEG_Q}.")
    parser.add_argument("--cams-file", type=str, default=str(SCRIPT_DIR / "cams.json"),
                        help="Path to cams.json. Default: cams.json next to this script.")
    parser.add_argument("--staging-dir", type=str, default=str(SCRIPT_DIR / "timelapse"),
                        help="Where new shots are written. Default: ./timelapse")
    parser.add_argument("--publish-dir", type=str,
                        default="~/wv-cam-ssr/dist/client/timelapse",
                        help="Published folder served by the site (ignored if --no-publish).")
    args = parser.parse_args()

    # Resolve paths
    staging_dir = expand_path(args.staging_dir)
    publish_dir = expand_path(args.publish_dir)

    # Find cams.json (try a few places)
    cam_candidates = [args.cams_file, SCRIPT_DIR / "cams.json", "./cams.json", "/cams.json"]
    cams_file = None
    for c in cam_candidates:
        p = expand_path(c)
        if p.exists():
            cams_file = p
            break
    if cams_file is None:
        print("❌ cams.json not found in any of:", ", ".join(map(str, cam_candidates)))
        sys.exit(1)

    print("📁 Using paths/mode:")
    print(f"   cams_file     = {cams_file}")
    print(f"   staging_dir   = {staging_dir}")
    if args.no_publish:
        print(f"   publish_dir   = (disabled)")
        print(f"   index_root    = staging (frames.json written under staging)")
    else:
        print(f"   publish_dir   = {publish_dir}")
        print(f"   index_root    = publish")

    # Load cams
    with open(cams_file, "r") as f:
        cams_data = json.load(f)

    staging_dir.mkdir(parents=True, exist_ok=True)
    if not args.no_publish:
        publish_dir.mkdir(parents=True, exist_ok=True)

    # Purge old screenshots
    purge_older_than(staging_dir, args.keep_days)
    if not args.no_publish:
        purge_older_than(publish_dir, args.keep_days)

    # Flatten cam list; apply optional limit
    all_cams = (cam for county in cams_data for cam in county.get("cams", []))
    if args.limit is not None and args.limit >= 0:
        all_cams = itertools.islice(all_cams, args.limit)

    touched = set()
    ts = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

    # Capture one frame per selected cam
    for cam in all_cams:
        cam_id = cam.get("id")
        stream_url = cam.get("stream")
        if not cam_id or not stream_url:
            continue

        stage_cam = staging_dir / cam_id
        stage_cam.mkdir(parents=True, exist_ok=True)
        filename = f"{ts}.jpg"
        stage_path = stage_cam / filename

        cmd = ["ffmpeg", "-y", "-i", stream_url, "-frames:v", "1", "-q:v", args.quality, str(stage_path)]

        try:
            print(f"🎥 Capturing {cam_id}…")
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"✅ Saved {stage_path}")

            if not args.no_publish:
                pub_cam = publish_dir / cam_id
                pub_cam.mkdir(parents=True, exist_ok=True)
                shutil.copy2(stage_path, pub_cam / filename)
                print(f"➡️  Published to {pub_cam / filename}")

            touched.add(cam_id)
        except subprocess.CalledProcessError:
            print(f"❌ Failed to capture {cam_id} ({stream_url})")
            continue

    # Rebuild frames.json under the chosen index root
    index_root = staging_dir if args.no_publish else publish_dir
    for cam_id in touched:
        cam_folder = index_root / cam_id
        if cam_folder.is_dir():
            frames = sorted([p.name for p in cam_folder.glob("*.jpg")])
            with open(cam_folder / "frames.json", "w") as f:
                json.dump(frames, f)

    print(f"✅ Timelapse updated. Indexed {len(touched)} cam(s) under: {index_root}")

if __name__ == "__main__":
    main()
