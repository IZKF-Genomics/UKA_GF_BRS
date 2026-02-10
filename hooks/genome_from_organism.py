from __future__ import annotations

def set_from_organism(ctx):
    """
    Pre-render hook: derive ctx.params.genome from ctx.params.organism
    when not provided on CLI.

    Mapping:
      human -> GRCh38
      mouse -> GRCm39
      rat   -> mRatBN7.2

    Behavior:
      - If ctx.params.genome is already set, do nothing (respect CLI/project).
      - If organism missing or unsupported, raise a clear error to avoid
        rendering with an undefined genome.
    """
    # Respect explicit genome if present
    if ctx.params.get("genome"):
        print(f"[hook:genome] genome={ctx.params.get('genome')} (pre-set)")
        return {"skipped": "genome already set"}

    org = ctx.params.get("organism")
    if not org:
        # Leave genome empty so user can edit run.sh manually
        ctx.params.setdefault("genome", "")
        print("[hook:genome] organism missing; genome not set")
        return {"skipped": "organism missing; genome left empty"}

    key = str(org).strip().lower()
    mapping = {
        "human": "GRCh38",
        "mouse": "GRCm39",
        "rat": "mRatBN7.2",
    }
    genome = mapping.get(key)
    if not genome:
        # Unsupported organism; leave empty for manual edit
        ctx.params["genome"] = ""
        print("[hook:genome] unsupported organism; genome not set")
        return {"skipped": f"unsupported organism '{org}'; genome left empty"}

    ctx.params["genome"] = genome
    print(f"[hook:genome] genome={genome} (from organism '{org}')")
    return {"ok": True, "genome": genome}
