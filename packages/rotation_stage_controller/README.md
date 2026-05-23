# rotation-stage-controller

Minimal Python package for controlling a single-axis rotation stage over a serial connection to FluidNC.

## Install

```bash
pip install "git+https://github.com/TDA-2030/rotation-stage-controller.git#subdirectory=packages/rotation_stage_controller"
```

For local editable development:

```bash
cd packages/rotation_stage_controller
pip install -e .
```

## Usage

```python
from rotation_stage_controller import RotationStage

stage = RotationStage.connect("COM5", baudrate=115200)

stage.home()
stage.move_to(90)
stage.rotate(-15)
print(stage.position())
stage.wait()
stage.disconnect()
```

## Notes

- The controller assumes the stage is exposed as the `X` axis.
- The stage angle is treated directly as the `X` axis position in degrees.
- The default motion range is `0` to `360` degrees.
