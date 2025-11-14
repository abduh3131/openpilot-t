#!/usr/bin/env python3
"""Stream CAN traffic from openpilot and mirror it as PWM samples.

The script subscribes to the ``can`` messaging channel, converts the payload of
each CAN frame into PWM information, and writes the result to a CSV file.  This
allows hobby hardware to consume the generated PWM signals without needing to
parse CAN frames directly.
"""

from __future__ import annotations

import argparse
import csv
import os
import signal
import sys
import time
from pathlib import Path
from typing import Iterable

from cereal import messaging

from openpilot.selfdrive.pwm_bridge.translator import CanToPwmTranslator, PwmSample


def _write_header(writer: csv.writer) -> None:
  writer.writerow([
    "logMonoTime",
    "address",
    "src",
    "busTime",
    "channel",
    "dutyCycle",
    "pulseWidthUs",
  ])


def _samples_from_message(translator: CanToPwmTranslator, msg) -> Iterable[PwmSample]:
  assert msg.which() == 'can'
  log_mono_time = msg.logMonoTime

  for frame in msg.can:
    yield from translator.translate(
      log_mono_time=log_mono_time,
      address=frame.address,
      src=frame.src,
      bus_time=frame.busTime,
      data=frame.dat,
    )


def stream_pwm(output_path: Path, *, frequency_hz: float, min_us: float,
               max_us: float, no_console: bool) -> None:
  translator = CanToPwmTranslator(
    frequency_hz=frequency_hz,
    min_pulse_us=min_us,
    max_pulse_us=max_us,
  )

  sock = messaging.sub_sock('can', conflate=False)
  poller = messaging.Poller()
  poller.register(sock)

  output_path.parent.mkdir(parents=True, exist_ok=True)
  with output_path.open('w', newline='') as output_file:
    writer = csv.writer(output_file)
    _write_header(writer)

    start_time = time.monotonic()
    received = 0

    while True:
      polled = poller.poll(1000)
      if not polled:
        continue

      message = messaging.recv_one(sock)
      if message is None:
        continue

      for sample in _samples_from_message(translator, message):
        writer.writerow([
          sample.log_mono_time,
          sample.address,
          sample.src,
          sample.bus_time,
          sample.channel,
          f"{sample.duty_cycle:.6f}",
          f"{sample.pulse_width_us:.3f}",
        ])
        received += 1

      if not no_console and received and received % 500 == 0:
        elapsed = time.monotonic() - start_time
        print(f"wrote {received} pwm samples in {elapsed:.1f}s", file=sys.stderr)


def _parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Mirror CAN messages as PWM CSV output")
  parser.add_argument("output", type=Path, help="Destination CSV file")
  parser.add_argument("--frequency", type=float, default=50.0,
                      help="PWM frequency in hertz (default: 50Hz)")
  parser.add_argument("--min-us", type=float, default=1000.0,
                      help="Minimum pulse width in microseconds (default: 1000)")
  parser.add_argument("--max-us", type=float, default=2000.0,
                      help="Maximum pulse width in microseconds (default: 2000)")
  parser.add_argument("--no-console", action='store_true',
                      help="Disable progress logging on stderr")
  return parser.parse_args()


def main() -> None:
  args = _parse_args()

  def _handle_sigint(signum, frame):
    raise KeyboardInterrupt()

  signal.signal(signal.SIGINT, _handle_sigint)
  signal.signal(signal.SIGTERM, _handle_sigint)

  try:
    stream_pwm(args.output, frequency_hz=args.frequency, min_us=args.min_us,
               max_us=args.max_us, no_console=args.no_console)
  except KeyboardInterrupt:
    print("PWM bridge stopped", file=sys.stderr)


if __name__ == "__main__":
  main()

