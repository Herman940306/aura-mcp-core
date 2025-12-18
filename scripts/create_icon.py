"""Create MCP Monitor Icon
Project Creator: Herman Swanepoel
"""

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Installing Pillow for icon creation...")
    import os
    os.system("pip install Pillow")
    from PIL import Image, ImageDraw, ImageFont

def create_mcp_icon():
    """Create a simple MCP monitor icon"""
    # Create a 256x256 image with a gradient background
    size = 256
    img = Image.new('RGB', (size, size), color='#1a1a2e')
    draw = ImageDraw.Draw(img)
    
    # Draw gradient background
    for i in range(size):
        color_value = int(26 + (i / size) * 30)
        draw.line([(0, i), (size, i)], fill=(color_value, color_value, 46))
    
    # Draw outer circle (monitor frame)
    circle_margin = 30
    draw.ellipse(
        [circle_margin, circle_margin, size - circle_margin, size - circle_margin],
        fill='#16213e',
        outline='#0f3460',
        width=8
    )
    
    # Draw inner circle (screen)
    inner_margin = 50
    draw.ellipse(
        [inner_margin, inner_margin, size - inner_margin, size - inner_margin],
        fill='#0f3460',
        outline='#00d4ff',
        width=6
    )
    
    # Draw "MCP" text
    try:
        # Try to use a nice font
        font_size = 60
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        # Fallback to default font
        font = ImageFont.load_default()
    
    text = "MCP"
    # Get text bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Center the text
    text_x = (size - text_width) // 2
    text_y = (size - text_height) // 2 - 20
    
    # Draw text with glow effect
    for offset in range(3, 0, -1):
        glow_alpha = int(100 / offset)
        draw.text((text_x, text_y), text, fill='#00d4ff', font=font)
    
    draw.text((text_x, text_y), text, fill='#00ffff', font=font)
    
    # Draw "MONITOR" text below
    try:
        small_font = ImageFont.truetype("arial.ttf", 24)
    except:
        small_font = ImageFont.load_default()
    
    monitor_text = "MONITOR"
    bbox = draw.textbbox((0, 0), monitor_text, font=small_font)
    monitor_width = bbox[2] - bbox[0]
    monitor_x = (size - monitor_width) // 2
    monitor_y = text_y + text_height + 10
    
    draw.text((monitor_x, monitor_y), monitor_text, fill='#00d4ff', font=small_font)
    
    # Draw status indicator (green dot)
    dot_size = 20
    dot_x = size - 60
    dot_y = 60
    draw.ellipse(
        [dot_x, dot_y, dot_x + dot_size, dot_y + dot_size],
        fill='#00ff00',
        outline='#00aa00',
        width=2
    )
    
    # Save as PNG first
    png_path = "mcp_monitor_icon.png"
    img.save(png_path, "PNG")
    print(f"✅ Created PNG icon: {png_path}")
    
    # Try to convert to ICO
    try:
        # Create multiple sizes for ICO
        sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
        icons = []
        for icon_size in sizes:
            resized = img.resize(icon_size, Image.Resampling.LANCZOS)
            icons.append(resized)
        
        ico_path = "mcp_monitor_icon.ico"
        icons[0].save(ico_path, format='ICO', sizes=[(s[0], s[1]) for s in sizes])
        print(f"✅ Created ICO icon: {ico_path}")
    except Exception as e:
        print(f"⚠️  Could not create ICO file: {e}")
        print("   Using PNG icon instead")
    
    return png_path

if __name__ == "__main__":
    print("Creating KIRO_MCP Monitor Icon...")
    create_mcp_icon()
    print("\n✅ Icon creation complete!")
