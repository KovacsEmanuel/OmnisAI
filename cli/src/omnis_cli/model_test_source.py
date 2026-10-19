"""Finite source inventory shared by bundle assembly and release validation."""

from pathlib import PurePosixPath

PACKAGE = "records-mapping-contract"
PACKAGE_FILES = (
    "SKILL.md",
    "omnis.yaml",
    "NOTICE.md",
    "references/methodology.md",
    "templates/procedures/map-records.yaml",
    "templates/schemas/records.schema.json",
    "templates/schemas/operations.schema.json",
    "templates/schemas/surface_map.schema.json",
    "templates/schemas/empty.schema.json",
)
SOURCE_FILES = {"model-test/profile.yaml"} | {
    "model-test/skills/" + PACKAGE + "/" + name for name in PACKAGE_FILES
}
SOURCE_DIRS = {str(PurePosixPath(name).parent) for name in SOURCE_FILES}
SOURCE_DIRS |= {
    "model-test",
    "model-test/skills",
    "model-test/skills/" + PACKAGE,
    "model-test/skills/" + PACKAGE + "/templates",
}
