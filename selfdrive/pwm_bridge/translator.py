from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, List


@dataclass
class PwmSample:
  """A single PWM sample derived from a CAN frame."""

  log_mono_time: int
  address: int
  src: int
  bus_time: int
  channel: int
  duty_cycle: float
  pulse_width_us: float


class CanToPwmTranslator:
  """Convert CAN frames into PWM duty cycles.

  The mapping implemented here is intentionally generic: each byte in a CAN
  data payload is interpreted as a PWM channel value with a configurable
  minimum and maximum pulse width.  This keeps the code flexible enough for
  prototyping while still providing deterministic behaviour that can be tested
  without access to vehicle specific calibration data.
  """

  def __init__(self, *, min_pulse_us: float = 1000.0, max_pulse_us: float = 2000.0,
               frequency_hz: float = 50.0) -> None:
    if min_pulse_us <= 0 or max_pulse_us <= 0:
      raise ValueError("Pulse widths must be positive")
    if max_pulse_us <= min_pulse_us:
      raise ValueError("max_pulse_us must be greater than min_pulse_us")
    if frequency_hz <= 0:
      raise ValueError("PWM frequency must be positive")

    self._min_pulse_us = float(min_pulse_us)
    self._max_pulse_us = float(max_pulse_us)
    self._frequency_hz = float(frequency_hz)

  @property
  def min_pulse_us(self) -> float:
    return self._min_pulse_us

  @property
  def max_pulse_us(self) -> float:
    return self._max_pulse_us

  @property
  def frequency_hz(self) -> float:
    return self._frequency_hz

  def translate(self, *, log_mono_time: int, address: int, src: int, bus_time: int,
                data: Iterable[int]) -> List[PwmSample]:
    """Translate a CAN frame into a list of :class:`PwmSample` values."""

    samples: List[PwmSample] = []
    for channel, raw_value in enumerate(data):
      pulse_width = self._pulse_width_from_raw(raw_value)
      duty_cycle = self._pulse_to_duty_cycle(pulse_width)

      samples.append(PwmSample(
        log_mono_time=log_mono_time,
        address=address,
        src=src,
        bus_time=bus_time,
        channel=channel,
        duty_cycle=duty_cycle,
        pulse_width_us=pulse_width,
      ))

    return samples

  def _pulse_width_from_raw(self, value: int) -> float:
    value = max(0, min(255, int(value)))
    normalized = value / 255.0
    return self._min_pulse_us + normalized * (self._max_pulse_us - self._min_pulse_us)

  def _pulse_to_duty_cycle(self, pulse_width: float) -> float:
    period_us = 1_000_000.0 / self._frequency_hz
    pulse_width = max(self._min_pulse_us, min(self._max_pulse_us, pulse_width))
    return pulse_width / period_us

