import time
import board
import neopixel

# >>> set this to your actual LED count <<<
NUM_LEDS = 10

PIN = board.D12 # your data pin on GPIO18 (physical pin 12)
BRIGHTNESS = 0.2

# Orders to test (most likely correct is one of the first two)
ORDERS = [
	neopixel.GRB, # WS2812/NeoPixel typical
	neopixel.RGB, # Some WS2812 variants
]

# If you *know* these are SK6812 RGBW, uncomment below to test RGBW orders too:
try:
	ORDERS += [neopixel.GRBW, neopixel.RGBW]
except AttributeError:
	pass # library without RGBW support

def show_color(pix, color, label):
	pix.fill(color)
	pix.show()
	print(f" -> {label}")
	time.sleep(2)

for order in ORDERS:
	print("\n====================================")
	print(f"Testing pixel order: {order}")
	pixels = neopixel.NeoPixel(
		PIN,
		NUM_LEDS,
		brightness=BRIGHTNESS,
		auto_write=False,
		pixel_order=order,
	)
	# Clear first
	pixels.fill((0,0,0))
	pixels.show()
	time.sleep(0.5)

	# Test colors: expect RED then GREEN then BLUE then WHITE
	# For RGB strips:
	show_color(pixels, (255, 0, 0), "RED")
	show_color(pixels, ( 0, 255, 0), "GREEN")
	show_color(pixels, ( 0, 0, 255), "BLUE")
	# For RGBW-capable, (R,G,B,W) — if strip is RGB only, WHITE will just look bluish
	try:
		show_color(pixels, ( 0, 0, 0, 255), "WHITE (W channel)")
	except TypeError:
		show_color(pixels, (255, 255, 255), "WHITE (RGB mix)")

	# Off before next order
	pixels.fill((0,0,0))
	pixels.show()
	time.sleep(0.5)

print("\nDone. Note which order produced correct colors in correct sequence.")
