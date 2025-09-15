import time
import math
import threading
from typing import Tuple, Optional
import neopixel
import board

ON_PI = True

# ====== BASIC SETTINGS ======
PIN = board.D18
NUM_PIXELS = 250 # <-- set to your strip length
BRIGHTNESS = 0.25 # global brightness (0.0 - 1.0)

ORDER = neopixel.GRBW

Color = Tuple[int, int, int, int] # (R,G,B,W) for RGBW; use 0 for W on RGB strips


def clamp255(x: int) -> int:
	return max(0, min(255, int(x)))


def lerp(a: float, b: float, t: float) -> float:
	return a + (b - a) * t


def blend(c1: Color, c2: Color, t: float) -> Color:
	return (
		clamp255(lerp(c1[0], c2[0], t)),
		clamp255(lerp(c1[1], c2[1], t)),
		clamp255(lerp(c1[2], c2[2], t)),
		clamp255(lerp(c1[3], c2[3], t)),
	)


def wheel(pos: int) -> Color:
	"""Rainbow helper: pos 0..255 -> color (RGBW with W=0)."""
	pos = pos % 256
	if pos < 85:
		return (255 - pos * 3, pos * 3, 0, 0)
	if pos < 170:
		pos -= 85
		return (0, 255 - pos * 3, pos * 3, 0)
	pos -= 170
	return (pos * 3, 0, 255 - pos * 3, 0)


