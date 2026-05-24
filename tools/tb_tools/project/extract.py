import argparse
import sys
from pathlib import Path

import pyeboot
from loguru import logger
from pycdlib import pycdlib
from tqdm.rich import tqdm

import tb_tools.project.paths as tb_paths
from tb_tools.formats.arc import Arc
from tb_tools.formats.bdi import Bdi
from tb_tools.formats.ppt import PPT_MAGIC, Ppt

__SCRIPT_CMD = "extract"
__SCRIPT_DESC = (
    "Given a Twin Brave iso extracts the files, namco.bdi and misc files to xml"
)


def main(iso_path: Path, iso_only: bool, xml: bool):
    logger.debug(f"{iso_only}, {iso_path}")

    extract_iso(iso_path)
    decrypt_eboot()

    if iso_only:
        return

    extract_files()

    if xml:
        return

    # extract_xmls()


def extract_iso(iso_path: Path) -> None:
    print("Extracting ISO files...")

    if iso_path is None:
        files = tb_paths.iso_files / "PSP_GAME"
        if files.exists() and files.is_dir():
            logger.info("No iso path provided but files present in 0_disc")
            logger.info("Continuing with files in 0_disc")
            return

        iso_path = tb_paths.default_iso
        logger.info("No iso path provided and no files in 0_disc")

        if iso_path.exists():
            logger.info(f"Using default name {iso_path.stem}")
        else:
            logger.info(f"Can't find default iso ({iso_path.stem}), exiting...")
            sys.exit(-1)

    iso = pycdlib.PyCdlib()
    iso.open(str(iso_path))

    ext_folder = tb_paths.iso_files
    tb_paths.clean_folder(ext_folder)

    files: list[Path] = []

    for dirname, _, filelist in iso.walk(iso_path="/"):
        for file in filelist:
            p = dirname + "/" + file
            p = p.lstrip("/")
            files.append(Path(p))

    total_size = 0
    for file in files:
        with iso.open_file_from_iso(iso_path="/" + file.as_posix()) as f:
            f.seek(0, 2)
            total_size += f.tell()

    with tqdm(
        total=total_size,
        desc=f"Extracting {file.as_posix()}",
        unit="B",
        unit_divisor=1024,
        unit_scale=True,
    ) as pbar:
        for file in files:
            out_path = ext_folder / file
            out_path.parent.mkdir(parents=True, exist_ok=True)
            pbar.set_description(file.as_posix())
            with (
                iso.open_file_from_iso(iso_path="/" + file.as_posix()) as f,
                out_path.open("wb+") as output,
            ):
                while data := f.read(0x8000):
                    output.write(data)
                    pbar.update(len(data))

    iso.close()


def decrypt_eboot() -> None:
    in_path = tb_paths.original_eboot
    out_path = tb_paths.decrypted_eboot
    pyeboot.decrypt(str(in_path), str(out_path))


def extract_files() -> None:
    print("Extracting Game files...")

    _out = tb_paths.bdi_files
    _bdi = tb_paths.namco_bdi
    _hsh = tb_paths.hashes
    with Bdi(_bdi, _hsh) as bdi:
        for file in (pbar := tqdm(bdi.files)):
            pbar.set_description(file.rel_path.as_posix())

            rel_path, data = bdi._read_blob(file)
            out_path = _out / rel_path
            out_path.parent.mkdir(parents=True, exist_ok=True)

            # keep this in case we want to make BDIs from nothing
            # if file.is_compressed:
            #     out_path.with_suffix(".gz" + "".join(out_path.suffixes))

            if file.is_arc:
                Arc(data).save_all(out_path)
            elif len(data) > 4 and data[:4] == PPT_MAGIC:
                Ppt(data).save_png(out_path)
            else:
                out_path.write_bytes(data)


def add_arguments_to_parser(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--iso-only",
        help="Extract only the iso files",
        action="store_true",
    )
    parser.add_argument(
        "--xml",
        help="Re-Extract xml files",
        action="store_true",
    )
    parser.add_argument(
        "--iso",
        help="Path to the game's .iso file",
        default=None,
        type=Path,
    )


def process_arguments(args: argparse.Namespace):
    main(args.iso, args.iso_only, args.xml)


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
