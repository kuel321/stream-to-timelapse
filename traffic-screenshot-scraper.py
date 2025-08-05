import json
import os
import subprocess
import datetime
import shutil

count = 0
max_count = 50

cams_file = os.path.expanduser("~/timelapse-scraper/cams.json")
output_dir = os.path.expanduser("~/timelapse-scraper/timelapse")
final_destination = os.path.expanduser("~/wv-cam-ssr/dist/client/timelapse")

# Load cam data
with open(cams_file, "r") as f:
    cams_data = json.load(f)

os.makedirs(output_dir, exist_ok=True)

# 🧹 Step 1: Delete old images (>24h)
now = datetime.datetime.now()
for root, dirs, files in os.walk(output_dir):
    for file in files:
        if file.endswith(".jpg"):
            filepath = os.path.join(root, file)
            try:
                file_time = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
                if (now - file_time).total_seconds() > 86400:
                    os.remove(filepath)
                    print(f"🗑️ Deleted old file: {filepath}")
            except Exception as e:
                print(f"⚠️ Error checking/deleting file {filepath}: {e}")

# 📸 Step 2: Capture images
for county in cams_data:
    for cam in county.get("cams", []):
        if count >= max_count:
            break

        cam_id = cam.get("id")
        stream_url = cam.get("stream")

        if not stream_url or not cam_id:
            continue

        cam_folder = os.path.join(output_dir, f"{cam_id}")
        os.makedirs(cam_folder, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        output_path = os.path.join(cam_folder, f"{timestamp}.jpg")

        cmd = [
            "ffmpeg",
            "-y",
            "-i", stream_url,
            "-frames:v", "1",
            "-q:v", "2",
            output_path
        ]

        try:
            print(f"🎥 Capturing {cam_id}...")
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"✅ Saved {output_path}")
            count += 1
        except subprocess.CalledProcessError:
            print(f"❌ Failed to capture {cam_id}")
            continue

# 🧹 Step 3: Update frames.json for each cam
for cam_dir in os.listdir(output_dir):
    cam_folder = os.path.join(output_dir, cam_dir)
    if os.path.isdir(cam_folder):
        frames = sorted([f for f in os.listdir(cam_folder) if f.endswith(".jpg")])
        with open(os.path.join(cam_folder, "frames.json"), "w") as f:
            json.dump(frames, f)

# 📂 Step 4: Replace timelapse folder in SSR site
print("♻️ Replacing timelapse folder in SSR build...")

shutil.rmtree(final_destination, ignore_errors=True)
shutil.copytree(output_dir, final_destination)

print(f"✅ timelapse/ copied to {final_destination}")
