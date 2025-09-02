import time
from lights import get_lights

L = get_lights()

try:
	print("Solid purple for 2s")
	L.set_color(180, 0, 255, 0)
	time.sleep(2)

	print("Pulse blue...")
	L.pulse((0, 0, 255, 0), seconds=2.5)
	time.sleep(5)

	print("Bounce red...")
	L.bounce((255, 0, 0, 0), tail=6, speed=0.015)
	time.sleep(5)

	print("Wave cyan...")
	L.wave((0, 180, 255, 0), wavelength=20, speed=0.02)
	time.sleep(5)

	print("Fade between magenta and gold...")
	L.fade_between((255, 0, 180, 0), (255, 180, 0, 0), period=3.0)
	time.sleep(6)

	print("Rainbow...")
	L.rainbow(speed=0.01, step=2)
	time.sleep(6)

	print("Heart pulse...")
	L.heart_pulse()
	time.sleep(2)

	print("Override burn...")
	L.override_burn(seconds=2.5)
	time.sleep(3)

	print("Weather: rain...")
	L.weather("rain")
	time.sleep(5)

finally:
	print("Off")
	L.off()
