import board, neopixel, time

pixels = neopixel.NeoPixel(board.D18, 10, auto_write=False) # 10 = number of LEDs

for i in range(10):
	pixels.fill((255, 0, 0)) # Red
	pixels.show()
	time.sleep(1)
	pixels.fill((0, 255, 0)) # Green
	pixels.show()
	time.sleep(1)
	pixels.fill((0, 0, 255)) # Blue
	pixels.show()
	time.sleep(1)

pixels.fill((0, 0, 0)) # Turn off
pixels.show()
