from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from modules.config.loader import load_bundle
from modules.core.orchestrator import run_pipeline
from modules.reporting.formatter import render_console, sort_results, summarize_results
from modules.reporting.writer import write_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Domain Checker + Variant Generator")
    parser.add_argument(
        "--domains-file",
        type=Path,
        help="Archivo de dominios base (default: domains.json)",
    )
    parser.add_argument(
        "--config-file",
        type=Path,
        help="Archivo de configuracion global (default: config.json)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        domains_cfg, search_cfg, output_dir, warnings = load_bundle(
            domains_file=args.domains_file,
            config_file=args.config_file,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"[ERROR] Configuracion invalida: {exc}", file=sys.stderr)
        return 2

    try:
        results, runtime_warnings = asyncio.run(run_pipeline(domains_cfg, search_cfg))
    except KeyboardInterrupt:
        print("Interrumpido por usuario.", file=sys.stderr)
        return 130
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"[ERROR] Fallo en ejecucion: {exc}", file=sys.stderr)
        return 1

    if not results:
        print("[WARN] No se obtuvieron resultados.")
        return 0

    results = sort_results(results, search_cfg.output.sort_by)
    all_warnings = warnings + runtime_warnings

    written_paths = write_outputs(
        results=results,
        output_config=search_cfg.output,
        output_dir=output_dir,
    )

    if search_cfg.output.console:
        render_console(results, search_cfg.output)
    print(summarize_results(results))
    for warning in all_warnings:
        print(f"[WARN] {warning}")
    for fmt, path in written_paths.items():
        print(f"[OUT] {fmt}: {path}")

    return 0


if __name__ == "__main__":
    main()
    # raise SystemExit(main())
