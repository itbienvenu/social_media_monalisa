import boto3
import os
import subprocess
from botocore.exceptions import ClientError
import logging
import re
import uuid
from fastapi import HTTPException
from libs.common.signatures import sign_url_path

logger = logging.getLogger("post-orchestrator")

def generate_upload_url(filename: str, user_id: str, content_type: str = "image/jpeg") -> dict:
    """
    Generates a pre-signed PUT URL for uploading to MinIO/S3.
    Returns the public URL where the file will be accessible.
    """
    # Restrict allowed content-types
    ALLOWED_CONTENT_TYPES = {
        "image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp",
        "video/mp4", "video/mpeg", "video/quicktime", "video/webm",
        "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/ogg", "audio/aac", "audio/m4a", "audio/x-m4a"
    }
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Content-Type not allowed")

    # Validate/sanitize filename (no path separators, reasonable length)
    safe_filename = os.path.basename(filename)
    safe_filename = re.sub(r'[^a-zA-Z0-9_\.-]', '', safe_filename)
    if len(safe_filename) > 100:
        name, ext = os.path.splitext(safe_filename)
        safe_filename = name[:100-len(ext)] + ext

    if not safe_filename or safe_filename in (".", ".."):
        safe_filename = "file"

    # Enforce an object key scheme like uploads/{user_id}/{uuid}_{safe_filename}
    file_uuid = uuid.uuid4()
    object_key = f"uploads/{user_id}/{file_uuid}_{safe_filename}"

    s3_client = boto3.client(
        "s3",
        endpoint_url=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
        aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "minioadminpassword"),
        config=boto3.session.Config(signature_version='s3v4')
    )
    
    bucket = os.getenv("MINIO_BUCKET_NAME", "social-media-uploads")
    
    # Ensure bucket exists
    try:
        s3_client.head_bucket(Bucket=bucket)
    except ClientError:
        try:
             s3_client.create_bucket(Bucket=bucket)
        except Exception as e:
             logger.error(f"Failed to create bucket: {e}")

    try:
        # Create a client pointing to the public URL for presigned generation
        # so the signed Host header matches the browser's Host header.
        public_endpoint = os.getenv("MINIO_PUBLIC_URL", "http://localhost:9000")
        presign_client = boto3.client(
            "s3",
            endpoint_url=public_endpoint,
            aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "minioadminpassword"),
            config=boto3.session.Config(signature_version='s3v4')
        )

        # Generate presigned URL for uploading
        presigned_url = presign_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': bucket,
                'Key': object_key,
                'ContentType': content_type
            },
            ExpiresIn=3600
        )
        
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        if base_url.endswith("/"):
            base_url = base_url[:-1]
            
        exp, sig = sign_url_path(bucket, object_key)
        public_url = f"{base_url}/uploads/{bucket}/{object_key}?exp={exp}&sig={sig}"
        
        return {"upload_url": presigned_url, "public_url": public_url, "key": object_key}
        
    except ClientError as e:
        logger.error(f"S3 Error: {e}")
        return None


def delete_media_files(media_keys: list):
    """
    Deletes the listed media files from the MinIO bucket to free up storage.
    """
    if not media_keys:
        return
        
    s3_client = boto3.client(
        "s3",
        endpoint_url=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
        aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "minioadminpassword"),
        config=boto3.session.Config(signature_version='s3v4')
    )
    bucket = os.getenv("MINIO_BUCKET_NAME", "social-media-uploads")
    
    for key in media_keys:
        if not key:
            continue
        # Extract object key if it's a full public URL
        # Format: http://<domain>/uploads/<bucket>/uploads/<user_id>/<file>
        obj_key = key
        if str(key).startswith("http"):
            parts = str(key).split(f"/uploads/{bucket}/")
            if len(parts) > 1:
                obj_key = parts[1]
            else:
                # Try general fallback to extract starting from "uploads/"
                match = re.search(r'uploads/.*', str(key))
                if match:
                    obj_key = match.group(0)
                else:
                    # Skip external CDN URL
                    continue
        
        if isinstance(obj_key, str):
            obj_key = obj_key.split("?")[0]
        
        try:
            s3_client.delete_object(Bucket=bucket, Key=obj_key)
            logger.info(f"Successfully deleted local media file from MinIO: {obj_key}")
        except Exception as e:
            logger.error(f"Failed to delete media file {obj_key} from MinIO: {e}")


