"""Minimal kernel entry point for workspace validation."""

from . import __version__


def main() -> None:
    print(f"voiceready-kernel {__version__}")


if __name__ == "__main__":
    main()