class Lights(LightsBase or object):
	def __init__(self, num_pixels: int = NUM_PIXELS, pin=PIN, brightness: float = BRIGHTNESS):
		self.num = num_pixels
		self.pixels = neopixel.NeoPixel(
			pin,
			num_pixels,
			brightness=brightness,
			auto_write=False,
			pixel_order=ORDER,
		)
		self._lock = threading.Lock()
		self._stop = threading.Event()
		self._thread: Optional[threading.Thread] = None
		self._mode_name = "off"

	# ---------- threading helpers ----------
	def _start_thread(self, target, *args, **kwargs):
		self.stop() # stop any existing animation
		self._stop.clear()
		self._thread = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
		self._thread.start()

	def stop(self):
		self._stop.set()
		t = self._thread
		if t and t.is_alive():
			t.join(timeout=1.0)
		self._thread = None
		self._mode_name = "off"

	def off(self):
		with self._lock:
			self.pixels.fill((0, 0, 0, 0))
			self.pixels.show()
		self._mode_name = "off"

	# ---------- basic controls ----------
	def set_color(self, r: int, g: int, b: int, w: int = 0):
		self.stop()
		with self._lock:
			self.pixels.fill((clamp255(r), clamp255(g), clamp255(b), clamp255(w)))
			self.pixels.show()
		self._mode_name = "solid"

	# ---------- animations (run in threads) ----------
	def pulse(self, color: Color, seconds: float = 2.0):
		"""Breathing pulse up/down."""
		self._mode_name = "pulse"
		def _run():
			while not self._stop.is_set():
				# up
				for t in [i / 60.0 for i in range(61)]:
					if self._stop.is_set(): break
					c = tuple(int(v * t) for v in color)
					with self._lock:
						self.pixels.fill(c)
						self.pixels.show()
					time.sleep(seconds / 120.0)
				# down
				for t in [i / 60.0 for i in range(60, -1, -1)]:
					if self._stop.is_set(): break
					c = tuple(int(v * t) for v in color)
					with self._lock:
						self.pixels.fill(c)
						self.pixels.show()
					time.sleep(seconds / 120.0)
		self._start_thread(_run)

	def bounce(self, color: Color = (255, 0, 0, 0), tail: int = 5, speed: float = 0.01):
		"""Ping-pong dot with optional fading tail."""
		self._mode_name = "bounce"
		def _run():
			idx = 0
			direction = 1
			while not self._stop.is_set():
				with self._lock:
					self.pixels.fill((0, 0, 0, 0))
					for t in range(tail):
						j = idx - t * direction
						if 0 <= j < self.num:
							fade = max(0, 1 - (t / tail))
							c = tuple(int(v * fade) for v in color)
							self.pixels[j] = c
					self.pixels.show()
				idx += direction
				if idx >= self.num - 1: direction = -1
				if idx <= 0: direction = 1
				time.sleep(speed)
		self._start_thread(_run)

	def wave(self, base: Color = (0, 0, 255, 0), wavelength: int = 16, speed: float = 0.02):
		"""Sine intensity wave across the strip."""
		self._mode_name = "wave"
		def _run():
			phase = 0.0
			while not self._stop.is_set():
				with self._lock:
					for i in range(self.num):
						s = (math.sin((i + phase) * 2 * math.pi / wavelength) + 1) / 2
						self.pixels[i] = tuple(int(v * s) for v in base)
					self.pixels.show()
				phase += 1
				time.sleep(speed)
		self._start_thread(_run)

	def rainbow(self, speed: float = 0.01, step: int = 2):
		"""Classic moving rainbow."""
		self._mode_name = "rainbow"
		def _run():
			pos = 0
			while not self._stop.is_set():
				with self._lock:
					for i in range(self.num):
						self.pixels[i] = wheel((i * 256 // self.num + pos) & 255)
					self.pixels.show()
				pos = (pos + step) & 255
				time.sleep(speed)
		self._start_thread(_run)

	def fade_between(self, c1: Color, c2: Color, period: float = 3.0):
		"""Smoothly fade back and forth between two colors."""
		self._mode_name = "fade_between"
		def _run():
			t = 0.0
			direction = 1
			step = 1 / 60.0 # 60 steps per half cycle
			while not self._stop.is_set():
				b = blend(c1, c2, t)
				with self._lock:
					self.pixels.fill(b)
					self.pixels.show()
				t += direction * step / (period / 2.0)
				if t >= 1.0:
					t = 1.0
					direction = -1
				elif t <= 0.0:
					t = 0.0
					direction = 1
				time.sleep(1/60.0)
		self._start_thread(_run)

	# ---------- event cues ----------
	def heart_pulse(self):
		"""Quick red flash on heart event."""
		self._mode_name = "heart"
		def _run():
			for level in (0.0, 0.5, 1.0, 0.5, 0.0):
				c = (int(255 * level), 0, 0, 0)
				with self._lock:
					self.pixels.fill(c)
					self.pixels.show()
				time.sleep(0.08)
			self.off()
		self._start_thread(_run)

	def override_burn(self, seconds: float = 2.0):
		"""Slow burn purple/blue/red for override start."""
		self._mode_name = "override"
		seq = [(128, 0, 180, 0), (0, 0, 255, 0), (255, 0, 64, 0)]
		def _run():
			t_per = seconds / len(seq)
			for col in seq:
				for k in range(30):
					with self._lock:
						self.pixels.fill(col)
						self.pixels.show()
					time.sleep(t_per / 30.0)
			self.off()
		self._start_thread(_run)

	# ---------- weather wrapper ----------
	def weather(self, condition: str):
		"""Map simple condition keywords to effects."""
		cond = (condition or "").lower()
		if "sun" in cond or "clear" in cond:
			self.set_color(255, 170, 0, 0) # warm
		elif "cloud" in cond or "overcast" in cond:
			self.pulse((120, 120, 120, 30), seconds=3.5)
		elif "rain" in cond or "drizzle" in cond:
			self.wave((0, 80, 200, 0), wavelength=18, speed=0.02)
		elif "snow" in cond:
			self.fade_between((180, 220, 255, 40), (80, 120, 200, 10), period=4.0)
		elif "storm" in cond or "thunder" in cond:
			self._mode_name = "storm"
			def _run():
				pos = 0
				while not self._stop.is_set():
					# blue base
					with self._lock:
						self.pixels.fill((0, 40, 150, 0))
						# occasional white flash
						if pos % 50 == 0:
							for _ in range(2):
								self.pixels.fill((255, 255, 255, 60))
								self.pixels.show()
								time.sleep(0.04)
								self.pixels.fill((0, 40, 150, 0))
								self.pixels.show()
								time.sleep(0.06)
						self.pixels.show()
					pos += 1
					time.sleep(0.03)
			self._start_thread(_run)
		else:
			self.set_color(120, 120, 120, 10) # default soft white

	# ---------- Spotify hook (stub) ----------
	def spotify_mode(self, tempo_bpm: float = 100.0, energy: float = 0.5, color: Color = (0, 255, 180, 0)):
		"""
		Stub: animate to a tempo & energy. Later the app can call this with Spotify API data.
		"""
		self._mode_name = "spotify"
		beat_sec = max(0.2, 60.0 / max(1.0, tempo_bpm))
		amplitude = max(0.1, min(1.0, energy))

		def _run():
			while not self._stop.is_set():
				# beat flash
				with self._lock:
					self.pixels.fill(tuple(int(v * amplitude) for v in color))
					self.pixels.show()
				time.sleep(beat_sec * 0.2)
				with self._lock:
					self.pixels.fill((0, 0, 0, 0))
					self.pixels.show()
				time.sleep(beat_sec * 0.8)
		self._start_thread(_run)

# Convenience singleton (optional)
_lights_instance: Optional[Lights] = None


def get_lights() -> Lights:
	global _lights_instance
	if _lights_instance is None:
		_lights_instance = (Lights() if ON_PI else DummyLights())
	return _lights_instance
