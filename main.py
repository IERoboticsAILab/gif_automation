import argparse
import os
import shutil
import subprocess
import tempfile
import math

from PIL import Image, ImageSequence


def convert_mp4_to_gif(video_path, gif_path, fps=10, scale=1.0):
    """
    Convert MP4 video to GIF format.
    
    Args:
        video_path (str): Path to input MP4 file
        gif_path (str): Path to save the output GIF
        fps (int): Frames per second for the output GIF
        scale (float): Scale factor for resolution (1.0 = original size)
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Try using FFmpeg first (much better quality and efficiency)
    try:
        # Check if FFmpeg is available
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        
        # Create temp file for the palette (better quality with palette)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_palette:
            palette_path = temp_palette.name
        
        # Build filter string based on scale
        if scale != 1.0:
            filter_scale = f"scale=iw*{scale}:ih*{scale}:flags=lanczos,"
        else:
            filter_scale = ""
            
        filter_str = f"{filter_scale}fps={fps}"
        palette_filter = f"{filter_str},palettegen=stats_mode=diff"
        output_filter = f"{filter_str},paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
        
        # First pass - generate palette
        subprocess.run([
            "ffmpeg",
            "-i", video_path,
            "-vf", palette_filter,
            "-y", palette_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        
        # Second pass - generate GIF with palette
        subprocess.run([
            "ffmpeg",
            "-i", video_path,
            "-i", palette_path,
            "-lavfi", output_filter,
            "-y", gif_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        
        # Clean up
        os.unlink(palette_path)
        return True
        
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        print(f"FFmpeg error: {e}. Falling back to PIL conversion (lower quality).")
        try:
            return _convert_mp4_to_gif_with_pil(video_path, gif_path, fps, scale)
        except Exception as e:
            print(f"PIL conversion also failed: {e}")
            return False

def _convert_mp4_to_gif_with_pil(video_path, gif_path, fps=10, scale=1.0):
    """
    Fallback method to convert MP4 to GIF using PIL and temporary images.
    Less efficient and lower quality than FFmpeg method.
    """
    # We need to extract frames first using OpenCV
    try:
        import cv2
    except ImportError:
        print("OpenCV (cv2) is required for PIL-based video conversion.")
        return False
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Open the video file
        video = cv2.VideoCapture(video_path)
        if not video.isOpened():
            raise ValueError("Could not open video file")
            
        # Get video properties
        frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = video.get(cv2.CAP_PROP_FPS)
        
        # Calculate which frames to keep based on target fps
        frame_interval = max(1, round(video_fps / fps))
        frames = []
        
        # Extract frames to temporary directory
        success, frame = video.read()
        frame_idx = 0
        
        while success:
            if frame_idx % frame_interval == 0:
                # Resize if needed
                if scale != 1.0:
                    height, width = frame.shape[:2]
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
                
                # Convert BGR to RGB (OpenCV uses BGR)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Create PIL Image and append to frames list
                pil_img = Image.fromarray(frame_rgb)
                frames.append(pil_img)
                
            # Read next frame
            success, frame = video.read()
            frame_idx += 1
            
        # Release video
        video.release()
        
        if not frames:
            raise ValueError("No frames extracted from video")
        
        # Save as GIF
        frames[0].save(
            gif_path,
            format="GIF",
            append_images=frames[1:],
            save_all=True,
            optimize=True,
            duration=int(1000 / fps),  # Duration in ms between frames
            loop=0  # Loop forever
        )
        
        return True
        
    except Exception as e:
        print(f"Error in PIL conversion: {e}")
        return False
        
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_dir, ignore_errors=True)


def compress_gif(
    input_path, 
    output_path, 
    target_size_mb=1.0, 
    max_attempts=10, 
    progress_callback=None, 
    min_scale=0.4, 
    min_colors=32,
    frame_sample_rate=1.0,
    duration_factor=1.0,
    force_scaling=False,
    crop_pixels=None
):
    """
    Compress a GIF to target approximately 1MB (or specified size) using adaptive compression.

    Args:
        input_path (str): Path to the input GIF
        output_path (str): Path to save the compressed GIF
        target_size_mb (float): Target size in MB
        max_attempts (int): Maximum number of compression attempts
        progress_callback (function, optional): Callback function for progress updates
        min_scale (float): Minimum scale factor (0.1-1.0)
        min_colors (int): Minimum number of colors (2-256)
        frame_sample_rate (float): Sample rate for frames (1.0 = keep all frames, 0.5 = keep half)
        duration_factor (float): Factor to multiply frame duration by (>1 = slower GIF)
        force_scaling (bool): Start with scaling in the first pass to get better compression
        crop_pixels (tuple, optional): Pixels to crop (left, top, right, bottom)

    Returns:
        tuple: Original and new file sizes in bytes
    """
    # Get original file size
    original_size = os.path.getsize(input_path)
    target_size_bytes = int(target_size_mb * 1024 * 1024)

    # If already smaller than target, just copy the file
    if original_size <= target_size_bytes:
        shutil.copy(input_path, output_path)
        return original_size, original_size

    # Apply preprocessing steps in sequence (cropping, then frame adjustments)
    processed_input = input_path
    
    # Apply cropping if requested
    if crop_pixels and any(crop_pixels):
        temp_cropped = tempfile.NamedTemporaryFile(suffix=".gif", delete=False).name
        _crop_gif(processed_input, temp_cropped, crop_pixels)
        
        # Update the input path for next steps
        if processed_input != input_path:
            os.unlink(processed_input)  # Clean up any previous temp file
        processed_input = temp_cropped
    
    # Apply frame sampling/duration adjustment if requested
    if frame_sample_rate < 1.0 or duration_factor != 1.0:
        temp_sampled = tempfile.NamedTemporaryFile(suffix=".gif", delete=False).name
        _adjust_frames(processed_input, temp_sampled, frame_sample_rate, duration_factor)
        
        # Update the input path for next steps
        if processed_input != input_path:
            os.unlink(processed_input)  # Clean up any previous temp file
        processed_input = temp_sampled

    # From here on, use processed_input instead of input_path
    input_path_to_use = processed_input

    # Check if gifsicle is installed
    use_gifsicle = True
    try:
        subprocess.run(
            ["gifsicle", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        use_gifsicle = False
        print(
            "Gifsicle not found. Using Pillow for compression (less effective but no external dependencies)."
        )

    # Create temporary file for intermediate results
    temp_output = tempfile.NamedTemporaryFile(suffix=".gif", delete=False).name

    # Progressive compression settings with constraints
    lossy_values = [0, 30, 60, 90, 120, 150, 200]
    color_values = [c for c in [256, 192, 128, 96, 64, 32] if c >= min_colors]
    scale_values = [s for s in [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4] if s >= min_scale]
    
    # Make sure we have at least one value for each parameter
    if not color_values:
        color_values = [min_colors]
    if not scale_values:
        scale_values = [min_scale]

    best_size = original_size
    best_output = None

    # Try different compression settings until target size is reached or max attempts hit
    attempts = 0

    # If force_scaling is True, we'll include scaling in the first pass
    first_pass_scales = [1.0] if not force_scaling else scale_values
    
    # First pass: try lossy compression, color reduction, and optionally scaling
    for scale in first_pass_scales:
        for lossy in lossy_values:
            for colors in color_values:
                # Skip if we're not making progress or out of attempts
                if attempts >= max_attempts:
                    break

                attempts += 1

                # Compress with current settings
                if use_gifsicle:
                    lossy_param = []
                    if lossy > 0:
                        lossy_param = ["--lossy={}".format(lossy)]

                    scale_param = []
                    if scale < 1.0:
                        scale_param = ["--scale={}".format(scale)]

                    cmd = [
                        "gifsicle",
                        "--optimize=3",
                        *lossy_param,
                        *scale_param,
                        "--colors={}".format(colors),
                        "-i",
                        input_path_to_use,
                        "-o",
                        temp_output,
                    ]
                    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                else:
                    _compress_with_pillow(
                        input_path_to_use,
                        temp_output,
                        colors=colors,
                        lossy_equivalent=lossy,
                        scale=scale,
                    )

                # Check if we reached target size
                current_size = os.path.getsize(temp_output)

                # If this is the best size so far, save it
                if current_size < best_size:
                    best_size = current_size
                    if best_output:
                        os.unlink(best_output)
                    best_output = tempfile.NamedTemporaryFile(
                        suffix=".gif", delete=False
                    ).name
                    shutil.copy(temp_output, best_output)

                    # Print progress
                    settings_info = f"Lossy: {lossy}, Colors: {colors}, Scale: {scale}"
                    best_size_mb = best_size/1024/1024
                    print(f"Attempt {attempts}: {best_size_mb:.2f}MB ({settings_info})")
                    
                    # Call progress callback if provided
                    if progress_callback:
                        progress_callback(attempts, best_size_mb, settings_info)

                    # If we're at or below target size, we're done
                    if best_size <= target_size_bytes:
                        break

    # Second pass: if still above target size, try scaling down (if not already included in first pass)
    if best_size > target_size_bytes and not force_scaling:
        for scale in scale_values[1:]:  # Skip scale 1.0
            for lossy in [60, 120, 200]:  # Use more aggressive lossy values
                for colors in color_values:  # Use same color values as specified
                    # Skip if we're not making progress or out of attempts
                    if attempts >= max_attempts:
                        break

                    attempts += 1

                    # Compress with current settings
                    if use_gifsicle:
                        cmd = [
                            "gifsicle",
                            "--optimize=3",
                            "--lossy={}".format(lossy),
                            "--colors={}".format(colors),
                            "--scale={}".format(scale),
                            "-i",
                            input_path_to_use,
                            "-o",
                            temp_output,
                        ]
                        subprocess.run(
                            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                        )
                    else:
                        _compress_with_pillow(
                            input_path_to_use,
                            temp_output,
                            colors=colors,
                            lossy_equivalent=lossy,
                            scale=scale,
                        )

                    # Check size
                    current_size = os.path.getsize(temp_output)

                    # If this is the best size so far, save it
                    if current_size < best_size:
                        best_size = current_size
                        if best_output:
                            os.unlink(best_output)
                        best_output = tempfile.NamedTemporaryFile(
                            suffix=".gif", delete=False
                        ).name
                        shutil.copy(temp_output, best_output)

                        # Print progress
                        settings_info = f"Lossy: {lossy}, Colors: {colors}, Scale: {scale}"
                        best_size_mb = best_size/1024/1024
                        print(f"Attempt {attempts}: {best_size_mb:.2f}MB ({settings_info})")
                        
                        # Call progress callback if provided
                        if progress_callback:
                            progress_callback(attempts, best_size_mb, settings_info)

                        # If we're at or below target size, we're done
                        if best_size <= target_size_bytes:
                            break

    # Clean up and return results
    if best_output:
        shutil.copy(best_output, output_path)
        os.unlink(best_output)
    else:
        # If no successful compression, just use the last attempt
        shutil.copy(temp_output, output_path)

    os.unlink(temp_output)
    
    # Clean up any temp files
    if processed_input != input_path:
        os.unlink(processed_input)

    new_size = os.path.getsize(output_path)
    return original_size, new_size


def _crop_gif(input_path, output_path, crop_pixels):
    """
    Crop a GIF by removing specified pixels from each edge.
    
    Args:
        input_path (str): Path to input GIF
        output_path (str): Path to save the cropped GIF
        crop_pixels (tuple): Pixels to crop (left, top, right, bottom)
    """
    with Image.open(input_path) as img:
        frames = []
        durations = []
        disposals = []
        
        # Get dimensions of the original image
        width, height = img.size
        
        # Calculate new dimensions
        left, top, right, bottom = crop_pixels
        new_width = width - left - right
        new_height = height - top - bottom
        
        # Ensure we don't have negative dimensions
        if new_width <= 0 or new_height <= 0:
            shutil.copy(input_path, output_path)
            return
        
        # Process each frame
        for frame in ImageSequence.Iterator(img):
            # Convert to RGBA to preserve transparency
            converted = frame.convert("RGBA")
            
            # Crop the frame
            cropped = converted.crop((left, top, width - right, height - bottom))
            
            # Save frame info
            frames.append(cropped)
            durations.append(frame.info.get("duration", 100))
            disposals.append(
                frame.disposal_method if hasattr(frame, "disposal_method") else 2
            )
        
        # Save the cropped GIF
        if frames:
            frames[0].save(
                output_path,
                format="GIF",
                append_images=frames[1:],
                save_all=True,
                optimize=False,  # Don't optimize yet
                duration=durations,
                disposal=disposals,
                loop=img.info.get("loop", 0),
            )
        else:
            # If no frames (shouldn't happen), just copy the original
            shutil.copy(input_path, output_path)


def _adjust_frames(input_path, output_path, sample_rate=1.0, duration_factor=1.0):
    """
    Adjust the number of frames and/or frame duration in a GIF.
    
    Args:
        input_path (str): Path to input GIF
        output_path (str): Path to save the modified GIF
        sample_rate (float): Fraction of frames to keep (1.0 = all, 0.5 = every other frame)
        duration_factor (float): Factor to multiply frame duration by (>1 = slower GIF)
    """
    with Image.open(input_path) as img:
        frames = []
        durations = []
        disposals = []
        
        # Get all frames
        for i, frame in enumerate(ImageSequence.Iterator(img)):
            # Apply frame sampling
            if sample_rate < 1.0:
                # Skip frames based on sample rate
                if i % int(1/sample_rate) != 0:
                    continue
            
            # Convert to RGBA to preserve transparency
            converted = frame.convert("RGBA")
            
            # Save frame info
            frames.append(converted)
            
            # Adjust duration if needed
            orig_duration = frame.info.get("duration", 100)
            adjusted_duration = int(orig_duration * duration_factor)
            durations.append(adjusted_duration)
            
            # Keep disposal mode if available
            disposals.append(
                frame.disposal_method if hasattr(frame, "disposal_method") else 2
            )
        
        # Save the adjusted GIF
        if frames:
            frames[0].save(
                output_path,
                format="GIF",
                append_images=frames[1:],
                save_all=True,
                optimize=False,  # Don't optimize yet as we'll do that later
                duration=durations,
                disposal=disposals,
                loop=img.info.get("loop", 0),
            )
        else:
            # If no frames (shouldn't happen), just copy the original
            shutil.copy(input_path, output_path)


def _compress_with_pillow(
    input_path, output_path, colors=256, lossy_equivalent=0, scale=1.0
):
    """Fallback compression method using Pillow with approximate lossy effect"""
    with Image.open(input_path) as img:
        frames = []
        durations = []
        disposals = []

        # Determine dithering based on lossy_equivalent
        # Higher lossy = less dithering
        dither = Image.FLOYDSTEINBERG
        if lossy_equivalent > 100:
            dither = Image.NONE

        # Process each frame
        for i, frame in enumerate(ImageSequence.Iterator(img)):
            # Convert to RGBA first for better quality
            converted = frame.convert("RGBA")

            # Resize if needed
            if scale != 1.0:
                new_width = int(converted.width * scale)
                new_height = int(converted.height * scale)
                converted = converted.resize((new_width, new_height), Image.LANCZOS)

            # Apply lossy-like effect by slightly blurring for higher lossy values
            if lossy_equivalent > 30:
                from PIL import ImageFilter

                blur_radius = min(lossy_equivalent / 200, 0.8)
                converted = converted.filter(
                    ImageFilter.GaussianBlur(radius=blur_radius)
                )

            # Quantize to reduce colors
            converted = converted.quantize(colors=colors, method=2, dither=dither)

            # Save frame info
            frames.append(converted)
            durations.append(frame.info.get("duration", 100))
            disposals.append(
                frame.disposal_method if hasattr(frame, "disposal_method") else 2
            )

        # Save the optimized GIF
        frames[0].save(
            output_path,
            format="GIF",
            append_images=frames[1:],
            save_all=True,
            optimize=True,
            duration=durations,
            disposal=disposals,
            loop=img.info.get("loop", 0),
        )


def main():
    parser = argparse.ArgumentParser(
        description="Compress GIF files to approximately 1MB"
    )
    parser.add_argument("input", help="Input GIF file path or directory")
    parser.add_argument("-o", "--output", help="Output GIF file path or directory")
    parser.add_argument(
        "-s", "--size", type=float, default=1.0, help="Target size in MB (default: 1.0)"
    )
    parser.add_argument(
        "-m",
        "--max-attempts",
        type=int,
        default=10,
        help="Maximum compression attempts",
    )
    parser.add_argument(
        "-b",
        "--batch",
        action="store_true",
        help="Process all GIFs in the input directory",
    )
    
    # Add advanced options
    adv_group = parser.add_argument_group("Advanced Options")
    adv_group.add_argument(
        "--min-colors", 
        type=int, 
        default=32, 
        help="Minimum number of colors (2-256, default: 32)"
    )
    adv_group.add_argument(
        "--min-scale", 
        type=float, 
        default=0.4, 
        help="Minimum scale factor (0.1-1.0, default: 0.4)"
    )
    adv_group.add_argument(
        "--force-scaling", 
        action="store_true", 
        help="Enable scaling early in compression process"
    )
    adv_group.add_argument(
        "--frame-sample", 
        type=float, 
        default=1.0, 
        help="Frame sample rate (0.1-1.0, default: 1.0)"
    )
    adv_group.add_argument(
        "--duration-factor", 
        type=float, 
        default=1.0, 
        help="Frame duration multiplier (0.5-2.0, default: 1.0)"
    )
    adv_group.add_argument(
        "--crop", 
        type=int, 
        nargs=4, 
        metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
        help="Crop pixels from each edge (e.g. --crop 10 10 10 10)"
    )

    args = parser.parse_args()

    # Check if we're processing a single file or a directory
    if args.batch:
        # Process all GIFs in directory
        if not os.path.isdir(args.input):
            print(f"Error: {args.input} is not a directory")
            exit(1)

        # Create output directory if needed
        if args.output:
            os.makedirs(args.output, exist_ok=True)
        else:
            args.output = args.input

        # Process all GIF files
        for filename in os.listdir(args.input):
            if filename.lower().endswith(".gif"):
                input_path = os.path.join(args.input, filename)
                output_path = os.path.join(args.output, filename)

                print(f"Processing {filename}...")
                process_file(
                    input_path, 
                    output_path, 
                    args.size, 
                    args.max_attempts,
                    min_colors=args.min_colors,
                    min_scale=args.min_scale,
                    force_scaling=args.force_scaling,
                    frame_sample_rate=args.frame_sample,
                    duration_factor=args.duration_factor,
                    crop_pixels=args.crop
                )
    else:
        # Process single file
        if not args.output:
            name, ext = os.path.splitext(args.input)
            args.output = f"{name}_compressed{ext}"

        process_file(
            args.input, 
            args.output, 
            args.size, 
            args.max_attempts,
            min_colors=args.min_colors,
            min_scale=args.min_scale,
            force_scaling=args.force_scaling,
            frame_sample_rate=args.frame_sample,
            duration_factor=args.duration_factor,
            crop_pixels=args.crop
        )


def process_file(
    input_path, 
    output_path, 
    target_size_mb, 
    max_attempts, 
    min_colors=32, 
    min_scale=0.4, 
    force_scaling=False,
    frame_sample_rate=1.0,
    duration_factor=1.0,
    crop_pixels=None
):
    """Process a single GIF file"""
    try:
        orig_size, new_size = compress_gif(
            input_path,
            output_path,
            target_size_mb=target_size_mb,
            max_attempts=max_attempts,
            min_colors=min_colors,
            min_scale=min_scale,
            force_scaling=force_scaling,
            frame_sample_rate=frame_sample_rate,
            duration_factor=duration_factor,
            crop_pixels=crop_pixels
        )

        # Calculate compression ratio
        ratio = (1 - (new_size / orig_size)) * 100

        print(f"Original size: {orig_size/1024/1024:.2f} MB")
        print(f"Compressed size: {new_size/1024/1024:.2f} MB")
        print(f"Compression: {ratio:.2f}%")
        print(f"Saved to: {output_path}")
        print("------")

    except Exception as e:
        print(f"Error compressing GIF: {e}")


if __name__ == "__main__":
    main()
