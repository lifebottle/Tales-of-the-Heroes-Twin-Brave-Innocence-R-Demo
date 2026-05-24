import os
import struct
import xml.etree.ElementTree as ET

SCRIPT_DIR = os.path.dirname(__file__)

ARC_DIR = os.path.normpath(
    os.path.join(SCRIPT_DIR, "../../../1_extracted/all")
)

XML_DIR = os.path.normpath(
    os.path.join(SCRIPT_DIR, "../../../2_translated/menu")
)

OUTPUT_DIR = os.path.normpath(
    os.path.join(SCRIPT_DIR, "../../../3_patched/all")
)


def write_u8(f, val):
    f.write(struct.pack("<B", val))


def write_u32(f, val):
    f.write(struct.pack("<I", val))


def encode_string(text):
    # Always produce a valid string, even if empty
    if text is None:
        text = ""

    try:
        encoded = text.encode("euc_jp")
    except:
        encoded = text.encode("euc_jp", errors="replace")

    return b"\x40" + encoded + b"\x00"


def parse_xml(path):
    tree = ET.parse(path)
    root = tree.getroot()

    sections = []

    # 🔥 One <Strings> block = one section
    for strings_block in root.findall("Strings"):
        current_section = []

        for elem in strings_block:
            if elem.tag == "Entry":
                jp = elem.findtext("JapaneseText", default="")
                en = elem.findtext("EnglishText", default="")
                entry_id = int(elem.findtext("Id", default="0"))

                text = en.strip() if en.strip() else jp

                current_section.append({
                    "id": entry_id,
                    "text": text
                })

        if current_section:
            current_section.sort(key=lambda x: x["id"])
            sections.append(current_section)

    return sections


def build_mlt(sections, output_path):
    with open(output_path, "wb") as f:

        # HEADER
        f.write(b"MLT")
        write_u8(f, len(sections))

        section_ptr_pos = f.tell()
        f.write(b"\x00\x00\x00\x00" * len(sections))

        section_offsets = []

        # 🔥 Global string cache (dedup)
        string_cache = {}

        # SECTIONS
        for section in sections:
            section_offsets.append(f.tell())

            write_u32(f, len(section))

            entry_ptr_pos = f.tell()
            f.write(b"\x00\x00\x00\x00" * len(section))

            entry_offsets = []

            for entry in section:
                text = entry["text"]

                # Always encode (even empty → 0x40 00)
                data = encode_string(text)

                # 🔥 Exact dedup
                if data in string_cache:
                    entry_offsets.append(string_cache[data])
                else:
                    offset = f.tell()
                    f.write(data)

                    string_cache[data] = offset
                    entry_offsets.append(offset)

            # Patch entry pointers
            cur = f.tell()
            f.seek(entry_ptr_pos)

            for ptr in entry_offsets:
                write_u32(f, ptr)

            f.seek(cur)

        # Patch section pointers
        cur = f.tell()
        f.seek(section_ptr_pos)

        for ptr in section_offsets:
            write_u32(f, ptr)

        f.seek(cur)


def main():
    print("ARC DIR:", ARC_DIR)
    print("XML DIR:", XML_DIR)
    print("OUT DIR:", OUTPUT_DIR)

    count = 0
    missing_xml = 0

    for root, _, files in os.walk(ARC_DIR):
        for name in files:
            if not name.endswith(".mlb"):
                continue

            input_path = os.path.join(root, name)

            xml_name = os.path.splitext(name)[0] + ".xml"
            xml_path = os.path.join(XML_DIR, xml_name)

            if not os.path.exists(xml_path):
                print(f"[SKIP] No XML for {name}")
                missing_xml += 1
                continue

            rel_path = os.path.relpath(input_path, ARC_DIR)
            output_path = os.path.join(OUTPUT_DIR, rel_path)

            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            print(f"[BUILD] {rel_path}")

            sections = parse_xml(xml_path)
            build_mlt(sections, output_path)

            count += 1

    print(f"Done. Built: {count} | Missing XML: {missing_xml}")


if __name__ == "__main__":
    main()