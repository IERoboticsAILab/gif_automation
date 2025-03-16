import argparse
import os
import shutil
import subprocess
import tempfile

from PIL import Image, ImageSequence


def compress_gif(input_path, output_path, target_size_mb=1.0, max_attempts=10, progress_callback=None):
    """
    Compress a GIF to target approximately 1MB (or specified size) using adaptive compression.

    Args:
        input_path (str): Path to the input GIF
        output_path (str): Path to save the compressed GIF
        target_size_mb (float): Target size in MB
        max_attempts (int): Maximum number of compression attempts
        progress_callback (function, optional): Callback function for progress updates

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

    # Progressive compression settings
    lossy_values = [0, 30, 60, 90, 120, 150, 200]
    color_values = [256, 192, 128, 96, 64, 32]
    scale_values = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4]

    best_size = original_size
    best_output = None

    # Try different compression settings until target size is reached or max attempts hit
    attempts = 0

    # First pass: try lossy compression and color reduction without scaling
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

                cmd = [
                    "gifsicle",
                    "--optimize=3",
                    *lossy_param,
                    "--colors={}".format(colors),
                    "-i",
                    input_path,
                    "-o",
                    temp_output,
                ]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                _compress_with_pillow(
                    input_path,
                    temp_output,
                    colors=colors,
                    lossy_equivalent=lossy,
                    scale=1.0,
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
                settings_info = f"Lossy: {lossy}, Colors: {colors}, Scale: 1.0"
                best_size_mb = best_size/1024/1024
                print(f"Attempt {attempts}: {best_size_mb:.2f}MB ({settings_info})")
                
                # Call progress callback if provided
                if progress_callback:
                    progress_callback(attempts, best_size_mb, settings_info)

                # If we're at or below target size, we're done
                if best_size <= target_size_bytes:
                    break

    # Second pass: if still above target size, try scaling down
    if best_size > target_size_bytes:
        for scale in scale_values[1:]:  # Skip scale 1.0
            for lossy in [60, 120, 200]:  # Use more aggressive lossy values
                for colors in [128, 64, 32]:  # Use more aggressive color reduction
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
                            input_path,
                            "-o",
                            temp_output,
                        ]
                        subprocess.run(
                            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                        )
                    else:
                        _compress_with_pillow(
                            input_path,
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

    new_size = os.path.getsize(output_path)
    return original_size, new_size


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
                process_file(input_path, output_path, args.size, args.max_attempts)
    else:
        # Process single file
        if not args.output:
            name, ext = os.path.splitext(args.input)
            args.output = f"{name}_compressed{ext}"

        process_file(args.input, args.output, args.size, args.max_attempts)


def process_file(input_path, output_path, target_size_mb, max_attempts):
    """Process a single GIF file"""
    try:
        orig_size, new_size = compress_gif(
            input_path,
            output_path,
            target_size_mb=target_size_mb,
            max_attempts=max_attempts,
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
