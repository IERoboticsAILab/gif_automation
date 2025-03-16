import streamlit as st
import os
import tempfile
import time
from main import compress_gif  # Import the function from main.py

# Set page config
st.set_page_config(
    page_title="GIF Compressor",
    page_icon="🎬",
    layout="centered",
)

# App title and description
st.title("GIF Compression Tool")
st.markdown("Upload a GIF and compress it to your desired size!")

# Sidebar with options
with st.sidebar:
    st.header("Compression Settings")
    target_size = st.slider(
        "Target Size (MB)", 
        min_value=0.1, 
        max_value=10.0, 
        value=1.0, 
        step=0.1,
        help="Target file size in megabytes"
    )
    
    max_attempts = st.slider(
        "Max Compression Attempts", 
        min_value=1, 
        max_value=20, 
        value=10, 
        step=1,
        help="Maximum number of compression attempts to try"
    )
    
    st.markdown("---")
    st.subheader("Advanced Settings")
    
    with st.expander("Quality Thresholds"):
        min_colors = st.slider(
            "Minimum Colors", 
            min_value=2, 
            max_value=256, 
            value=32, 
            step=1,
            help="Minimum number of colors to preserve (higher = better quality)"
        )
        
        min_scale = st.slider(
            "Minimum Scale", 
            min_value=0.1, 
            max_value=1.0, 
            value=0.4, 
            step=0.05,
            help="Minimum size scale (higher = less resizing)"
        )
        
        force_scaling = st.checkbox(
            "Force Scaling", 
            value=False,
            help="Enable scaling early in the compression process for better results"
        )
    
    with st.expander("Frame Adjustments"):
        frame_sample_rate = st.slider(
            "Frame Sample Rate", 
            min_value=0.1, 
            max_value=1.0, 
            value=1.0, 
            step=0.1,
            help="Fraction of frames to keep (1.0 = all frames, 0.5 = half the frames)"
        )
        
        duration_factor = st.slider(
            "Frame Duration Factor", 
            min_value=0.5, 
            max_value=2.0, 
            value=1.0, 
            step=0.1,
            help="Adjust playback speed (1.0 = original, 2.0 = twice as slow)"
        )
    
    with st.expander("Crop GIF"):
        st.write("Crop pixels from each edge:")
        crop_left = st.number_input("Left", min_value=0, max_value=100, value=0, step=1)
        crop_top = st.number_input("Top", min_value=0, max_value=100, value=0, step=1)
        crop_right = st.number_input("Right", min_value=0, max_value=100, value=0, step=1)
        crop_bottom = st.number_input("Bottom", min_value=0, max_value=100, value=0, step=1)
        
        # Only use crop values if at least one is non-zero
        use_crop = crop_left > 0 or crop_top > 0 or crop_right > 0 or crop_bottom > 0
        crop_pixels = (crop_left, crop_top, crop_right, crop_bottom) if use_crop else None
    
    st.markdown("---")
    st.markdown("### About")
    st.markdown("""
    This tool compresses GIF files to a target size while 
    preserving as much quality as possible.
    
    It uses an adaptive compression algorithm that tries different 
    settings until the target size is reached.
    """)

# File upload
uploaded_file = st.file_uploader("Upload a GIF file", type=["gif"])

if uploaded_file is not None:
    # Display the original GIF
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Original GIF")
        st.image(uploaded_file, use_container_width=True)
        
        # Get and display original file size
        file_size = uploaded_file.size / (1024 * 1024)  # Convert to MB
        st.write(f"Original Size: {file_size:.2f} MB")
    
    # Process button
    if st.button("Compress GIF"):
        with st.spinner("Compressing... This may take a moment."):
            # Create temporary files for processing
            with tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as temp_input:
                temp_input.write(uploaded_file.getvalue())
                input_path = temp_input.name
            
            with tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as temp_output:
                output_path = temp_output.name
            
            # Progress placeholder
            progress_placeholder = st.empty()
            
            # Run compression
            try:
                # Define the progress callback function
                def progress_callback(attempt, current_size, settings):
                    progress_placeholder.write(f"Attempt {attempt}: {current_size:.2f}MB (Settings: {settings})")
                
                # Process the GIF
                orig_size, new_size = compress_gif(
                    input_path,
                    output_path,
                    target_size_mb=target_size,
                    max_attempts=max_attempts,
                    progress_callback=progress_callback,
                    min_scale=min_scale,
                    min_colors=min_colors,
                    frame_sample_rate=frame_sample_rate,
                    duration_factor=duration_factor,
                    force_scaling=force_scaling,
                    crop_pixels=crop_pixels
                )
                
                # Read the compressed file
                with open(output_path, "rb") as f:
                    compressed_data = f.read()
                
                # Display the compressed GIF
                with col2:
                    st.subheader("Compressed GIF")
                    st.image(compressed_data, use_container_width=True)
                    
                    # Display stats
                    new_size_mb = new_size / (1024 * 1024)
                    compression_ratio = (1 - (new_size / orig_size)) * 100
                    st.write(f"Compressed Size: {new_size_mb:.2f} MB")
                    st.write(f"Compression: {compression_ratio:.2f}%")
                    
                    # Display compression settings used
                    st.write("**Applied Settings:**")
                    settings = []
                    if crop_pixels:
                        settings.append(f"Cropped: {crop_pixels}")
                    if frame_sample_rate < 1.0:
                        settings.append(f"Frame sampling: {frame_sample_rate:.1f}")
                    if duration_factor != 1.0:
                        settings.append(f"Duration adjustment: {duration_factor:.1f}x")
                    if min_colors < 256:
                        settings.append(f"Color reduction: min {min_colors} colors")
                    if min_scale < 1.0:
                        settings.append(f"Scale reduction: min {min_scale:.2f}x")
                    if force_scaling:
                        settings.append("Scaling applied early")
                        
                    if settings:
                        st.write(", ".join(settings))
                
                # Allow downloading the compressed file
                st.download_button(
                    label="Download Compressed GIF",
                    data=compressed_data,
                    file_name=f"compressed_{uploaded_file.name}",
                    mime="image/gif"
                )
                
            except Exception as e:
                st.error(f"Error compressing GIF: {e}")
            
            finally:
                # Clean up temporary files
                try:
                    os.unlink(input_path)
                    os.unlink(output_path)
                except:
                    pass 