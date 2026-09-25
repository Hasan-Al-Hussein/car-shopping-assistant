"""Validate coordinates before openpyxl's streaming reader can discard bad nodes."""

import posixpath
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from xml.etree.ElementTree import fromstring, iterparse
from zipfile import ZipFile

SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CELL_COORDINATE = re.compile(r"([A-Z]{1,3})([1-9][0-9]{0,6})\Z")
MAX_XML_NODES = 250_000


@dataclass(frozen=True)
class CellStorage:
    """Original XML tokens supplement values decoded by openpyxl (e.g. dates)."""

    data_type: str
    value: str | None = field(repr=False)
    formula: str | None = field(repr=False)


@dataclass(frozen=True)
class SheetStructure:
    error: str | None
    cells: dict[str, CellStorage] = field(default_factory=dict, repr=False)


def _inspect_coordinates(archive: ZipFile, path: str, max_rows: int) -> SheetStructure:
    previous_row = 0
    current_row: int | None = None
    previous_column = 0
    cells: dict[str, CellStorage] = {}
    parents: list[str] = []
    sheet_data_seen = False
    with archive.open(path) as stream:
        for node_count, (event, element) in enumerate(iterparse(stream, events=("start", "end"))):
            if node_count > MAX_XML_NODES:
                return SheetStructure("SHEET_STRUCTURE_LIMIT", cells)
            if event == "start":
                parent = parents[-1] if parents else None
                if not parents and element.tag != f"{{{SHEET_NS}}}worksheet":
                    return SheetStructure("WORKSHEET_ROOT_INVALID", cells)
                if element.tag == f"{{{SHEET_NS}}}sheetData":
                    if parent != f"{{{SHEET_NS}}}worksheet" or sheet_data_seen:
                        return SheetStructure("WORKSHEET_HIERARCHY_INVALID", cells)
                    sheet_data_seen = True
                elif element.tag == f"{{{SHEET_NS}}}row":
                    if parent != f"{{{SHEET_NS}}}sheetData":
                        return SheetStructure("WORKSHEET_HIERARCHY_INVALID", cells)
                elif element.tag == f"{{{SHEET_NS}}}c" and parent != f"{{{SHEET_NS}}}row":
                    return SheetStructure("WORKSHEET_HIERARCHY_INVALID", cells)
                parents.append(element.tag)
            else:
                parents.pop()
            if event == "start" and element.tag == f"{{{SHEET_NS}}}row":
                label = element.get("r", "")
                if not re.fullmatch(r"[1-9][0-9]{0,6}", label):
                    return SheetStructure("ROW_COORDINATE_INVALID", cells)
                row = int(label)
                if current_row is not None or row <= previous_row:
                    return SheetStructure("ROW_COORDINATE_DUPLICATE_OR_UNORDERED", cells)
                if row > max_rows:
                    return SheetStructure("SHEET_STRUCTURE_LIMIT", cells)
                current_row = previous_row = row
                previous_column = 0
            elif event == "start" and element.tag == f"{{{SHEET_NS}}}c":
                match = CELL_COORDINATE.fullmatch(element.get("r", ""))
                if match is None or current_row is None:
                    return SheetStructure("CELL_COORDINATE_INVALID", cells)
                column = 0
                for letter in match[1]:
                    column = column * 26 + ord(letter) - ord("A") + 1
                if int(match[2]) != current_row or column > 16_384:
                    return SheetStructure("CELL_COORDINATE_INVALID", cells)
                if column <= previous_column:
                    return SheetStructure("CELL_COORDINATE_DUPLICATE_OR_UNORDERED", cells)
                previous_column = column
            elif event == "end":
                if element.tag == f"{{{SHEET_NS}}}row":
                    current_row = None
                    element.clear()
                elif element.tag == f"{{{SHEET_NS}}}c":
                    children = [child.tag for child in element]
                    allowed = {f"{{{SHEET_NS}}}{name}" for name in ("f", "v", "is", "extLst")}
                    if any(tag not in allowed or children.count(tag) > 1 for tag in children):
                        return SheetStructure("CELL_STORAGE_INVALID", cells)
                    if element.get("t") == "inlineStr" and (
                        f"{{{SHEET_NS}}}v" in children or f"{{{SHEET_NS}}}f" in children
                    ):
                        return SheetStructure("CELL_STORAGE_INVALID", cells)
                    if element.get("t") != "inlineStr" and f"{{{SHEET_NS}}}is" in children:
                        return SheetStructure("CELL_STORAGE_INVALID", cells)
                    value = element.findtext(f"{{{SHEET_NS}}}v")
                    if element.get("t") == "inlineStr":
                        value = "".join(
                            item.text or "" for item in element.iter(f"{{{SHEET_NS}}}t")
                        )
                    cells[element.attrib["r"]] = CellStorage(
                        element.get("t", "n"), value, element.findtext(f"{{{SHEET_NS}}}f")
                    )
                    element.clear()
    return SheetStructure(None if sheet_data_seen else "WORKSHEET_HIERARCHY_INVALID", cells)


def inspect_structure(
    archive: ZipFile, sheets: Iterable[str], *, max_rows: int
) -> dict[str, SheetStructure]:
    """Return at most one safe structural reason per configured sheet, no values.

    Counts from a worksheet with invalid coordinates are explicitly incomplete;
    a lossy downstream reader must not certify its apparently valid row total.
    """
    workbook = fromstring(archive.read("xl/workbook.xml"))
    relationships = fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    by_id = {
        item.get("Id"): item for item in relationships.findall(f"{{{PACKAGE_NS}}}Relationship")
    }
    results: dict[str, SheetStructure] = {}
    for name in sheets:
        entries = [
            item for item in workbook.iter(f"{{{SHEET_NS}}}sheet") if item.get("name") == name
        ]
        if not entries:
            results[name] = SheetStructure("REQUIRED_SHEET_MISSING")
            continue
        if len(entries) != 1:
            results[name] = SheetStructure("SHEET_NAME_DUPLICATE")
            continue
        relationship = by_id.get(entries[0].get(f"{{{REL_NS}}}id"))
        if relationship is None or relationship.get("TargetMode") == "External":
            results[name] = SheetStructure("SHEET_RELATIONSHIP_INVALID")
            continue
        if relationship.get("Type") != f"{REL_NS}/worksheet":
            results[name] = SheetStructure("SHEET_NOT_WORKSHEET")
            continue
        target = relationship.get("Target", "")
        path = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "xl/" + target)
        if not path.startswith("xl/worksheets/") or path not in archive.namelist():
            results[name] = SheetStructure("SHEET_RELATIONSHIP_INVALID")
            continue
        results[name] = _inspect_coordinates(archive, path, max_rows)
    return results
