import argparse

from extract_generator.build import build
from extract_generator.output import write_all


def main(argv=None):
    parser = argparse.ArgumentParser(prog="extract_generator", description="Write synthetic case management extracts.")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--out", default="output")
    args = parser.parse_args(argv)
    write_all(build(args.seed), args.out)


if __name__ == "__main__":
    main()
