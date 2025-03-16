# GIF Compression Tool

A web-based tool to compress GIF files to a specified target size while maintaining quality. It can also convert MP4 videos to optimized GIFs.

## Features

- Upload any GIF file or MP4 video
- Convert videos to GIF format with customizable settings
- Set custom target size for compression
- Visual comparison between original and compressed files
- Adaptive compression algorithm that tries different settings
- Frame sampling and duration adjustment
- Crop unnecessary borders to reduce file size
- Download compressed GIF with a single click

## Installation

1. Clone this repository:
```
git clone <repository-url>
cd gif_automation
```

2. Install dependencies:
```
pip install -r requirements.txt
```

3. (Optional but recommended) Install FFmpeg for better video-to-GIF conversion:

On macOS:
```
brew install ffmpeg
```

On Ubuntu/Debian:
```
apt-get install ffmpeg
```

On Windows:
```
# Download from https://ffmpeg.org/download.html and add to your PATH
```

4. (Optional) Install gifsicle for improved GIF compression:

On macOS:
```
brew install gifsicle
```

On Ubuntu/Debian:
```
apt-get install gifsicle
```

On Windows:
```
# Download from http://www.lcdf.org/gifsicle/ and add to your PATH
```

## Usage

### Web Interface (Streamlit App)

1. Run the Streamlit app:
```
streamlit run app.py
```

2. Open your web browser to the URL shown in the terminal (typically http://localhost:8501)

3. Upload a GIF or MP4, adjust settings in the sidebar if needed, and click "Compress GIF" or "Convert to GIF & Compress"

4. Download the processed GIF using the download button

### Command Line Interface

You can also use the command-line interface directly:

```
python main.py input.gif -o output.gif -s 1.0
```

Options:
- `-o, --output`: Output file path
- `-s, --size`: Target size in MB (default: 1.0)
- `-m, --max-attempts`: Maximum compression attempts (default: 10)
- `-b, --batch`: Process all GIFs in a directory

Advanced options:
- `--min-colors`: Minimum number of colors (2-256, default: 32)
- `--min-scale`: Minimum scale factor (0.1-1.0, default: 0.4)
- `--force-scaling`: Enable scaling early in compression process
- `--frame-sample`: Frame sample rate (0.1-1.0, default: 1.0)
- `--duration-factor`: Frame duration multiplier (0.5-2.0, default: 1.0)
- `--crop`: Crop pixels from each edge (e.g. --crop 10 10 10 10)

Example batch processing:
```
python main.py /path/to/gifs/ -b -o /path/to/output/ -s 0.5
```

## How It Works

The application uses a multi-step approach:

1. For MP4 files, first converts them to GIFs using FFmpeg (if available) or OpenCV+PIL
2. Applies any preprocessing steps (cropping, frame sampling, duration adjustment)
3. Tries multiple compression strategies to reach target size:
   - Color reduction
   - Lossy compression
   - Scale reduction
   - Frame sampling
4. Uses gifsicle for better compression when available, falls back to PIL otherwise

## Requirements

- Python 3.6+
- Pillow
- Streamlit
- OpenCV (for MP4 conversion)
- (Optional) FFmpeg (for better MP4 conversion)
- (Optional) gifsicle (for better GIF compression)