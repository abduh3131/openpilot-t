# Raw actuator output (no CAN send)

This guide explains how to run openpilot while *only* publishing raw actuator values,
without transmitting CAN messages to the vehicle. This is useful for offline analysis,
simulation, or validating controller outputs without touching the bus.

## What changes when raw actuator output is enabled

When raw actuator output is enabled:

- `carOutput.actuatorsOutput` continues to publish raw actuator values (steering, accel, braking, etc.).
- No messages are published on the `sendcan` socket.
- Control logic and state estimation still run normally.

## Enable raw actuator output

You can enable raw actuator output in one of two ways:

1. **Environment variable**

   ```
   export RAW_ACTUATORS_ONLY=1
   ```

2. **Persistent param**

   ```
   ./scripts/param set RawActuatorsOnly 1
   ```

Either method disables CAN sends and leaves `carOutput` as the primary output.

## Observing actuator outputs

Subscribe to `carOutput` to read raw actuator values:

```
./tools/cabana/cabana.sh  # or any cereal subscriber
```

Look for `carOutput.actuatorsOutput.*` fields in the message stream.
