import json
import re

HEADERS = {
    "name": ("name", "name"), "id": ("id", "id"), "version": ("version", "version"),
    "available": ("available", "verfügbar"), "source": ("source", "quelle"),
}
ID_RE = re.compile(r"^[A-Za-z0-9._+\-]+$")


def parse_json_output(output):
    document = json.loads(output)
    rows = document if isinstance(document, list) else document.get("Data", document.get("data", []))
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        def value(*keys):
            for key in keys:
                if row.get(key) is not None:
                    return str(row[key])
            return ""
        item = {"Name": value("Name", "name"), "Id": value("Id", "id"), "Version": value("Version", "version"),
                "AvailableVersion": value("Available", "AvailableVersion", "availableVersion"), "Source": value("Source", "source")}
        if item["Name"] and valid_package_id(item["Id"]):
            result.append(item)
    return result


def valid_package_id(package_id):
    return bool(package_id) and not package_id.endswith(".") and "…" not in package_id and "..." not in package_id and ID_RE.fullmatch(package_id) is not None


def _header_positions(header):
    found = {}
    for canonical, aliases in HEADERS.items():
        for alias in aliases:
            match = re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", header, re.IGNORECASE)
            if match:
                found[canonical] = match.start()
                break
    return sorted(found.items(), key=lambda pair: pair[1])


def parse_upgrade_output(output):
    lines = output.splitlines()
    separator = next((index for index, line in enumerate(lines) if line.replace("─", "-").count("-") >= 3), -1)
    if separator < 1:
        return []
    columns = _header_positions(lines[separator - 1])
    if not {"name", "id", "version"}.issubset(dict(columns)):
        return []
    results = []
    for line in lines[separator + 1:]:
        if not line.strip() or re.search(r"\b(upgrades?|aktualisierungen?)\b", line, re.IGNORECASE) and len(line.split()) < 7:
            continue
        values = {}
        for index, (column, start) in enumerate(columns):
            end = columns[index + 1][1] if index + 1 < len(columns) else len(line)
            values[column] = line[start:end].strip() if start < len(line) else ""
        package_id = values.get("id", "")
        if not valid_package_id(package_id):
            region = line[columns[[name for name, _ in columns].index("id")][1]:]
            candidates = [token.rstrip("…") for token in region.split() if ID_RE.fullmatch(token.rstrip("…")) and not re.fullmatch(r"[vV]?\d+\.\d+(?:\.\d+)?", token.rstrip("…"))]
            package_id = max(candidates, key=len, default="")
        if not values.get("name") or not valid_package_id(package_id):
            continue
        results.append({"Name": values["name"], "Id": package_id, "Version": values.get("version", ""),
                        "AvailableVersion": values.get("available", ""), "Source": values.get("source", "")})
    return results