def get_presigned_download_url(url: str, expires_in: int = 3600) -> str:
    """
    If the URL points to our MinIO instance via the API Gateway/uploads route,
    converts it to a presigned GET URL pointing to MINIO_PUBLIC_URL.
    Otherwise, returns the URL unchanged.
    """
    if not url:
        return url
    
    # Check if the URL has our /uploads/ format
    if "/uploads/" in url:
        try:
            parts = url.split("/uploads/", 1)[1].split("/", 1)
            if len(parts) == 2:
                bucket_name, obj_key = parts
                
                s3_client = boto3.client(
                    "s3",
                    endpoint_url=os.getenv("MINIO_PUBLIC_URL", "http://localhost:9000"),
                    aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
                    aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "minioadminpassword"),
                    config=boto3.session.Config(signature_version='s3v4')
                )
                
                presigned_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': bucket_name,
                        'Key': obj_key
                    },
                    ExpiresIn=expires_in
                )
                return presigned_url
        except Exception as e:
            logger.error(f"Failed to generate presigned GET URL for {url}: {e}")
            
    return url


def is_image_file(filename: str) -> bool:
    lower = filename.lower()
    return any(lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"])


def is_video_file(filename: str) -> bool:
    lower = filename.lower()
    return any(lower.endswith(ext) for ext in [".mp4", ".mov", ".avi", ".webm", ".mkv"])


import asyncio

def has_audio_stream(video_path: str) -> bool:
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "a",
            "-show_entries", "stream=codec_type", "-of", "csv=p=0", video_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, timeout=10)
        return "audio" in result.stdout
    except Exception:
        return False


