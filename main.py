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
    parser.add_argument(
        "--output-folder",
        type=str,
        help="Subcarpeta de output a usar (para relectura o sobrescritura manual)",
        default=None,
    )
    parser.add_argument(
        "--show-results",
        action="store_true",
        help="Muestra el archivo results.csv de una subcarpeta de output en consola",
    )
    return parser


def main() -> int:
    import shutil
    from datetime import datetime
    import csv

    parser = build_parser()
    args = parser.parse_args()

    if args.show_results:
        # Mostrar results.csv de una subcarpeta de output
        folder = args.output_folder
        if not folder:
            print("[ERROR] Debe especificar --output-folder para mostrar resultados.", file=sys.stderr)
            return 2
        out_dir = Path("output") / folder
        if not out_dir.exists() or not out_dir.is_dir():
            print(f"[ERROR] Carpeta no encontrada: {out_dir}", file=sys.stderr)
            return 2
        csv_path = out_dir / "results.csv"
        if not csv_path.exists():
            print(f"[ERROR] No existe results.csv en {out_dir}", file=sys.stderr)
            return 2
        try:
            with csv_path.open("r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)
        except Exception as exc:
            print(f"[ERROR] Error leyendo CSV: {exc}", file=sys.stderr)
            return 2
        if not rows:
            print("[WARN] CSV vacío.")
            return 0
        # Mostrar tabla con colores si rich está disponible
        try:
            from rich.console import Console
            from rich.table import Table
            console = Console()
            table = Table(show_header=True, header_style="bold magenta")
            for col in rows[0]:
                table.add_column(col)
            for row in rows[1:]:
                table.add_row(*row)
            console.print(table)
        except ImportError:
            # Fallback: imprimir como texto tabular simple
            col_widths = [max(len(str(cell)) for cell in col) for col in zip(*rows)]
            fmt = " ".join([f"{{:<{w}}}" for w in col_widths])
            for i, row in enumerate(rows):
                print(fmt.format(*row))
                if i == 0:
                    print("-" * (sum(col_widths) + len(col_widths) - 1))
        return 0

    # --- Ejecución normal (búsqueda y guardado de resultados) ---
    try:
        domains_cfg, search_cfg, _output_dir, warnings = load_bundle(
            domains_file=args.domains_file,
            config_file=args.config_file,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"[ERROR] Configuracion invalida: {exc}", file=sys.stderr)
        return 2

    # Crear subcarpeta con timestamp si no se especifica output_folder
    if args.output_folder:
        run_output_dir = Path("output") / args.output_folder
    else:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        run_output_dir = Path("output") / now
    run_output_dir.mkdir(parents=True, exist_ok=True)

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

    # Guardar copia de domains.json usada
    domains_file_path = args.domains_file or Path("domains.json")
    try:
        shutil.copy(domains_file_path, run_output_dir / "domains.json")
    except Exception as exc:
        print(f"[WARN] No se pudo copiar domains.json: {exc}")

    written_paths = write_outputs(
        results=results,
        output_config=search_cfg.output,
        output_dir=run_output_dir,
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
