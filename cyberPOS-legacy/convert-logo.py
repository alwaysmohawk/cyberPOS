from PIL import Image, ImageChops, ImageOps

def prep_logo_for_nv(
    src="fastafLogo.png",
    out="fastaf_nv.bmp",
    target_width=560
):
    img = Image.open(src).convert("RGBA")

    # Flatten alpha to white
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    img = Image.alpha_composite(bg, img).convert("RGB")

    # Auto-crop whitespace
    white = Image.new("RGB", img.size, (255, 255, 255))
    diff = ImageChops.difference(img, white)
    bbox = diff.getbbox()
    if bbox:
        img = img.crop(bbox)

    # Scale to target width
    new_h = int(img.height * (target_width / img.width))
    img = img.resize((target_width, new_h), Image.LANCZOS)

    # Snap width to multiple of 8 (ESC/POS requirement)
    w, h = img.size
    w = (w // 8) * 8
    img = img.crop((0, 0, w, h))

    # Convert to pure 1-bit (NO dithering)
    img = ImageOps.autocontrast(img)
    img = img.convert("1", dither=Image.NONE)

    img.save(out)
    print(f"Saved NV-ready logo as {out} ({w}x{h})")

prep_logo_for_nv()
