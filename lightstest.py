import time, board, neopixel

pixels = neopixel.NeoPixel(board.D18, 10, pixel_order=neopixel.GRBW, auto_write=True, brightness=1.0)

# Red
pixels.fill((255, 0, 0, 0))
time.sleep(2)

# Green
pixels.fill((0, 255, 0, 0))
time.sleep(2)

# Blue
pixels.fill((0, 0, 255, 0))
time.sleep(2)

# White
pixels.fill((0, 0, 0, 255))
time.sleep(2)

# Off
pixels.fill((0, 0, 0, 0))
