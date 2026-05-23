from __future__ import annotations

import argparse
import logging

from .controller import RotationStage, RotationStageError


LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(message)s"
LOGGER = logging.getLogger("rotation-stage")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rotation-stage",
        description="Control a single-axis FluidNC rotation stage from the command line.",
    )
    parser.add_argument("--port", required=True, help="Serial port, for example COM13.")
    parser.add_argument("--baudrate", type=int, default=115200, help="Serial baudrate.")
    parser.add_argument("--timeout", type=float, default=2.0, help="Serial read timeout in seconds.")
    parser.add_argument("--wait-timeout", type=float, default=20.0, help="Wait timeout in seconds.")
    parser.add_argument("--feed", type=float, default=None, help="Motion feed rate in deg/min.")
    parser.add_argument("--home", action="store_true", help="Run homing before moving.")
    parser.add_argument("--move-to", type=float, default=None, help="Move to an absolute angle in degrees.")
    return parser


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt="%H:%M:%S")


def main() -> int:
    configure_logging()
    args = build_parser().parse_args()

    if not args.home and args.move_to is None:
        raise SystemExit("At least one action is required: use --home and/or --move-to ANGLE.")

    LOGGER.info("Connecting to %s", args.port)
    stage = RotationStage.connect(args.port, baudrate=args.baudrate, timeout=args.timeout)

    try:
        LOGGER.info("Connection established")

        if args.home:
            LOGGER.info("Starting homing cycle")
            stage.home()
            stage.wait(timeout=args.wait_timeout)
            LOGGER.info("Homing complete")

        if args.move_to is not None:
            LOGGER.info("Moving to %.3f deg", args.move_to)
            stage.move_to(args.move_to, feed=args.feed)
            stage.wait(timeout=args.wait_timeout)
            LOGGER.info("Move complete")

        position = stage.position()
        LOGGER.info("Current position: %.3f deg", position)
        return 0
    except RotationStageError as exc:
        LOGGER.error("%s", exc)
        return 1
    finally:
        stage.disconnect()
        LOGGER.info("Disconnected")
