# app.py - Main Flask application for Steganography
# This application allows users to hide secret text inside images and extract hidden text from images

import cv2
import numpy as np
import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
import base64
from io import BytesIO

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your_secret_key_here_change_this_in_production'

# Configuration for file uploads
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

def allowed_file(filename):
    """Check if the uploaded file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def text_to_binary(text):
    """Convert text to binary format with stop signal"""
    # Convert each character to 8-bit binary
    binary = ''.join(format(ord(char), '08b') for char in text)
    # Add stop signal (16 bits of 1's) to mark the end of message
    stop_signal = '1111111111111110'  # This is 16 bits, the last 0 ensures uniqueness
    return binary + stop_signal

def binary_to_text(binary_string):
    """Convert binary back to original text"""
    chars = []
    # Process each 8-bit chunk
    for i in range(0, len(binary_string), 8):
        byte = binary_string[i:i+8]
        if len(byte) < 8:
            break
        # Check if this is the stop signal
        if byte == '11111110' or (i+16 <= len(binary_string) and binary_string[i:i+16] == '1111111111111110'):
            break
        chars.append(chr(int(byte, 2)))
    return ''.join(chars)

def encode_image(image_path, secret_text, output_path):
    """Hide secret text inside image using LSB (Least Significant Bit) technique"""
    # Read the image
    img = cv2.imread(image_path)
    if img is None:
        return False, "Could not read image file"
    
    # Convert text to binary
    binary_data = text_to_binary(secret_text)
    data_len = len(binary_data)
    
    # Get image dimensions
    height, width, channels = img.shape
    total_capacity = height * width * channels  # Each pixel has 3 channels (BGR)
    
    # Check if the secret text can fit in the image
    if data_len > total_capacity:
        return False, f"Secret text is too large! Image can only store {total_capacity} bits, but your text requires {data_len} bits. Use a larger image or smaller text."
    
    # Encode each bit into the LSB of pixel values
    bit_index = 0
    for i in range(height):
        for j in range(width):
            for k in range(3):  # Loop through BGR channels
                if bit_index < data_len:
                    # Get current pixel value
                    pixel_value = img[i, j, k]
                    # Get the current bit to hide
                    bit = int(binary_data[bit_index])
                    # Clear LSB and set it to our bit
                    new_pixel_value = (pixel_value & 0xFE) | bit
                    # Update pixel
                    img[i, j, k] = new_pixel_value
                    bit_index += 1
                else:
                    # Save the encoded image
                    cv2.imwrite(output_path, img)
                    return True, f"Successfully encoded! Hidden {bit_index} bits of data."
    
    # Save if we've used all pixels
    cv2.imwrite(output_path, img)
    return True, f"Successfully encoded! Hidden {bit_index} bits of data."

def decode_image(image_path):
    """Extract hidden text from image using LSB technique"""
    # Read the image
    img = cv2.imread(image_path)
    if img is None:
        return None, "Could not read image file"
    
    # Extract LSBs from all pixels
    binary_data = ''
    height, width, channels = img.shape
    
    # Extract bits from each channel of each pixel
    for i in range(height):
        for j in range(width):
            for k in range(3):  # Loop through BGR channels
                # Get LSB from pixel value
                lsb = img[i, j, k] & 1
                binary_data += str(lsb)
                
                # Check for stop signal every 16 bits
                if len(binary_data) >= 16:
                    # Look for the stop signal
                    if binary_data[-16:] == '1111111111111110':
                        # Remove the stop signal and convert to text
                        hidden_text = binary_to_text(binary_data[:-16])
                        return hidden_text, "Successfully extracted hidden message!"
    
    # If no stop signal found, try to extract everything
    hidden_text = binary_to_text(binary_data)
    if hidden_text:
        return hidden_text, "Extracted message (no stop signal found)"
    return None, "No hidden message found in this image"

@app.route('/')
def index():
    """Home page - Main landing page with navigation options"""
    return render_template('index.html')

@app.route('/encode', methods=['GET', 'POST'])
def encode():
    """Page for encoding/hiding text inside an image"""
    if request.method == 'POST':
        # Check if file was uploaded
        if 'image' not in request.files:
            flash('No file uploaded', 'error')
            return redirect(request.url)
        
        file = request.files['image']
        secret_text = request.form.get('secret_text', '')
        
        # Validate inputs
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if not secret_text:
            flash('Please enter some secret text to hide', 'error')
            return redirect(request.url)
        
        if not allowed_file(file.filename):
            flash('Invalid file type! Please upload PNG, JPG, JPEG, or BMP file.', 'error')
            return redirect(request.url)
        
        try:
            # Save uploaded file
            filename = secure_filename(file.filename)
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], 'input_' + filename)
            file.save(input_path)
            
            # Create output filename (always save as PNG to preserve quality)
            output_filename = 'encoded_' + os.path.splitext(filename)[0] + '.png'
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
            
            # Encode the text into image
            success, message = encode_image(input_path, secret_text, output_path)
            
            # Clean up input file
            os.remove(input_path)
            
            if success:
                # Get file size info
                file_size = os.path.getsize(output_path)
                flash(f'{message} Output file size: {file_size} bytes', 'success')
                return render_template('encode.html', 
                                     encoded_image=output_filename,
                                     original_text=secret_text)
            else:
                flash(message, 'error')
                return redirect(request.url)
                
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
            return redirect(request.url)
    
    return render_template('encode.html', encoded_image=None)

@app.route('/decode', methods=['GET', 'POST'])
def decode():
    """Page for decoding/extracting hidden text from an image"""
    if request.method == 'POST':
        # Check if file was uploaded
        if 'image' not in request.files:
            flash('No file uploaded', 'error')
            return redirect(request.url)
        
        file = request.files['image']
        
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if not allowed_file(file.filename):
            flash('Invalid file type! Please upload PNG, JPG, JPEG, or BMP file.', 'error')
            return redirect(request.url)
        
        try:
            # Save uploaded file
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'decode_' + filename)
            file.save(file_path)
            
            # Decode the image
            hidden_text, message = decode_image(file_path)
            
            # Clean up uploaded file
            os.remove(file_path)
            
            if hidden_text:
                flash(message, 'success')
                return render_template('decode.html', hidden_text=hidden_text)
            else:
                flash(message, 'error')
                return redirect(request.url)
                
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
            return redirect(request.url)
    
    return render_template('decode.html', hidden_text=None)

@app.route('/download/<filename>')
def download_file(filename):
    """Download the encoded image"""
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        flash('File not found', 'error')
        return redirect(url_for('index'))

# Run the application
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)