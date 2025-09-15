from __future__ import annotations
"""Pre-run hook: generate samplesheet.csv with strandedness=reverse."""

from ._samplesheet_common import generate


def main(ctx):
    return generate(ctx, strandedness="reverse")

