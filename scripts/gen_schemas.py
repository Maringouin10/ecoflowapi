"""Generate parsers/schemas.py from public .proto definitions.

Usage:
    python scripts/gen_schemas.py <tolwi_proto_dir> <iobroker_dpu_js> <ref_ecocharge_proto>

Sources (see THIRD_PARTY_NOTICES.md):
  tolwi/hassio-ecoflow-cloud  devices/internal/proto/*.proto   (Apache-2.0)
  foxthefox/ioBroker.ecoflow-mqtt lib/dict_data/ef_deltaproultra_data.js (MIT)
  shuette42/ecoflow-energy-ha ecoflow/proto/ecocharge.proto     (MIT)

Field numbers are merged message by message; the first source to name a
number wins and conflicts are printed.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

KINDS = {
    "float": "FLOAT",
    "double": "DOUBLE",
    "uint32": "UINT",
    "uint64": "UINT",
    "fixed32": "UINT",
    "fixed64": "UINT",
    "int32": "INT",
    "int64": "INT",
    "sint32": "SINT",
    "sint64": "SINT",
    "bool": "BOOL",
    "string": "STRING",
    "bytes": "BYTES",
}
FIELD_RE = re.compile(
    r"^\s*(?:oneof\s+\w+\s*\{\s*)?(optional\s+|repeated\s+)?([.\w]+)\s+(\w+)\s*=\s*(\d+)\s*;"
)


def parse_proto(text: str) -> tuple[dict[str, list], set[str]]:
    """Return {message: [(number, name, type, repeated)]} and enum names."""
    text = re.sub(r"//[^\n]*", "", text)
    messages: dict[str, list] = {}
    enums = set(re.findall(r"\benum\s+(\w+)", text))
    for match in re.finditer(r"\bmessage\s+(\w+)\s*\{", text):
        name = match.group(1)
        depth, i = 1, match.end()
        while depth and i < len(text):
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        body = text[match.end() : i - 1]
        fields = []
        for line in body.splitlines():
            m = FIELD_RE.match(line)
            if m:
                label, typ, fname, number = m.groups()
                fields.append(
                    (int(number), fname, typ.lstrip("."), (label or "").strip() == "repeated")
                )
        messages[name] = fields
    return messages, enums


class Builder:
    def __init__(self) -> None:
        self.out: list[str] = []
        self.done: set[str] = set()

    def schema(self, var: str, sources: list[tuple[dict, set, str]]) -> None:
        merged: dict[int, tuple] = {}
        for messages, enums, msg_name in sources:
            for number, name, typ, repeated in messages.get(msg_name, []):
                if number in merged:
                    if merged[number][0] != name:
                        print(f"{var}: field {number} {merged[number][0]} kept, {name} ignored")
                    continue
                merged[number] = (name, typ, repeated, messages, enums)
        lines = [f"{var}: dict[int, Field] = {{"]
        for number in sorted(merged):
            name, typ, repeated, messages, enums = merged[number]
            rep = ", repeated=True" if repeated else ""
            if typ in KINDS:
                lines.append(f'    {number}: Field("{name}", {KINDS[typ]}{rep}),')
            elif typ in enums or typ not in messages:
                lines.append(f'    {number}: Field("{name}", UINT{rep}),')
            else:
                sub = f"_{typ.upper()}"
                if sub not in self.done:
                    self.done.add(sub)
                    self.schema(sub, [(messages, enums, typ)])
                lines.append(f'    {number}: Field("{name}", MSG, {sub}{rep}),')
        lines.append("}\n")
        self.out.append("\n".join(lines))


def iobroker_proto(js_path: Path) -> str:
    text = js_path.read_text(encoding="utf-8")
    start = text.index("const protoSource = `") + len("const protoSource = `")
    return text[start : text.index("`", start)]


def main() -> None:
    tolwi, iob_js, ref_proto = (Path(p) for p in sys.argv[1:4])
    d3 = (*parse_proto((tolwi / "ef_delta3.proto").read_text()), "")
    r3 = (*parse_proto((tolwi / "ef_river3.proto").read_text()), "")
    dp3 = (*parse_proto((tolwi / "ef_dp3_iobroker.proto").read_text()), "")
    ref = (*parse_proto(ref_proto.read_text()), "")
    dpu = (*parse_proto(iobroker_proto(iob_js)), "")

    def src(p, name):
        return (p[0], p[1], name)

    b = Builder()
    b.schema(
        "GEN3_DISPLAY",
        [
            src(d3, "Delta3DisplayPropertyUpload"),
            src(r3, "River3DisplayPropertyUpload"),
            src(ref, "Delta3DisplayProperty"),
            src(dp3, "DP3DisplayPropertyUpload"),
        ],
    )
    b.schema(
        "GEN3_RUNTIME",
        [
            src(d3, "Delta3RuntimePropertyUpload"),
            src(r3, "River3RuntimePropertyUpload"),
            src(dp3, "DP3RuntimePropertyUpload"),
        ],
    )
    b.schema("GEN3_BMS", [src(d3, "Delta3BMSHeartBeatReport"), src(r3, "River3BMSHeartBeatReport")])
    b.schema("DPU_APP_SHOW", [src(dpu, "AppShowHeartbeatReport")])
    b.schema("DPU_BACKEND", [src(dpu, "BackendRecordHeartbeatReport")])
    b.schema("DPU_APP_PARA", [src(dpu, "AppParaHeartbeatReport")])
    b.schema("DPU_BP_INFO", [src(dpu, "BPInfo")])
    b.schema("DPU_DISPLAY", [src(dpu, "DisplayPropertyUpload")])

    header = (
        '"""Full protobuf schemas - GENERATED by scripts/gen_schemas.py, do not edit.\n\n'
        "Every field number with a known name, merged from the public definitions\n"
        "listed in THIRD_PARTY_NOTICES.md. Parsers map the well-understood fields\n"
        'to named sensors and expose all the others as raw values.\n"""\n\n'
        "# ruff: noqa: E501\n"
        "from __future__ import annotations\n\n"
        "from ..proto import BOOL, BYTES, DOUBLE, FLOAT, INT, MSG, SINT, STRING, UINT, Field\n\n"
        '__all__ = ["BOOL", "BYTES", "DOUBLE", "FLOAT", "INT", "MSG", "SINT", "STRING", "UINT", "Field"]\n\n'
    )
    out = (
        Path(__file__).resolve().parent.parent / "custom_components/ecoflow_app/parsers/schemas.py"
    )
    out.write_text(header + "\n".join(b.out), encoding="utf-8")


if __name__ == "__main__":
    main()
