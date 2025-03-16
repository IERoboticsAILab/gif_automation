# GIF Compression Tool

A web-based tool to compress GIF files to a specified target size while maintaining quality.

## Features

- Upload any GIF file
- Set custom target size
- Visual comparison between original and compressed GIFs
- Adaptive compression algorithm that tries different settings
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

3. (Optional) Install gifsicle for improved compression quality:

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

3. Upload a GIF, adjust compression settings in the sidebar if needed, and click "Compress GIF"

4. Download the compressed GIF using the download button

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

Example batch processing:
```
python main.py /path/to/gifs/ -b -o /path/to/output/ -s 0.5
```

## How It Works

The compression algorithm tries multiple strategies in sequence:

1. First attempts color reduction and lossy compression to reach target size
2. If target size is still not reached, reduces the GIF dimensions
3. Uses gifsicle for better compression when available, falls back to PIL otherwise

## Requirements

- Python 3.6+
- Pillow
- Streamlit
- (Optional) gifsicle