def _process_and_mix_media_sync(
    user_id: str,
    media_keys: list,
    audio_key: str = None,
    is_reel: bool = False,
    music_volume: float = 0.2,
    video_volume: float = 1.0,
    slideshow_duration: int = 10
) -> dict:
    """
    Synchronous implementation of media compilation and mixing.
    Runs in a separate thread.
    """
    import subprocess
    import tempfile
    import shutil
    
    # Initialize S3 client
    s3_client = boto3.client(
        "s3",
        endpoint_url=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
        aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "minioadminpassword"),
        config=boto3.session.Config(signature_version='s3v4')
    )
    bucket = os.getenv("MINIO_BUCKET_NAME", "social-media-uploads")
    
    # Helper function to extract MinIO Key from URL or key
    def get_object_key(key_or_url: str) -> str:
        if not key_or_url:
            return ""
        if str(key_or_url).startswith("http"):
            parts = str(key_or_url).split(f"/uploads/{bucket}/")
            if len(parts) > 1:
                return parts[1].split("?")[0]
            # Try uploads/ fallback
            match = re.search(r'uploads/.*', str(key_or_url))
            if match:
                return match.group(0).split("?")[0]
        return str(key_or_url).split("?")[0]

    # Enforce upper bound on images/clips count (max 20)
    valid_keys = [k for k in media_keys if k][:20]
    if not valid_keys:
        return None
        
    # Enforce bounds on slideshow duration (max 60 seconds)
    slideshow_duration = min(60, max(1, slideshow_duration))
    
    # Determine file types
    is_all_images = all(is_image_file(get_object_key(k)) for k in valid_keys)
    is_single_video = len(valid_keys) == 1 and is_video_file(get_object_key(valid_keys[0]))
    
    needs_slideshow = is_reel and is_all_images and len(valid_keys) > 0
    needs_audio_mix = audio_key and (needs_slideshow or is_single_video)
    
    if not needs_slideshow and not needs_audio_mix:
        # No compilation required
        return None

    # Enforce upper bound on file sizes (max 100MB per file)
    MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024
    for k in valid_keys:
        obj_key = get_object_key(k)
        try:
            head = s3_client.head_object(Bucket=bucket, Key=obj_key)
            if head.get('ContentLength', 0) > MAX_FILE_SIZE_BYTES:
                raise ValueError(f"File {obj_key} size exceeds the 100MB limit.")
        except ClientError as e:
            logger.error(f"S3 head object error for validation of {obj_key}: {e}")

    if audio_key:
        audio_obj_key = get_object_key(audio_key)
        try:
            head = s3_client.head_object(Bucket=bucket, Key=audio_obj_key)
            if head.get('ContentLength', 0) > MAX_FILE_SIZE_BYTES:
                raise ValueError(f"Audio file {audio_obj_key} size exceeds the 100MB limit.")
        except ClientError as e:
            logger.error(f"S3 head object error for validation of {audio_obj_key}: {e}")
        
    # Create temp workspace
    temp_dir = tempfile.mkdtemp()
    try:
        logger.info(f"Processing media in temp dir: {temp_dir}")
        
        # Download media files
        local_media_paths = []
        for idx, k in enumerate(valid_keys):
            obj_key = get_object_key(k)
            local_ext = os.path.splitext(obj_key)[1] or (".jpg" if is_all_images else ".mp4")
            local_path = os.path.join(temp_dir, f"media_{idx}{local_ext}")
            logger.info(f"Downloading {obj_key} to {local_path}")
            s3_client.download_file(bucket, obj_key, local_path)
            local_media_paths.append(local_path)
            
        # Download audio if provided
        local_audio_path = None
        if audio_key:
            audio_obj_key = get_object_key(audio_key)
            audio_ext = os.path.splitext(audio_obj_key)[1] or ".mp3"
            local_audio_path = os.path.join(temp_dir, f"audio{audio_ext}")
            logger.info(f"Downloading audio {audio_obj_key} to {local_audio_path}")
            s3_client.download_file(bucket, audio_obj_key, local_audio_path)
            
        output_filename = f"compiled_{uuid.uuid4()}.mp4"
        output_local_path = os.path.join(temp_dir, output_filename)
        
        # Enforce FFmpeg execution timeout (60 seconds)
        FFMPEG_TIMEOUT_SECONDS = 60
        
        if needs_slideshow:
            logger.info("Compiling image slideshow...")
            # Compile individual video clips for each image
            duration_per_image = max(1.0, float(slideshow_duration) / len(local_media_paths))
            clip_paths = []
            
            for idx, img_path in enumerate(local_media_paths):
                clip_path = os.path.join(temp_dir, f"clip_{idx}.mp4")
                # Scale, pad to 1080x1920 (standard vertical Reel format)
                cmd = [
                    "ffmpeg", "-y", "-loop", "1", "-i", img_path,
                    "-c:v", "libx264", "-t", str(duration_per_image),
                    "-pix_fmt", "yuv420p", "-vf",
                    "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
                    clip_path
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=FFMPEG_TIMEOUT_SECONDS)
                clip_paths.append(clip_path)
                
            # Concatenate clips
            list_file_path = os.path.join(temp_dir, "clips.txt")
            with open(list_file_path, "w") as f:
                for cp in clip_paths:
                    f.write(f"file '{cp}'\n")
                    
            concat_no_audio = os.path.join(temp_dir, "concat_no_audio.mp4")
            cmd_concat = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file_path,
                "-c", "copy", concat_no_audio
            ]
            subprocess.run(cmd_concat, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=FFMPEG_TIMEOUT_SECONDS)
            
            # Now overlay audio if available, otherwise output silent video
            if local_audio_path:
                cmd_audio = [
                    "ffmpeg", "-y", "-i", concat_no_audio, "-stream_loop", "-1", "-i", local_audio_path,
                    "-filter_complex", f"[1:a]volume={music_volume}[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                    "-shortest", output_local_path
                ]
                subprocess.run(cmd_audio, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=FFMPEG_TIMEOUT_SECONDS)
            else:
                shutil.copy(concat_no_audio, output_local_path)
                
        elif is_single_video and local_audio_path:
            logger.info("Mixing background music into single video...")
            video_path = local_media_paths[0]
            
            if has_audio_stream(video_path):
                # Video has audio; mix the streams
                cmd = [
                    "ffmpeg", "-y", "-i", video_path, "-stream_loop", "-1", "-i", local_audio_path,
                    "-filter_complex", f"[0:a]volume={video_volume}[a0];[1:a]volume={music_volume}[a1];[a0][a1]amix=inputs=2:duration=first[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", output_local_path
                ]
            else:
                # Video has no audio; attach background audio directly
                cmd = [
                    "ffmpeg", "-y", "-i", video_path, "-stream_loop", "-1", "-i", local_audio_path,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest", output_local_path
                ]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=FFMPEG_TIMEOUT_SECONDS)
            
        # Upload compiled video to MinIO
        new_object_key = f"uploads/{user_id}/{output_filename}"
        logger.info(f"Uploading compiled media to {new_object_key}")
        s3_client.upload_file(
            output_local_path, bucket, new_object_key,
            ExtraArgs={'ContentType': 'video/mp4'}
        )
        
        # Construct public URL
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        if base_url.endswith("/"):
            base_url = base_url[:-1]
        
        exp, sig = sign_url_path(bucket, new_object_key)
        new_public_url = f"{base_url}/uploads/{bucket}/{new_object_key}?exp={exp}&sig={sig}"
        
        return {
            "media_key": new_object_key,
            "media_keys": [new_object_key],
            "media_url": new_public_url,
            "media_urls": [new_public_url]
        }
        
    except Exception as e:
        logger.error(f"Failed compile or mix media: {e}")
        # Return None so we gracefully fallback to original media
        return None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def process_and_mix_media(
    user_id: str,
    media_keys: list,
    audio_key: str = None,
    is_reel: bool = False,
    music_volume: float = 0.2,
    video_volume: float = 1.0,
    slideshow_duration: int = 10
) -> dict:
    """
    Async wrapper that offloads the blocking media compilation to a background executor.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: _process_and_mix_media_sync(
            user_id=user_id,
            media_keys=media_keys,
            audio_key=audio_key,
            is_reel=is_reel,
            music_volume=music_volume,
            video_volume=video_volume,
            slideshow_duration=slideshow_duration
        )
    )
