# PWM bridge – plain-language guide

This page walks through the CAN-to-PWM helper that was added to openpilot.  It
is written in very simple English so you can copy, paste, and run the exact
commands without digging into the source code first.

The bridge lets openpilot **pretend it is driving a real car**, but instead of
talking to a CAN bus it writes the “car commands” out as PWM values inside a CSV
file.  That CSV can then be read by a microcontroller on a scooter (or any
project that understands PWM signals).

---

## 1. One-line setup and launch

Copy and paste the line below into a shell inside the openpilot repository.
This installs everything and then starts the webcam-based simulator plus the PWM
bridge.  When the command finishes, the CSV file will start filling with PWM
numbers.

```bash
./scripts/setup_pwm_bridge.sh && ./scripts/run_webcam_pwm_autopilot.sh
```

What happens automatically:

1. A Python virtual environment called `pwm-env` is created (or reused).
2. openpilot and the CAN→PWM tools are installed into that environment.
3. openpilot boots in webcam mode, so it thinks the webcam feed is the forward
   camera of a car.
4. The bridge listens to the fake CAN bus traffic that openpilot sends to the
   simulated car.
5. Every CAN byte becomes a PWM value, and each value is written into
   `~/openpilot_pwm/pwm_capture.csv`.

If you ever need to stop the system, press <kbd>Ctrl</kbd>+<kbd>C</kbd>.  All
processes exit cleanly.

---

## 2. What each helper file does

| File | Why it matters |
|------|----------------|
| `scripts/setup_pwm_bridge.sh` | Creates the Python environment, installs dependencies (openpilot, OpenCV) and leaves you ready to launch. |
| `scripts/run_webcam_pwm_autopilot.sh` | Activates the environment, launches openpilot with the webcam simulator, starts the PWM bridge, and saves the CSV output. |
| `selfdrive/pwm_bridge/bridge.py` | Connects to openpilot’s CAN messages, converts each one to PWM samples, and writes CSV rows. |
| `selfdrive/pwm_bridge/translator.py` | Holds the math that maps raw CAN bytes (0–255) into PWM duty cycles and pulse widths. |
| `docs/pwm_bridge.md` (this file) | Explains how to run everything and how to interpret the CSV output. |

---

## 3. Understanding the PWM CSV

The CSV is created at `~/openpilot_pwm/pwm_capture.csv` (change the
`PWM_OUTPUT_DIR` environment variable if you need another location).  Each line
shows one PWM channel derived from one CAN frame.

| Column | In plain words |
|--------|----------------|
| `logMonoTime` | When the CAN message was created (nanoseconds since boot). |
| `address` | Which CAN address the message came from.  Think of this as the “message ID”. |
| `src` | Which CAN bus the message came from (0 is usually camera, 1 is powertrain, etc.). |
| `busTime` | Timing info from the CAN hardware.  Most people can ignore this. |
| `channel` | PWM channel number.  Channel 0 is the first data byte, channel 1 is the second, and so on. |
| `dutyCycle` | Duty cycle value between 0.0 and 1.0.  Higher means “more on”. |
| `pulseWidthUs` | Pulse width in microseconds.  Useful if your MCU expects 1000–2000 μs steering/throttle style PWM. |

### Mapping cheat sheet

Every byte from the CAN frame becomes one PWM channel:

```
CAN frame 0x123 (data = [0x10, 0x80, 0xFF])
  ├─ Channel 0 gets 0x10 → 1062 µs pulse (~10 % duty at 50 Hz)
  ├─ Channel 1 gets 0x80 → 1500 µs pulse (~50 % duty at 50 Hz)
  └─ Channel 2 gets 0xFF → 2000 µs pulse (~100 % duty at 50 Hz)
```

This mapping is fixed and repeatable:

* Raw CAN byte 0 = minimum pulse (1000 µs by default)
* Raw CAN byte 128 = middle pulse (1500 µs by default)
* Raw CAN byte 255 = maximum pulse (2000 µs by default)

You can change the range or the frequency when you launch the bridge:

```bash
python -m openpilot.selfdrive.pwm_bridge.bridge ~/openpilot_pwm/custom.csv \
  --frequency 100 --min-us 900 --max-us 2100
```

> **Tip:** 50 Hz with 1000–2000 µs is the normal hobby servo range.  Increase
> the frequency or adjust the limits if your scooter MCU needs something else.

---

## 4. Checking that everything is running

1. **Look at the logs:** The launch script prints messages like `wrote 500 pwm
   samples in 8.2s`.  That means data is flowing.
2. **Watch the CSV live:**

   ```bash
   tail -f ~/openpilot_pwm/pwm_capture.csv
   ```

   You should see new rows appear every few seconds.
3. **Openpilot UI:** When the simulator is running you can also open the Qt UI
   (`./launch_openpilot.sh`) to confirm it sees the webcam video and is
   “engaged”.

Because this is a webcam-based simulator, openpilot believes it is in a car and
keeps publishing steering/throttle/brake CAN messages.  The bridge captures all
of those without talking to a real vehicle.

---

## 5. Using the PWM values on your scooter

* Point your microcontroller (for example, an STM32 or ESP32) at the CSV file
  or stream it over serial/USB.
* For each line, match `channel` to the PWM output you care about (steering,
  throttle, brake, etc.).  You may need to log the scooter’s original CAN data
  to figure out which CAN addresses hold the signals you want.
* Use the provided `pulseWidthUs` column directly if your firmware expects the
  typical RC-style servo format.
* If you want to drive real hardware, replace the CSV writer with code that sets
  hardware PWM timers using the same duty cycle/pulse width numbers.

> **Important safety reminder:** The webcam simulator is perfect for software
> bring-up, but a real scooter will need proper calibration and safety checks.
> Double-check every signal path before feeding the PWM outputs into the MCU
> that controls a live vehicle.

---

## 6. Troubleshooting quick answers

| Problem | Quick fix |
|---------|-----------|
| `Virtual environment not found` | Run `./scripts/setup_pwm_bridge.sh` before the launch script. |
| CSV file is empty | Give the simulator a few seconds; the first CAN messages take a moment to appear.  Also check that the webcam is detected. |
| Need a different output folder | Set `PWM_OUTPUT_DIR=/path/to/folder` before running the launch script. |
| Want to run bridge alone | `source pwm-env/bin/activate` and then run `python -m openpilot.selfdrive.pwm_bridge.bridge ~/file.csv`. |

If you hit something else, the bridge logs errors to the console before it
exits, so start by reading the terminal output.

---

## 7. Summary for quick copy/paste

```
# inside the openpilot repo
./scripts/setup_pwm_bridge.sh && ./scripts/run_webcam_pwm_autopilot.sh

# watch the PWM stream
tail -f ~/openpilot_pwm/pwm_capture.csv
```

That is all you need to boot the simulator, make openpilot think it is driving,
and see the PWM values it would send to a real scooter.

