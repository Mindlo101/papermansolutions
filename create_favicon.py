from PIL import Image, ImageDraw, ImageFont
import os

# Create a square image (32x32 pixels)
size = 32
img = Image.new('RGB', (size, size), color='#1a365d')
draw = ImageDraw.Draw(img)

# Try to use a font that supports the text
try:
    # Try to use Arial font
    font = ImageFont.truetype("arial.ttf", 14)
except:
    # Fallback to default font
    font = ImageFont.load_default()

# Draw the text "PS" (Paperman Solutions) centered
text = "PS"
bbox = draw.textbbox((0, 0), text, font=font)
text_width = bbox[2] - bbox[0]
text_height = bbox[3] - bbox[1]
x = (size - text_width) // 2
y = (size - text_height) // 2
draw.text((x, y), text, fill='white', font=font)

# Save as favicon
img.save('app/static/favicon.ico', format='ICO')
print("✅ Favicon created at app/static/favicon.ico")

# Also save as PNG for backup
img.save('app/static/favicon.png', format='PNG')
print("✅ Favicon PNG created at app/static/favicon.png")