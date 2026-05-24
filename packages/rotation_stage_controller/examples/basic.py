import logging

from rotation_stage_controller import RotationStage


LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(message)s"
LOGGER = logging.getLogger("rotation-stage-example")


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt="%H:%M:%S")


def log_step(message: str) -> None:
    LOGGER.info("%s", message)


def main() -> None:
    configure_logging()
    log_step("Connecting to rotation stage on COM13")
    stage = RotationStage.connect("COM14", baudrate=115200)
    log_step("Connection established")
    try:
        # log_step("Starting homing cycle")
        # stage.home()
        # stage.wait(timeout=60.0)
        # log_step("Homing complete")

        log_step("Moving to 90.0 deg")
        stage.move_to(90, feed=600)
        stage.wait(timeout=30.0)
        log_step("Reached 90.0 deg")

        log_step("Rotating by -15.0 deg")
        stage.rotate(-15, feed=600)
        stage.wait(timeout=30.0)
        log_step("Relative move complete")

        position = stage.position()
        log_step(f"Current position: {position:.3f} deg")
    finally:
        log_step("Disconnecting")
        stage.disconnect()
        log_step("Disconnected")


if __name__ == "__main__":
    main()
