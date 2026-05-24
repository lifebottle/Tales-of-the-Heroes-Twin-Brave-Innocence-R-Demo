import argparse
import sys
from pathlib import Path

from tb_tools.formats.arc import Arc
from tb_tools.formats.ppt import PPT_MAGIC, Ppt
import tb_tools.project.paths as tb_paths
from tb_tools.formats.bdi import Bdi
from tqdm.rich import tqdm

__SCRIPT_CMD = "bdi"
__SCRIPT_DESC = "BDI tools"

def main(args):
    if args.extract:
        out: Path = args.output
        with Bdi(args.extract, args.hashes) as bdi:
            if args.expand:
                for file in (pbar := tqdm(bdi.files)):
                    pbar.set_description(file.rel_path.as_posix())

                    rel_path, data = bdi._read_blob(file)
                    out_path = out / rel_path
                    out_path.parent.mkdir(parents=True, exist_ok=True)

                    if file.is_arc:
                        Arc(data).save_all(out_path)
                    elif len(data) > 4 and data[:4] == PPT_MAGIC:
                        Ppt(data).save_png(out_path)
                    else:
                        out_path.write_bytes(data)
                return
            if args.files is None:
                bdi.save_all_p(out)
            else:
                for file in args.files:
                    p, b = bdi.get_file(file)
                    if p is not None and b is not None:
                        print(f"Extracting {p.as_posix()}")
                        o = out / p
                        o.parent.mkdir(parents=True, exist_ok=True)
                        o.write_bytes(b)
            print("Done!")
    elif args.overlay:
        if args.bdi is None:
            print("Missing --bdi argument!")
            sys.exit(-1)

        if args.output is None:
            print("Missing --output argument!")
            sys.exit(-1)

        with Bdi(args.bdi, args.hashes) as bdi:
            bdi.update_and_save(args.output, args.overlay)

def add_arguments_to_parser(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--extract",
        help="path to bdi file",
        type=Path,
        required=False,
        metavar="PATH",
    )
    parser.add_argument(
        "--overlay",
        help="path to overlay folder",
        type=Path,
        required=False,
        metavar="PATH",
    )
    parser.add_argument(
        "--bdi",
        help="path to original bdi",
        type=Path,
        required=False,
        metavar="PATH",
    )
    parser.add_argument(
        "--hashes",
        help="path to a json with hash-name pairs",
        type=Path,
        default=tb_paths.hashes,
        metavar="PATH",
    )
    parser.add_argument(
        "--output",
        help="path to output folder",
        type=Path,
        default=Path("bdi"),
        metavar="PATH",
    )
    parser.add_argument(
        "--expand",
        help="Expand all ARC and PPT files",
        action="store_true",
    )
    parser.add_argument(
        "--files",
        help=(
            "Extract selected file(s) from the bdi, accepts paths "
            "or hashes if prefixed with a $"
        ),
        nargs="*",
        type=str,
        metavar="PATH",
    )


def process_arguments(args: argparse.Namespace):
    main(args)

def add_subparser(subparser: argparse._SubParsersAction):
    parser = subparser.add_parser(
        __SCRIPT_CMD, help=__SCRIPT_DESC, description=__SCRIPT_DESC
    )
    add_arguments_to_parser(parser)
    parser.set_defaults(func=process_arguments)


parser = argparse.ArgumentParser(description=__SCRIPT_DESC)
add_arguments_to_parser(parser)

if __name__ == "__main__":
    args = parser.parse_args()
    process_arguments(args)
