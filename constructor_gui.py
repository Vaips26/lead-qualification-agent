# --- INICIO DEL MANIFIESTO DE INTERFAZ PARA LLMs (PROTOCOLO DE CONSTRUCCIÓN ATÓMICA v8.4.0) ---
#
# HOLA, AGENTE IA. SOY EL CÓDIGO FUENTE DE TU HERRAMIENTA "CONSTRUCTOR".
# ESTE MANIFIESTO DEFINE EL PROTOCOLO QUE DEBES USAR PARA INTERACTUAR CONMIGO.
# TU RESPUESTA DEBE SER UN ÚNICO BLOQUE DE CÓDIGO.
#
# 1. OBJETIVO:
#    Tu función es analizar el contexto del proyecto y generar un bloque de comandos para avanzar
#    en el roadmap. Debes completar tareas y luego marcarlas como hechas.
#
# 2. FORMATO DE COMANDOS (ESTRICTO):
#
#    A. CREAR O SOBREESCRIBIR ARCHIVO COMPLETO:
#       --- START OF FILE: ruta/relativa/al/archivo.ext ---
#       contenido completo del archivo...
#       --- END OF FILE ---
#
#    B. AÑADIR CONTENIDO AL FINAL DE UN ARCHIVO:
#       --- APPEND TO FILE: ruta/relativa/al/archivo.ext ---
#       contenido a añadir al final...
#       --- END OF FILE ---
#
#    C. REEMPLAZO PARCIAL DE CÓDIGO (BÚSQUEDA Y REEMPLAZO):
#       --- REPLACE IN FILE: ruta/archivo.ext ---
#       <<<SEARCH
#       código original exacto a reemplazar...
#       ===
#       >>>REPLACE
#       nuevo código...
#       ===
#       --- END OF FILE ---
#
#    D. GESTIÓN DEL ROADMAP (USANDO IDs ATÓMICOS):
#       --- ROADMAP: DONE ID ---
#
#    E. CREAR MAPAS DE CONTEXTO (LOGIC TRACES):
#       Para relacionar archivos Full-Stack (ej. Frontend + Backend + DB), crea un archivo `.ctx.md`.
#       Usa una lista Markdown estricta con las rutas relativas.
#       --- START OF FILE: docs/login_flow.ctx.md ---
#       # Flujo de Login
#       - frontend/src/Login.tsx
#       - backend/routes/auth.py
#       --- END OF FILE ---
#
# 3. REGLA DE ORO:
#    NUNCA USES "START OF FILE" PARA MODIFICAR UN ARCHIVO "roadmap.md".
#
# 4. PROCESAMIENTO POR LOTES (BATCH PROCESSING):
#    DEBES generar MÚLTIPLES archivos/comandos en una sola respuesta según el "Tamaño de Lote" indicado.
#
# --- FIN DEL MANIFIESTO ---

import os
import re
import sys
import shutil
import threading
import datetime
import subprocess
import platform
from pathlib import Path
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk, filedialog
import ttkbootstrap
from ttkbootstrap.constants import *
from ttkbootstrap.widgets import ToolTip, Meter

# ---------------------------------------------------------------------------
# CLASE: DependencyAnalyzer
# ---------------------------------------------------------------------------
class DependencyAnalyzer:
    PY_EXTENSIONS = {'.py'}
    JS_EXTENSIONS = {'.js', '.ts', '.jsx', '.tsx', '.mjs', '.cjs'}
    SUPPORTED_EXTENSIONS = PY_EXTENSIONS | JS_EXTENSIONS
    JS_RESOLVE_ORDER = ['.ts', '.tsx', '.js', '.jsx', '.mjs', '/index.ts', '/index.tsx', '/index.js', '/index.jsx']

    def __init__(self, base_dir: Path, ignored_dirs: set):
        self.base_dir = base_dir
        self.ignored_dirs = ignored_dirs
        self.graph: dict[str, list[str]] = {}
        self.reverse_graph: dict[str, list[str]] = {}
        self._alias_cache: dict[str, dict] = {}
        self._project_root_cache: dict[str, Path] = {}

    def analyze_project(self):
        self.graph = {}
        self.reverse_graph = {}
        self._alias_cache = {}
        self._project_root_cache = {}
        for file_path in self._iter_source_files():
            rel = self._to_rel(file_path)
            deps = self._extract_deps(file_path)
            self.graph[rel] = deps
            for dep in deps:
                self.reverse_graph.setdefault(dep, [])
                if rel not in self.reverse_graph[dep]:
                    self.reverse_graph[dep].append(rel)

    def get_all_dependencies(self, rel_path: str, visited: set = None) -> set[str]:
        if visited is None: visited = set()
        if rel_path in visited: return visited
        visited.add(rel_path)
        for dep in self.graph.get(rel_path, []):
            self.get_all_dependencies(dep, visited)
        return visited - {rel_path}

    def get_dependents(self, rel_path: str) -> list[str]:
        return self.reverse_graph.get(rel_path, [])

    def get_all_dependents(self, rel_path: str, visited: set = None) -> set[str]:
        if visited is None: visited = set()
        if rel_path in visited: return visited
        visited.add(rel_path)
        for dep in self.reverse_graph.get(rel_path, []):
            self.get_all_dependents(dep, visited)
        return visited - {rel_path}

    def summary(self, rel_path: str) -> dict:
        return {
            'direct_deps': sorted(self.graph.get(rel_path, [])),
            'all_deps': sorted(self.get_all_dependencies(rel_path)),
            'direct_dep_by': sorted(self.get_dependents(rel_path)),
            'all_dep_by': sorted(self.get_all_dependents(rel_path)),
        }

    def _iter_source_files(self):
        for root, dirs, files in os.walk(self.base_dir):
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]
            for fname in files:
                p = Path(root) / fname
                if p.suffix in self.SUPPORTED_EXTENSIONS: yield p

    def _to_rel(self, path: Path) -> str:
        return str(path.relative_to(self.base_dir)).replace(os.sep, '/')

    def _find_project_root(self, file_path: Path) -> Path:
        cache_key = str(file_path.parent)
        if cache_key in self._project_root_cache: return self._project_root_cache[cache_key]
        current = file_path.parent
        found = self.base_dir
        ancestors = []
        while True:
            ancestors.append(current)
            for marker in ('tsconfig.json', 'jsconfig.json', 'package.json'):
                if (current / marker).exists():
                    found = current
                    break
            else:
                if current == self.base_dir or current == current.parent: break
                current = current.parent
                continue
            break
        for anc in ancestors: self._project_root_cache[str(anc)] = found
        return found

    def _get_alias_map(self, project_root: Path) -> dict[str, Path]:
        cache_key = str(project_root)
        if cache_key in self._alias_cache: return self._alias_cache[cache_key]
        alias_map: dict[str, Path] = {}
        for config_name in ('tsconfig.json', 'jsconfig.json'):
            config_path = project_root / config_name
            if not config_path.exists(): continue
            try:
                import json
                text = config_path.read_text(encoding='utf-8', errors='ignore')
                text = re.sub(r'//[^\n]*', '', text)
                text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
                text = re.sub(r',\s*([}\]])', r'\1', text)
                config = json.loads(text)
                compiler_opts = config.get('compilerOptions', {})
                base_url = compiler_opts.get('baseUrl', '.')
                paths = compiler_opts.get('paths', {})
                base_abs = (project_root / base_url).resolve()
                for alias_pattern, targets in paths.items():
                    if not targets: continue
                    alias_prefix = alias_pattern.rstrip('/*').rstrip('/')
                    if not alias_prefix: continue
                    target = targets[0].rstrip('/*').rstrip('/')
                    resolved = (base_abs / target).resolve()
                    alias_map[alias_prefix] = resolved
                break
            except Exception: pass
        if '@' not in alias_map:
            for candidate in [project_root / 'src', project_root]:
                if candidate.is_dir():
                    alias_map['@'] = candidate
                    break
        if '~' not in alias_map and '@' in alias_map: alias_map['~'] = alias_map['@']
        self._alias_cache[cache_key] = alias_map
        return alias_map

    def _extract_deps(self, file_path: Path) -> list[str]:
        try: text = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception: return []
        if file_path.suffix in self.PY_EXTENSIONS: return self._resolve_python(file_path, self._parse_python_imports(text))
        else: return self._resolve_js(file_path, self._parse_js_imports(text))

    def _parse_python_imports(self, text: str) -> list[tuple[str, int]]:
        results = []
        for m in re.finditer(r'^\s*from\s+(\.+)?([\w.]+)?\s+import', text, re.MULTILINE):
            level = len(m.group(1)) if m.group(1) else 0
            module = m.group(2) or ''
            results.append((module, level))
        for m in re.finditer(r'^\s*import\s+([\w., ]+)', text, re.MULTILINE):
            for mod in m.group(1).split(','):
                mod = mod.strip().split(' ')[0]
                if mod: results.append((mod, 0))
        return results

    def _resolve_python(self, file_path: Path, imports: list) -> list[str]:
        resolved = []
        for module, level in imports:
            if level > 0:
                anchor = file_path.parent
                for _ in range(level - 1): anchor = anchor.parent
                parts = module.split('.') if module else []
                candidate = anchor.joinpath(*parts) if parts else anchor
            else:
                parts = module.split('.')
                candidate = self.base_dir.joinpath(*parts)
            for suffix in ['.py', '/__init__.py']:
                test = Path(str(candidate) + suffix) if suffix == '.py' else candidate / '__init__.py'
                if test.exists() and test.is_file():
                    rel = self._to_rel(test)
                    if rel not in resolved: resolved.append(rel)
                    break
        return resolved

    def _parse_js_imports(self, text: str) -> list[str]:
        results = []
        patterns = [
            r'''import\s+(?:type\s+)?(?:[\w*{},\s]+\s+from\s+)?['"]([^'"]+)['"]''',
            r'''export\s+(?:type\s+)?(?:[\w*{},\s]+\s+from\s+)?['"]([^'"]+)['"]''',
            r'''require\s*\(\s*['"]([^'"]+)['"]\s*\)''',
            r'''import\s*\(\s*['"]([^'"]+)['"]\s*\)''',
        ]
        seen = set()
        for pat in patterns:
            for m in re.finditer(pat, text):
                spec = m.group(1)
                if spec in seen: continue
                seen.add(spec)
                if spec.startswith('.') or spec.startswith('/'): results.append(spec)
                elif spec.startswith('@') and '/' in spec:
                    excluded_scopes = {'@types/', '@babel/', '@emotion/', '@mui/', '@radix-ui/', '@tanstack/', '@testing-library/', '@vitejs/'}
                    if not any(spec.startswith(ex) for ex in excluded_scopes): results.append(spec)
                elif spec.startswith('~/'): results.append(spec)
        return results

    def _resolve_js(self, file_path: Path, specifiers: list) -> list[str]:
        resolved = []
        project_root = self._find_project_root(file_path)
        alias_map = self._get_alias_map(project_root)
        for spec in specifiers:
            found_path = None
            if spec.startswith('.') or spec.startswith('/'):
                if spec.startswith('/'):
                    base = project_root
                    spec_clean = spec.lstrip('/')
                else:
                    base = file_path.parent
                    spec_clean = spec
                found_path = self._try_resolve_js_path(base / spec_clean)
            else:
                matched_alias = None
                matched_len = -1
                for alias_prefix, alias_target in alias_map.items():
                    if spec == alias_prefix or spec.startswith(alias_prefix + '/'):
                        if len(alias_prefix) > matched_len:
                            matched_alias = alias_prefix
                            matched_len = len(alias_prefix)
                if matched_alias is not None:
                    alias_target = alias_map[matched_alias]
                    remainder = spec[len(matched_alias):].lstrip('/')
                    candidate = alias_target / remainder if remainder else alias_target
                    found_path = self._try_resolve_js_path(candidate)
                    if not found_path and remainder:
                        found_path = self._try_resolve_js_path(project_root / remainder)
            if found_path:
                try:
                    found_path.relative_to(self.base_dir)
                    rel = self._to_rel(found_path)
                    if rel not in resolved: resolved.append(rel)
                except ValueError: pass
        return resolved

    def _try_resolve_js_path(self, candidate: Path) -> Path | None:
        if candidate.suffix in self.JS_EXTENSIONS and candidate.exists() and candidate.is_file(): return candidate
        base_str = str(candidate)
        for ext in self.JS_RESOLVE_ORDER:
            if ext.startswith('/'): test = candidate / ext.lstrip('/')
            else: test = Path(base_str + ext)
            if test.exists() and test.is_file(): return test
        return None


# ---------------------------------------------------------------------------
# CLASES DE GESTIÓN
# ---------------------------------------------------------------------------
class HistoryManager:
    def __init__(self):
        self.stack = []       # Snapshots undoables (cambios de archivos)
        self.report_log = []  # Eventos de reporte (no undoables)

    def create_snapshot(self, files_to_modify, base_dir, description="Modificación"):
        snapshot = {
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
            "description": description,
            "event_type": "change",
            "backups": {}
        }
        for file_rel_path in files_to_modify:
            full_path = base_dir / file_rel_path
            if full_path.exists() and full_path.is_file():
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        snapshot["backups"][file_rel_path] = f.read()
                except: snapshot["backups"][file_rel_path] = None
            else: snapshot["backups"][file_rel_path] = None
        self.stack.append(snapshot)

    def record_report(self, file_count: int, fname: str, options_str: str):
        """Registra un evento de generación de reporte en el timeline."""
        self.report_log.append({
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
            "description": f"{fname}  ({file_count} archivos)",
            "event_type": "report",
            "file_count": file_count,
            "fname": fname,
            "options": options_str,
            "backups": {}
        })

    def pop_snapshot(self): return self.stack.pop() if self.stack else None
    def get_history(self): return self.stack

    def get_all_events(self) -> list:
        """Retorna todos los eventos (cambios + reportes) en orden cronológico."""
        all_events = list(self.stack) + list(self.report_log)
        return sorted(all_events, key=lambda e: e["timestamp"])


class RoadmapParser:
    def parse(self, file_path):
        if not file_path.exists(): return None
        try:
            with open(file_path, 'r', encoding='utf-8') as f: lines = f.readlines()
        except Exception: return None
        roadmap = {"title": "Proyecto Sin Título", "phases": []}
        current_phase = None
        task_id_pattern = re.compile(r'^\s*-\s\[([ x])\]\s+(?:\[(\d+)\]|(\d+):)?\s*(.*)')
        for line in lines:
            line_strip = line.strip()
            if line_strip.startswith("# "): roadmap["title"] = line_strip.replace("# ", "").strip()
            elif line_strip.startswith("## "):
                if current_phase: roadmap["phases"].append(current_phase)
                current_phase = {"name": line_strip.replace("## ", "").strip(), "tasks": [], "total": 0, "done": 0}
            else:
                match = task_id_pattern.match(line_strip)
                if match and current_phase is not None:
                    is_done = match.group(1) == 'x'
                    task_id = match.group(2) or match.group(3)
                    task_text = match.group(4).strip()
                    if not task_id:
                        text_match = re.match(r'(?:\[(\d+)\]|(\d+):)\s*(.*)', task_text)
                        if text_match:
                            task_id = text_match.group(1) or text_match.group(2)
                            task_text = text_match.group(3).strip()
                    current_phase["tasks"].append({"id": task_id, "text": task_text, "done": is_done})
                    current_phase["total"] += 1
                    if is_done: current_phase["done"] += 1
        if current_phase: roadmap["phases"].append(current_phase)
        return roadmap

    def assign_ids_if_missing(self, file_path):
        if not file_path.exists(): return False
        try:
            with open(file_path, 'r', encoding='utf-8') as f: lines = f.readlines()
        except Exception: return False
        needs_rewrite = False
        task_pattern = re.compile(r'^\s*-\s\[([ x])\](.*)')
        id_pattern = re.compile(r'^\s*-\s\[[ x]\]\s+(?:\[\d+\]|\d+:)')
        for line in lines:
            if task_pattern.match(line.strip()) and not id_pattern.match(line.strip()):
                needs_rewrite = True; break
        if not needs_rewrite: return True
        current_id = 1; new_lines = []
        for line in lines:
            match = task_pattern.match(line.strip())
            if match and not id_pattern.match(line.strip()):
                status, text = match.groups()
                new_lines.append(f"- [{status}] {current_id:03d}:{text.strip()}\n")
                current_id += 1
            else: new_lines.append(line)
        try:
            with open(file_path, 'w', encoding='utf-8') as f: f.writelines(new_lines)
            return True
        except Exception: return False


# ---------------------------------------------------------------------------
# CLASE WORKSPACE (UN PROYECTO INDIVIDUAL)
# ---------------------------------------------------------------------------
class ProjectWorkspace(ttk.Frame):
    def __init__(self, parent, base_dir):
        super().__init__(parent)
        self.base_dir = Path(base_dir).resolve()
        self.dry_run_var = tk.BooleanVar()
        self.history_manager = HistoryManager()
        self.roadmap_parser = RoadmapParser()
        self.current_roadmap_data = None
        self.current_roadmap_path = None

        self.dep_analyzer = DependencyAnalyzer(
            self.base_dir,
            ignored_dirs={'.git', 'node_modules', '__pycache__', '.venv', 'venv', '.next', 'build', 'dist'}
        )
        self._dep_ready = False
        self._selected_file_for_deps = None
        self._dep_basket: list = []

        self.setup_report_generator_config()
        self._create_widgets()
        self._configure_styles()
        self._configure_console_tags()
        self.start_scan_thread()

    def _create_widgets(self):
        main_container = ttk.Frame(self)
        main_container.pack(fill=BOTH, expand=True)
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=BOTH, expand=True, padx=10, pady=(10, 0))

        constructor_frame = ttk.Frame(self.notebook)
        self.notebook.add(constructor_frame, text="⚙ Constructor")
        self._create_constructor_tab(constructor_frame)

        # PESTAÑA UNIFICADA DE REPORTE
        report_frame = ttk.Frame(self.notebook)
        self.notebook.add(report_frame, text="📄 Reporte")
        self._create_report_tab(report_frame)

        deps_frame = ttk.Frame(self.notebook)
        self.notebook.add(deps_frame, text="🔗 Dependencias")
        self._create_deps_tab(deps_frame)

        contexts_frame = ttk.Frame(self.notebook)
        self.notebook.add(contexts_frame, text="🧠 Contextos")
        self._create_contexts_tab(contexts_frame)

        timeline_frame = ttk.Frame(self.notebook)
        self.notebook.add(timeline_frame, text="⏳ Línea de Tiempo / Roadmap")
        self._create_timeline_tab(timeline_frame)

        docker_frame = ttk.Frame(self.notebook)
        self.notebook.add(docker_frame, text="🐳 Docker Logs")
        self._create_docker_tab(docker_frame)

        self._create_status_bar(main_container)

    def _create_status_bar(self, parent):
        status_frame = ttk.Frame(parent, bootstyle="dark")
        status_frame.pack(fill=X, side=BOTTOM, ipady=5)
        ttk.Separator(parent, orient=HORIZONTAL).pack(fill=X, side=BOTTOM)

        self.global_project_label = ttk.Label(status_frame, text="Sin Roadmap Cargado", font=("Consolas", 9, "bold"), bootstyle="inverse-dark")
        self.global_project_label.pack(side=LEFT, padx=15)
        self.global_progress = ttk.Progressbar(status_frame, value=0, maximum=100, bootstyle="success-striped", length=200)
        self.global_progress.pack(side=LEFT, padx=10)

        ttk.Button(status_frame, text="📋 Copiar Contexto Roadmap", command=self.copy_roadmap_context, bootstyle="info-outline", width=25).pack(side=LEFT, padx=5)

        ttk.Label(status_frame, text="📦 Lote:", font=("Consolas", 9), bootstyle="inverse-dark").pack(side=LEFT, padx=(10, 2))
        self.batch_size_var = tk.IntVar(value=5)
        self.batch_spinbox = ttk.Spinbox(status_frame, from_=1, to=50, textvariable=self.batch_size_var, width=3, font=("Consolas", 10, "bold"))
        self.batch_spinbox.pack(side=LEFT, padx=2)
        ToolTip(self.batch_spinbox, text="Cantidad de archivos/tareas que el LLM debe generar por respuesta")

        self.global_percent_label = ttk.Label(status_frame, text="0%", font=("Consolas", 9), bootstyle="inverse-dark")
        self.global_percent_label.pack(side=LEFT, padx=5)

        ttk.Button(status_frame, text="🗺 Copiar Mapa (Todo)", command=self.copy_project_map, bootstyle="secondary-outline", width=20).pack(side=RIGHT, padx=5)
        ttk.Button(status_frame, text="🤖 Prompt LLM", command=self.copy_llm_context, bootstyle="warning", width=15).pack(side=RIGHT, padx=5)
        self.global_status_msg = ttk.Label(status_frame, text=f"Ruta: {self.base_dir}", font=("Helvetica", 9), bootstyle="inverse-dark")
        self.global_status_msg.pack(side=RIGHT, padx=15)

    # ---------------------------------------------------------------
    # TAB: CONSTRUCTOR
    # ---------------------------------------------------------------
    def _create_constructor_tab(self, parent_frame):
        main_frame = ttk.Frame(parent_frame, padding="15"); main_frame.pack(fill=BOTH, expand=True)
        info_frame = ttk.Labelframe(main_frame, text="Información del Proyecto", padding="15"); info_frame.pack(fill=X, pady=(0, 15))
        ttk.Label(info_frame, text="Raíz:", bootstyle="secondary").pack(side=LEFT, padx=(0, 10))
        ttk.Label(info_frame, text=str(self.base_dir), bootstyle="primary", font=("Helvetica", 10, "bold")).pack(side=LEFT)
        ttk.Button(info_frame, text="📋 Copiar Ruta", command=self.copy_path_to_clipboard, bootstyle="info-outline", width=15).pack(side=LEFT, padx=10)
        ttk.Button(info_frame, text="📂 Abrir en Explorer", command=self.open_in_explorer, bootstyle="warning-outline").pack(side=LEFT, padx=5)
        paned = ttk.Panedwindow(main_frame, orient=HORIZONTAL); paned.pack(fill=BOTH, expand=True, pady=(0, 15))
        input_frame = ttk.Labelframe(paned, text="📝 Entrada (Pegar respuesta LLM)", padding="10"); paned.add(input_frame, weight=1)
        self.input_text = scrolledtext.ScrolledText(input_frame, wrap=tk.WORD, width=40, height=20, font=("Consolas", 10)); self.input_text.pack(fill=BOTH, expand=True)
        output_container_frame = ttk.Labelframe(paned, text="📊 Estado y Consola", padding="0"); paned.add(output_container_frame, weight=1)
        output_split = ttk.Frame(output_container_frame); output_split.pack(fill=BOTH, expand=True)
        self.output_console = scrolledtext.ScrolledText(output_split, wrap=tk.WORD, width=40, height=20, state="disabled", font=("Consolas", 10)); self.output_console.pack(side=LEFT, fill=BOTH, expand=True, padx=(5, 0), pady=5)
        mini_map_frame = ttk.Frame(output_split, width=220); mini_map_frame.pack(side=RIGHT, fill=Y, padx=0, pady=0); mini_map_frame.pack_propagate(False)
        ttk.Label(mini_map_frame, text="📍 Roadmap", font=("Consolas", 9, "bold"), anchor="center", bootstyle="inverse-secondary").pack(fill=X)
        self.mini_map_canvas = tk.Canvas(mini_map_frame, bg="#252526", highlightthickness=0)
        mm_vsb = ttk.Scrollbar(mini_map_frame, orient="vertical", command=self.mini_map_canvas.yview); self.mini_map_canvas.configure(yscrollcommand=mm_vsb.set)
        mm_vsb.pack(side=RIGHT, fill=Y); self.mini_map_canvas.pack(side=LEFT, fill=BOTH, expand=True)

        controls_frame = ttk.Frame(main_frame); controls_frame.pack(fill=X)
        self.apply_button = ttk.Button(controls_frame, text="✓ Aplicar Cambios", command=self.run_apply_structure, bootstyle="success", width=20); self.apply_button.pack(side=LEFT, padx=(0, 10))
        self.undo_button = ttk.Button(controls_frame, text="↶ Deshacer Último", command=self.undo_last_action, bootstyle="warning-outline", state="disabled"); self.undo_button.pack(side=LEFT, padx=(0, 10))
        self.fix_prompt_button = ttk.Button(controls_frame, text="🚑 Reportar Error al LLM", command=self.generate_fix_prompt, bootstyle="danger-outline"); self.fix_prompt_button.pack(side=LEFT, padx=(0, 10))
        ToolTip(self.fix_prompt_button, text="Genera un prompt con el 'Antes y Después' del código roto para que el LLM lo arregle.")
        self.clear_button = ttk.Button(controls_frame, text="🗑 Limpiar", command=self.clear_input, bootstyle="secondary-outline"); self.clear_button.pack(side=LEFT, padx=(0, 20))
        self.dry_run_check = ttk.Checkbutton(controls_frame, text="Modo Simulación", variable=self.dry_run_var, bootstyle="info-round-toggle"); self.dry_run_check.pack(side=RIGHT)

    # ---------------------------------------------------------------
    # TAB: REPORTE UNIFICADO
    # ---------------------------------------------------------------
    def _create_report_tab(self, parent_frame):
        """Página única de reporte con tres fuentes de archivos y opciones configurables."""
        main_frame = ttk.Frame(parent_frame, padding="10")
        main_frame.pack(fill=BOTH, expand=True)

        paned = ttk.Panedwindow(main_frame, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True)

        # ── Panel izquierdo: fuentes de archivos ──────────────────────────
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=3)

        source_nb = ttk.Notebook(left_frame)
        source_nb.pack(fill=BOTH, expand=True)

        tree_tab = ttk.Frame(source_nb, padding="5")
        source_nb.add(tree_tab, text="🌲 Árbol")
        self._create_report_tree_subtab(tree_tab)

        ctx_tab = ttk.Frame(source_nb, padding="5")
        source_nb.add(ctx_tab, text="🧠 Contextos .ctx.md")
        self._create_report_contexts_subtab(ctx_tab)

        list_tab = ttk.Frame(source_nb, padding="5")
        source_nb.add(list_tab, text="📝 Lista Manual")
        self._create_report_list_subtab(list_tab)

        # Actualizar preview al cambiar de pestaña fuente
        source_nb.bind("<<NotebookTabChanged>>", lambda e: self._refresh_report_preview())

        # ── Panel derecho: config + preview ──────────────────────────────
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)
        self._create_report_config_panel(right_frame)

    def _create_report_tree_subtab(self, parent):
        """Sub-pestaña: árbol de archivos del proyecto."""
        btn_row = ttk.Frame(parent)
        btn_row.pack(fill=X, pady=(0, 6))
        ttk.Button(btn_row, text="🔍 Escanear", command=self.start_scan_thread, bootstyle="primary-outline").pack(side=LEFT)
        ttk.Button(btn_row, text="🔗 Seleccionar con Deps", command=self._select_deps_for_selected_tree_item, bootstyle="warning-outline").pack(side=LEFT, padx=5)

        self.reporter_status_label = ttk.Label(btn_row, text="● Listo", bootstyle="secondary")
        self.reporter_status_label.pack(side=RIGHT)

        self.tree = ttk.Treeview(parent, columns=("path", "inc", "size"), displaycolumns=("inc", "size"))
        self.tree.heading("#0", text="Archivo"); self.tree.column("#0", width=200)
        self.tree.heading("inc", text="Inc"); self.tree.column("inc", width=40)
        self.tree.heading("size", text="Size"); self.tree.column("size", width=60)
        self.tree.pack(fill=BOTH, expand=True, pady=5)
        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_selection_change)

        foot = ttk.Frame(parent)
        foot.pack(fill=X)
        self.total_chars_label = ttk.Label(foot, text="0 bytes sel.", bootstyle="secondary")
        self.total_chars_label.pack(side=LEFT)

    def _create_report_contexts_subtab(self, parent):
        """Sub-pestaña: selección de archivos .ctx.md."""
        ctrl = ttk.Frame(parent)
        ctrl.pack(fill=X, pady=(0, 6))
        ttk.Button(ctrl, text="🔄 Buscar .ctx.md", command=self._refresh_report_ctx_list, bootstyle="info-outline").pack(side=LEFT)
        self.report_ctx_include_deps_var = tk.BooleanVar(value=False)
        self.report_ctx_include_deps_var.trace_add("write", lambda *a: self._refresh_report_preview())
        ttk.Checkbutton(ctrl, text="Incluir dependencias directas", variable=self.report_ctx_include_deps_var, bootstyle="warning-round-toggle").pack(side=RIGHT)

        self.report_ctx_listbox = tk.Listbox(parent, font=("Consolas", 10), bg="#1e1e1e", fg="#d4d4d4",
                                             selectbackground="#264f78", selectmode=tk.MULTIPLE, activestyle="none")
        ctx_vsb = ttk.Scrollbar(parent, orient="vertical", command=self.report_ctx_listbox.yview)
        self.report_ctx_listbox.configure(yscrollcommand=ctx_vsb.set)
        ctx_vsb.pack(side=RIGHT, fill=Y)
        self.report_ctx_listbox.pack(fill=BOTH, expand=True)
        self.report_ctx_listbox.bind("<<ListboxSelect>>", lambda e: self._refresh_report_preview())

        self._refresh_report_ctx_list()

    def _create_report_list_subtab(self, parent):
        """Sub-pestaña: lista manual de rutas."""
        ttk.Label(parent, text="Una ruta relativa por línea:", font=("Helvetica", 9, "italic"), bootstyle="secondary").pack(anchor="w", pady=(0, 4))
        self.report_list_text = scrolledtext.ScrolledText(parent, height=10, font=("Consolas", 10))
        self.report_list_text.pack(fill=BOTH, expand=True)
        self.report_list_text.bind("<KeyRelease>", lambda e: self._refresh_report_preview())

    def _create_report_config_panel(self, parent):
        """Panel derecho: preview de archivos + opciones + botones de acción."""
        # Preview
        preview_frame = ttk.Labelframe(parent, text="📋 Archivos para el Reporte", padding="8")
        preview_frame.pack(fill=BOTH, expand=True, pady=(0, 8))

        self.report_preview_listbox = tk.Listbox(preview_frame, font=("Consolas", 9),
                                                  bg="#1e1e2e", fg="#cdd6f4",
                                                  selectbackground="#45475a", activestyle="none")
        prev_vsb = ttk.Scrollbar(preview_frame, orient="vertical", command=self.report_preview_listbox.yview)
        self.report_preview_listbox.configure(yscrollcommand=prev_vsb.set)
        prev_vsb.pack(side=RIGHT, fill=Y)
        self.report_preview_listbox.pack(fill=BOTH, expand=True)

        self.report_preview_count = ttk.Label(preview_frame, text="0 archivos", font=("Consolas", 9, "bold"), bootstyle="secondary")
        self.report_preview_count.pack(anchor="e", pady=(4, 0))

        # Opciones
        opts_frame = ttk.Labelframe(parent, text="⚙ Opciones del Reporte", padding="10")
        opts_frame.pack(fill=X, pady=(0, 8))

        self.report_opt_full_map   = tk.BooleanVar(value=True)
        self.report_opt_sel_map    = tk.BooleanVar(value=False)
        self.report_opt_dep_graph  = tk.BooleanVar(value=True)
        self.report_opt_trans_deps = tk.BooleanVar(value=False)

        ttk.Checkbutton(opts_frame, text="Incluir mapa completo del proyecto",
                        variable=self.report_opt_full_map, bootstyle="info-round-toggle").pack(anchor="w", pady=2)
        ttk.Checkbutton(opts_frame, text="Incluir mapa solo de archivos seleccionados",
                        variable=self.report_opt_sel_map, bootstyle="secondary-round-toggle").pack(anchor="w", pady=2)
        ttk.Separator(opts_frame, orient="horizontal").pack(fill=X, pady=4)
        ttk.Checkbutton(opts_frame, text="Incluir grafo de dependencias",
                        variable=self.report_opt_dep_graph, bootstyle="info-round-toggle").pack(anchor="w", pady=2)
        ttk.Checkbutton(opts_frame, text="Expandir dependencias transitivas",
                        variable=self.report_opt_trans_deps, bootstyle="secondary-round-toggle").pack(anchor="w", pady=2)

        ttk.Separator(opts_frame, orient="horizontal").pack(fill=X, pady=6)
        fname_row = ttk.Frame(opts_frame)
        fname_row.pack(fill=X)
        ttk.Label(fname_row, text="Nombre:", font=("Helvetica", 9)).pack(side=LEFT)
        self.report_fname_var = tk.StringVar(value="reporte.txt")
        ttk.Entry(fname_row, textvariable=self.report_fname_var, width=22).pack(side=LEFT, padx=(6, 0))

        # Acciones
        actions_frame = ttk.Frame(parent)
        actions_frame.pack(fill=X)
        ttk.Button(actions_frame, text="💾 Generar Archivo", command=self._generate_unified_report,
                   bootstyle="success", width=20).pack(fill=X, pady=(0, 4))
        ttk.Button(actions_frame, text="📋 Copiar al Portapapeles", command=self._copy_unified_report,
                   bootstyle="info-outline").pack(fill=X, pady=(0, 4))
        ttk.Button(actions_frame, text="🗺 Copiar Mapa de Selección", command=self._copy_selection_map,
                   bootstyle="secondary-outline").pack(fill=X)

    # ── Lógica del Reporte Unificado ────────────────────────────────────────

    def _refresh_report_ctx_list(self):
        """Refresca la lista de archivos .ctx.md en la sub-pestaña de contextos del reporte."""
        self.report_ctx_listbox.delete(0, tk.END)
        ctx_files = []
        for root, dirs, files in os.walk(self.base_dir):
            dirs[:] = [d for d in dirs if d not in self.directorios_a_ignorar]
            for f in files:
                if f.endswith('.ctx.md'):
                    rel_path = str(Path(root, f).relative_to(self.base_dir)).replace(os.sep, '/')
                    ctx_files.append(rel_path)
        for f in sorted(ctx_files):
            self.report_ctx_listbox.insert(tk.END, f)
        self._refresh_report_preview()

    def _get_report_files(self) -> list[str]:
        """
        Recolecta y deduplica archivos de las tres fuentes activas:
          1. Árbol (checkboxes ☑)
          2. Contextos .ctx.md seleccionados
          3. Lista manual de texto
        Retorna una lista ordenada sin repetidos.
        """
        file_set = set()

        # Fuente 1: Árbol
        def collect_tree(parent_item):
            for child in self.tree.get_children(parent_item):
                item_data = self.tree.item(child)
                if 'file' in item_data['tags'] and item_data['values'][1] == "☑":
                    file_set.add(item_data['values'][0].replace(os.sep, '/'))
                if self.tree.get_children(child):
                    collect_tree(child)
        collect_tree("")

        # Fuente 2: Contextos .ctx.md
        for idx in self.report_ctx_listbox.curselection():
            ctx_path = self.report_ctx_listbox.get(idx)
            for f in self._parse_context_file(ctx_path):
                file_set.add(f)
                if self.report_ctx_include_deps_var.get() and self._dep_ready:
                    for dep in self.dep_analyzer.graph.get(f, []):
                        file_set.add(dep)

        # Fuente 3: Lista manual
        raw = self.report_list_text.get("1.0", tk.END).strip()
        if raw:
            for line in raw.split('\n'):
                line = line.strip().strip('"\'')
                if line:
                    file_set.add(line.replace('\\', '/'))

        # Expandir dependencias transitivas si está activado
        if self.report_opt_trans_deps.get() and self._dep_ready:
            base = set(file_set)
            for f in base:
                for dep in self.dep_analyzer.get_all_dependencies(f):
                    file_set.add(dep)

        return sorted(file_set)

    def _refresh_report_preview(self):
        """Actualiza el listbox de preview del panel derecho."""
        if not hasattr(self, 'report_preview_listbox'): return
        files = self._get_report_files()
        self.report_preview_listbox.delete(0, tk.END)
        for f in files:
            self.report_preview_listbox.insert(tk.END, f"📄 {f}")
        self.report_preview_count.config(text=f"{len(files)} archivo{'s' if len(files) != 1 else ''}")

    def _build_map_text(self, files_for_sel_map: list | None = None) -> str:
        """
        Construye el texto del mapa del proyecto.
        Si files_for_sel_map es None, devuelve el mapa completo.
        Si se pasa una lista, devuelve solo el mapa de esos archivos.
        """
        structure_lines = []
        if files_for_sel_map is not None:
            # Mapa parcial: solo rutas seleccionadas
            sel_set = set(files_for_sel_map)
            def _is_relevant(path_str):
                return any(f.startswith(path_str + '/') or f == path_str for f in sel_set)
            def recurse_sel(current_path, indent=""):
                try:
                    for entry in sorted(os.scandir(current_path), key=lambda e: (e.is_file(), e.name.lower())):
                        rel = str(Path(entry.path).relative_to(self.base_dir)).replace(os.sep, '/')
                        if entry.is_dir():
                            if entry.name in self.directorios_a_ignorar: continue
                            if _is_relevant(rel):
                                structure_lines.append(f"{indent}📁 {entry.name}/")
                                recurse_sel(entry.path, indent + "  ")
                        else:
                            if rel in sel_set:
                                structure_lines.append(f"{indent}📄 {entry.name}")
                except Exception as e: structure_lines.append(f"{indent}⚠️ Error: {e}")
            recurse_sel(self.base_dir)
            return f"MAPA DE SELECCIÓN ({self.base_dir.name}):\n" + "\n".join(structure_lines)
        else:
            # Mapa completo
            def recurse_full(current_path, indent=""):
                try:
                    for entry in sorted(os.scandir(current_path), key=lambda e: (e.is_file(), e.name.lower())):
                        if entry.is_dir():
                            if entry.name in self.directorios_a_ignorar: continue
                            structure_lines.append(f"{indent}📁 {entry.name}/")
                            recurse_full(entry.path, indent + "  ")
                        else:
                            if entry.name in self.archivos_a_ignorar_por_nombre or entry.path == self.script_path_abs: continue
                            structure_lines.append(f"{indent}📄 {entry.name}")
                except Exception as e: structure_lines.append(f"{indent}⚠️ Error: {e}")
            recurse_full(self.base_dir)
            return f"MAPA COMPLETO DEL PROYECTO ({self.base_dir.name}):\n" + "\n".join(structure_lines)

    def _gen_report(self, files: list[str], fname: str,
                    include_full_map: bool = True,
                    include_sel_map: bool = False,
                    include_dep_graph: bool = True) -> str:
        """
        Genera el contenido del reporte y lo escribe a disco.
        Retorna el contenido como string (para copiar al portapapeles).
        Registra el evento en el timeline.
        """
        content_parts = []

        # Mapa completo (opcional)
        if include_full_map:
            content_parts.append(self._build_map_text(files_for_sel_map=None))

        # Mapa de selección (opcional, no duplicar si ya hay mapa completo)
        if include_sel_map and not include_full_map:
            content_parts.append(self._build_map_text(files_for_sel_map=files))

        # Grafo de dependencias (opcional)
        if include_dep_graph and self._dep_ready and files:
            dep_lines = ["\n\nGRAFO DE DEPENDENCIAS (archivos incluidos):"]
            for f in files:
                rel = f.replace(os.sep, '/')
                deps = self.dep_analyzer.graph.get(rel, [])
                usedby = self.dep_analyzer.reverse_graph.get(rel, [])
                dep_lines.append(f"  {rel}")
                if deps: dep_lines.append(f"    ↓ importa: {', '.join(deps)}")
                if usedby: dep_lines.append(f"    ↑ usado por: {', '.join(usedby)}")
            content_parts.append("\n".join(dep_lines))

        # Nota para el LLM
        instruction_text = (
            "\n\n**NOTA PARA EL LLM: Se proporciona el mapa completo para darte contexto. "
            "Si necesitas ver un archivo no incluido en este reporte, solicítalo al usuario. "
            "No intentes reescribir lógica sin ver los archivos relevantes.**"
        )
        content_parts.append(instruction_text)

        # Contenido de archivos
        for f in files:
            path = self.base_dir / f
            if path.exists():
                content_parts.append(f"\n--- FILE CONTENT: {f} ---\n")
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
                        content_parts.append(fp.read())
                except Exception as e:
                    content_parts.append(f"[Error: {e}]")
                content_parts.append("\n--- END OF CONTENT ---")

        full_content = "\n".join(content_parts)

        # Escribir a disco
        report_path = self.base_dir / fname
        with open(report_path, 'w', encoding='utf-8') as out:
            out.write(full_content)

        # Registrar en el timeline
        opts_used = []
        if include_full_map: opts_used.append("mapa completo")
        if include_sel_map: opts_used.append("mapa selección")
        if include_dep_graph: opts_used.append("grafo deps")
        self.history_manager.record_report(len(files), fname, ", ".join(opts_used) or "sin mapa")
        self.update_timeline_visuals()

        dep_status = '✅ incluido' if (include_dep_graph and self._dep_ready) else '⚠ no disponible'
        messagebox.showinfo("Reporte Generado",
                            f"Creado: {report_path}\n"
                            f"Archivos incluidos: {len(files)}\n"
                            f"Mapa: {'completo' if include_full_map else ('selección' if include_sel_map else 'ninguno')}\n"
                            f"Dependencias: {dep_status}")
        return full_content

    def _generate_unified_report(self):
        """Genera el reporte a archivo usando la configuración del panel derecho."""
        files = self._get_report_files()
        if not files:
            messagebox.showwarning("Sin archivos", "No hay archivos seleccionados en ninguna fuente.")
            return
        fname = self.report_fname_var.get().strip() or "reporte.txt"
        self._gen_report(
            files, fname,
            include_full_map=self.report_opt_full_map.get(),
            include_sel_map=self.report_opt_sel_map.get(),
            include_dep_graph=self.report_opt_dep_graph.get()
        )

    def _copy_unified_report(self):
        """Genera el reporte y lo copia al portapapeles."""
        files = self._get_report_files()
        if not files:
            messagebox.showwarning("Sin archivos", "No hay archivos seleccionados en ninguna fuente.")
            return
        fname = self.report_fname_var.get().strip() or "reporte.txt"
        content = self._gen_report(
            files, fname,
            include_full_map=self.report_opt_full_map.get(),
            include_sel_map=self.report_opt_sel_map.get(),
            include_dep_graph=self.report_opt_dep_graph.get()
        )
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo("Copiado", "El reporte también ha sido copiado al portapapeles.")

    def _copy_selection_map(self):
        """Copia al portapapeles el mapa solo de los archivos seleccionados."""
        files = self._get_report_files()
        if not files:
            messagebox.showwarning("Sin archivos", "No hay archivos seleccionados.")
            return
        map_text = self._build_map_text(files_for_sel_map=files)
        self.clipboard_clear()
        self.clipboard_append(map_text)
        messagebox.showinfo("Mapa Copiado", f"Mapa de {len(files)} archivos copiado al portapapeles.")

    # ── Compatibilidad: cesta de dependencias redirige al reporte unificado ─
    def _gen_report_from_basket(self):
        """Añade los archivos de la cesta al reporte unificado y cambia a esa pestaña."""
        if not self._dep_basket:
            messagebox.showwarning("Contexto vacío", "Añade archivos al contexto primero.")
            return
        # Añadir a la lista manual del reporte unificado
        current = self.report_list_text.get("1.0", tk.END).strip()
        existing = set(l.strip() for l in current.split('\n') if l.strip())
        new_files = [e["file"] for e in self._dep_basket if e["file"] not in existing]
        if new_files:
            if current:
                self.report_list_text.insert(tk.END, "\n" + "\n".join(new_files))
            else:
                self.report_list_text.insert("1.0", "\n".join(new_files))
        self._refresh_report_preview()
        # Cambiar a la pestaña de Reporte
        for i in range(self.notebook.index("end")):
            if "Reporte" in self.notebook.tab(i, "text"):
                self.notebook.select(i)
                break
        messagebox.showinfo("Añadido al Reporte", f"{len(new_files)} archivo(s) añadidos a la Lista Manual del Reporte Unificado.")

    # ---------------------------------------------------------------
    # TAB: CONTEXTOS (Logic Traces) — exploración y edición
    # ---------------------------------------------------------------
    def _create_contexts_tab(self, parent_frame):
        """Pestaña de exploración y gestión de archivos .ctx.md."""
        main_frame = ttk.Frame(parent_frame, padding="10")
        main_frame.pack(fill=BOTH, expand=True)

        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.pack(fill=X, pady=(0, 10))
        ttk.Button(ctrl_frame, text="🔄 Buscar Archivos .ctx.md", command=self._refresh_contexts_list, bootstyle="info-outline").pack(side=LEFT)
        ttk.Button(ctrl_frame, text="📝 Crear Contexto de Ejemplo", command=self._create_sample_context, bootstyle="secondary-outline").pack(side=LEFT, padx=10)

        self.ctx_include_deps_var = tk.BooleanVar(value=False)
        self.ctx_include_deps_var.trace_add("write", lambda *a: self._on_context_select())
        ttk.Checkbutton(ctrl_frame, text="Incluir dependencias directas", variable=self.ctx_include_deps_var, bootstyle="warning-round-toggle").pack(side=RIGHT, padx=10)

        paned = ttk.Panedwindow(main_frame, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True)

        left_frame = ttk.Labelframe(paned, text="Archivos de Contexto (.ctx.md)", padding="5")
        paned.add(left_frame, weight=1)
        self.ctx_listbox = tk.Listbox(left_frame, font=("Consolas", 10), bg="#1e1e1e", fg="#d4d4d4",
                                      selectbackground="#264f78", selectmode=tk.MULTIPLE, activestyle="none")
        ctx_vsb = ttk.Scrollbar(left_frame, orient="vertical", command=self.ctx_listbox.yview)
        self.ctx_listbox.configure(yscrollcommand=ctx_vsb.set)
        ctx_vsb.pack(side=RIGHT, fill=Y); self.ctx_listbox.pack(fill=BOTH, expand=True)
        self.ctx_listbox.bind("<<ListboxSelect>>", self._on_context_select)

        right_frame = ttk.Labelframe(paned, text="Sumatoria de Archivos (Sin Repetidos)", padding="5")
        paned.add(right_frame, weight=2)

        btn_frame = ttk.Frame(right_frame)
        btn_frame.pack(fill=X, pady=(0, 5))
        ttk.Button(btn_frame, text="➕ Añadir selección al Reporte Unificado",
                   command=self._send_ctx_to_report, bootstyle="success").pack(side=LEFT)
        self.ctx_status_label = ttk.Label(btn_frame, text="Selecciona un contexto...",
                                           font=("Helvetica", 9, "italic"), bootstyle="secondary")
        self.ctx_status_label.pack(side=LEFT, padx=10)

        self.ctx_preview_listbox = tk.Listbox(right_frame, font=("Consolas", 9),
                                               bg="#1e1e2e", fg="#cdd6f4", activestyle="none")
        prev_vsb = ttk.Scrollbar(right_frame, orient="vertical", command=self.ctx_preview_listbox.yview)
        self.ctx_preview_listbox.configure(yscrollcommand=prev_vsb.set)
        prev_vsb.pack(side=RIGHT, fill=Y); self.ctx_preview_listbox.pack(fill=BOTH, expand=True)

    def _send_ctx_to_report(self):
        """Envía los archivos del contexto seleccionado a la Lista Manual del reporte unificado."""
        selections = self.ctx_listbox.curselection()
        if not selections:
            messagebox.showwarning("Contextos", "Selecciona al menos un archivo .ctx.md")
            return
        base_files = set()
        for idx in selections:
            for f in self._parse_context_file(self.ctx_listbox.get(idx)):
                base_files.add(f)
        if self.ctx_include_deps_var.get() and self._dep_ready:
            for f in set(base_files):
                for dep in self.dep_analyzer.graph.get(f, []):
                    base_files.add(dep)

        current = self.report_list_text.get("1.0", tk.END).strip()
        existing = set(l.strip() for l in current.split('\n') if l.strip())
        new_files = sorted(base_files - existing)
        if new_files:
            if current:
                self.report_list_text.insert(tk.END, "\n" + "\n".join(new_files))
            else:
                self.report_list_text.insert("1.0", "\n".join(new_files))
        self._refresh_report_preview()
        for i in range(self.notebook.index("end")):
            if "Reporte" in self.notebook.tab(i, "text"):
                self.notebook.select(i)
                break

    def _refresh_contexts_list(self):
        self.ctx_listbox.delete(0, tk.END)
        self.ctx_preview_listbox.delete(0, tk.END)
        ctx_files = []
        for root, dirs, files in os.walk(self.base_dir):
            dirs[:] = [d for d in dirs if d not in self.directorios_a_ignorar]
            for f in files:
                if f.endswith('.ctx.md'):
                    rel_path = str(Path(root, f).relative_to(self.base_dir)).replace(os.sep, '/')
                    ctx_files.append(rel_path)
        for f in sorted(ctx_files):
            self.ctx_listbox.insert(tk.END, f)
        self.ctx_status_label.config(text=f"Encontrados {len(ctx_files)} archivos .ctx.md")

    def _parse_context_file(self, rel_path: str) -> list:
        full_path = self.base_dir / rel_path
        files = []
        if not full_path.exists(): return files
        graph_keys = list(self.dep_analyzer.graph.keys()) if self._dep_ready else []
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('- '):
                        filepath = line[2:].strip()
                        if filepath.startswith('[') and '](' in filepath:
                            filepath = filepath.split('](')[1].split(')')[0]
                        raw_path = filepath.replace('\\', '/')
                        if self._dep_ready and raw_path in self.dep_analyzer.graph:
                            files.append(raw_path); continue
                        if self._dep_ready:
                            matched = False
                            for g_key in graph_keys:
                                if g_key.endswith('/' + raw_path) or g_key == raw_path:
                                    files.append(g_key); matched = True; break
                            if matched: continue
                        ctx_dir = full_path.parent
                        c1 = (ctx_dir / raw_path).resolve()
                        c2 = (self.base_dir / raw_path).resolve()
                        if c1.exists() and c1.is_file():
                            try: files.append(str(c1.relative_to(self.base_dir)).replace(os.sep, '/'))
                            except: files.append(raw_path)
                        elif c2.exists() and c2.is_file():
                            try: files.append(str(c2.relative_to(self.base_dir)).replace(os.sep, '/'))
                            except: files.append(raw_path)
                        else: files.append(raw_path)
        except Exception: pass
        return files

    def _on_context_select(self, event=None):
        selections = self.ctx_listbox.curselection()
        self.ctx_preview_listbox.delete(0, tk.END)
        if not selections:
            self.ctx_status_label.config(text="Selecciona un contexto...")
            return
        base_files = set()
        for idx in selections:
            for f in self._parse_context_file(self.ctx_listbox.get(idx)):
                base_files.add(f)
        final_files = set(base_files)
        deps_added = 0
        if self.ctx_include_deps_var.get():
            if not self._dep_ready:
                self.ctx_status_label.config(text="⏳ Esperando análisis de dependencias...", bootstyle="warning")
            else:
                for f in base_files:
                    for d in self.dep_analyzer.graph.get(f, []):
                        if d not in final_files:
                            final_files.add(d); deps_added += 1
        for f in sorted(final_files):
            if f in base_files:
                self.ctx_preview_listbox.insert(tk.END, f"📄 {f}")
            else:
                self.ctx_preview_listbox.insert(tk.END, f"🔗 {f}")
                self.ctx_preview_listbox.itemconfig(tk.END, fg="#89d185")
        if self.ctx_include_deps_var.get() and self._dep_ready:
            self.ctx_status_label.config(text=f"{len(final_files)} archivos ({len(base_files)} base + {deps_added} deps).", bootstyle="success")
        else:
            self.ctx_status_label.config(text=f"{len(base_files)} archivos base.", bootstyle="secondary")

    def _create_sample_context(self):
        sample_path = self.base_dir / "ejemplo_flujo.ctx.md"
        if sample_path.exists():
            messagebox.showinfo("Info", "El archivo ejemplo_flujo.ctx.md ya existe.")
            return
        content = """# Contexto: Ejemplo de Flujo Full-Stack
Este archivo define una traza lógica. El Constructor leerá las rutas listadas abajo.

- ruta/a/tu/frontend/Componente.tsx
- ruta/a/tu/backend/controlador.py
- ruta/a/tu/base_de_datos/modelo.py
"""
        try:
            with open(sample_path, 'w', encoding='utf-8') as f: f.write(content)
            self._refresh_contexts_list()
            self._refresh_report_ctx_list()
            messagebox.showinfo("Éxito", "Archivo 'ejemplo_flujo.ctx.md' creado en la raíz del proyecto.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear el archivo: {e}")

    # ---------------------------------------------------------------
    # TAB: DEPENDENCIAS
    # ---------------------------------------------------------------
    def _create_deps_tab(self, parent_frame):
        main_frame = ttk.Frame(parent_frame, padding="10")
        main_frame.pack(fill=BOTH, expand=True)

        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.pack(fill=X, pady=(0, 6))
        self.dep_status_label = ttk.Label(ctrl_frame, text="⏳ Analizando dependencias...", font=("Consolas", 9), bootstyle="warning")
        self.dep_status_label.pack(side=LEFT, padx=(0, 12))
        ttk.Button(ctrl_frame, text="🔄 Re-analizar", command=self._start_dep_analysis, bootstyle="info-outline").pack(side=LEFT)
        ttk.Button(ctrl_frame, text="🗺 Mapa Complejo", command=self._copy_dep_map_complex, bootstyle="secondary-outline", width=16).pack(side=RIGHT, padx=(4, 0))
        ttk.Button(ctrl_frame, text="🗺 Mapa Simple", command=self._copy_dep_map_simple, bootstyle="secondary-outline", width=14).pack(side=RIGHT, padx=(4, 0))

        paned = ttk.Panedwindow(main_frame, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True)

        left_frame = ttk.Labelframe(paned, text="📁 Archivos del Proyecto", padding="5")
        paned.add(left_frame, weight=2)

        ss_frame = ttk.Frame(left_frame)
        ss_frame.pack(fill=X, pady=(0, 4))
        ttk.Label(ss_frame, text="🔍").pack(side=LEFT)
        self.dep_search_var = tk.StringVar()
        self.dep_search_var.trace_add("write", lambda *a: self._populate_dep_listbox(self.dep_search_var.get()))
        ttk.Entry(ss_frame, textvariable=self.dep_search_var, width=16).pack(side=LEFT, padx=(3, 6))
        ttk.Label(ss_frame, text="Orden:", font=("Helvetica", 8)).pack(side=LEFT)
        self.dep_sort_var = tk.StringVar(value="nombre")
        sort_cb = ttk.Combobox(ss_frame, textvariable=self.dep_sort_var, values=["nombre", "imports ↑", "imports ↓", "usado por ↑", "usado por ↓"], state="readonly", width=13)
        sort_cb.pack(side=LEFT, padx=(3, 0))
        sort_cb.bind("<<ComboboxSelected>>", lambda e: self._populate_dep_listbox(self.dep_search_var.get()))

        self.dep_listbox = tk.Listbox(left_frame, font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4", selectbackground="#264f78", selectforeground="#ffffff", activestyle="none")
        dep_vsb = ttk.Scrollbar(left_frame, orient="vertical", command=self.dep_listbox.yview)
        dep_hsb = ttk.Scrollbar(left_frame, orient="horizontal", command=self.dep_listbox.xview)
        self.dep_listbox.configure(yscrollcommand=dep_vsb.set, xscrollcommand=dep_hsb.set)
        dep_vsb.pack(side=RIGHT, fill=Y); dep_hsb.pack(side=BOTTOM, fill=X)
        self.dep_listbox.pack(fill=BOTH, expand=True)
        self.dep_listbox.bind("<<ListboxSelect>>", self._on_dep_listbox_select)
        self._dep_all_files: list = []

        mid_frame = ttk.Labelframe(paned, text="🔍 Detalle", padding="5")
        paned.add(mid_frame, weight=3)

        self.dep_detail_label = ttk.Label(mid_frame, text="← Selecciona un archivo", font=("Helvetica", 9, "italic"))
        self.dep_detail_label.pack(anchor="w", pady=(0, 4))
        ttk.Button(mid_frame, text="➕ Añadir cadena al contexto", command=self._add_chain_to_basket, bootstyle="primary-outline").pack(fill=X, pady=(0, 6))

        detail_paned = ttk.Panedwindow(mid_frame, orient=VERTICAL)
        detail_paned.pack(fill=BOTH, expand=True)

        imports_frame = ttk.Labelframe(detail_paned, text="⬇ Importa directamente", padding="4")
        detail_paned.add(imports_frame, weight=1)
        self.deps_direct_list = tk.Listbox(imports_frame, font=("Consolas", 8), bg="#1a2a1a", fg="#89d185", selectbackground="#264f78")
        dv = ttk.Scrollbar(imports_frame, orient="vertical", command=self.deps_direct_list.yview); self.deps_direct_list.configure(yscrollcommand=dv.set); dv.pack(side=RIGHT, fill=Y)
        self.deps_direct_list.pack(fill=BOTH, expand=True)
        self.deps_direct_list.bind("<Double-Button-1>", self._navigate_to_dep)

        trans_frame = ttk.Labelframe(detail_paned, text="⬇⬇ Cadena transitiva completa", padding="4")
        detail_paned.add(trans_frame, weight=1)
        self.deps_all_list = tk.Listbox(trans_frame, font=("Consolas", 8), bg="#1a2a1a", fg="#4ec994", selectbackground="#264f78")
        tv = ttk.Scrollbar(trans_frame, orient="vertical", command=self.deps_all_list.yview); self.deps_all_list.configure(yscrollcommand=tv.set); tv.pack(side=RIGHT, fill=Y)
        self.deps_all_list.pack(fill=BOTH, expand=True)

        usedby_frame = ttk.Labelframe(detail_paned, text="⬆ Usado por", padding="4")
        detail_paned.add(usedby_frame, weight=1)
        self.deps_usedby_list = tk.Listbox(usedby_frame, font=("Consolas", 8), bg="#2a1a1a", fg="#f48771", selectbackground="#264f78")
        uv = ttk.Scrollbar(usedby_frame, orient="vertical", command=self.deps_usedby_list.yview); self.deps_usedby_list.configure(yscrollcommand=uv.set); uv.pack(side=RIGHT, fill=Y)
        self.deps_usedby_list.pack(fill=BOTH, expand=True)
        self.deps_usedby_list.bind("<Double-Button-1>", self._navigate_to_dep)

        right_frame = ttk.Labelframe(paned, text="📦 Contexto Acumulado", padding="5")
        paned.add(right_frame, weight=2)

        basket_ctrl = ttk.Frame(right_frame)
        basket_ctrl.pack(fill=X, pady=(0, 5))
        self.basket_count_label = ttk.Label(basket_ctrl, text="0 archivos", font=("Consolas", 8), bootstyle="secondary")
        self.basket_count_label.pack(side=LEFT)
        ttk.Button(basket_ctrl, text="🗑 Limpiar", command=self._clear_basket, bootstyle="danger-outline", width=10).pack(side=RIGHT)
        ttk.Button(basket_ctrl, text="📄 → Reporte", command=self._gen_report_from_basket, bootstyle="success", width=12).pack(side=RIGHT, padx=(0, 4))
        ToolTip(basket_ctrl.winfo_children()[-1], text="Envía la cesta al Reporte Unificado")

        basket_frame = ttk.Frame(right_frame)
        basket_frame.pack(fill=BOTH, expand=True)
        self.basket_listbox = tk.Listbox(basket_frame, font=("Consolas", 8), bg="#1e1e2e", fg="#cdd6f4", selectbackground="#45475a", selectforeground="#cdd6f4", activestyle="none")
        bv = ttk.Scrollbar(basket_frame, orient="vertical", command=self.basket_listbox.yview)
        bh = ttk.Scrollbar(basket_frame, orient="horizontal", command=self.basket_listbox.xview)
        self.basket_listbox.configure(yscrollcommand=bv.set, xscrollcommand=bh.set)
        bv.pack(side=RIGHT, fill=Y); bh.pack(side=BOTTOM, fill=X)
        self.basket_listbox.pack(fill=BOTH, expand=True)
        ttk.Button(right_frame, text="✖ Quitar seleccionado", command=self._remove_from_basket, bootstyle="secondary-outline").pack(fill=X, pady=(4, 0))

    def _add_chain_to_basket(self):
        if not self._dep_ready: messagebox.showwarning("Dependencias", "Análisis no terminado."); return
        if not self._selected_file_for_deps: messagebox.showwarning("Dependencias", "Selecciona un archivo primero."); return
        root_file = self._selected_file_for_deps
        all_deps = self.dep_analyzer.get_all_dependencies(root_file)
        existing = {e["file"] for e in self._dep_basket}
        added = 0
        if root_file not in existing:
            self._dep_basket.append({"file": root_file, "reason": "raíz"}); existing.add(root_file); added += 1
        for dep in sorted(all_deps):
            if dep not in existing:
                importers = self.dep_analyzer.reverse_graph.get(dep, [])
                parent = next((f for f in importers if f == root_file or f in existing), root_file)
                short_parent = parent.split("/")[-1]
                self._dep_basket.append({"file": dep, "reason": f"dep de: {short_parent}"}); existing.add(dep); added += 1
        self._refresh_basket_ui()
        self.dep_status_label.config(text=f"➕ +{added} añadidos  ({len(self._dep_basket)} total)", bootstyle="success")

    def _refresh_basket_ui(self):
        self.basket_listbox.delete(0, tk.END)
        for i, entry in enumerate(self._dep_basket):
            fname = entry["file"].split("/")[-1]
            bg_main = "#25253a" if i % 2 == 0 else "#1e1e2e"
            bg_sub  = "#1e1e2e" if i % 2 == 0 else "#18182a"
            self.basket_listbox.insert(tk.END, f"  📄 {fname}")
            self.basket_listbox.itemconfig(tk.END, bg=bg_main, fg="#cdd6f4")
            self.basket_listbox.insert(tk.END, f"     ↳ {entry['file']}  [{entry['reason']}]")
            self.basket_listbox.itemconfig(tk.END, bg=bg_sub, fg="#7f849c")
        self.basket_count_label.config(text=f"{len(self._dep_basket)} archivos")

    def _remove_from_basket(self):
        sel = self.basket_listbox.curselection()
        if not sel: return
        entry_idx = sel[0] // 2
        if entry_idx < len(self._dep_basket):
            self._dep_basket.pop(entry_idx); self._refresh_basket_ui()

    def _clear_basket(self):
        self._dep_basket.clear(); self._refresh_basket_ui()
        self.dep_status_label.config(text="Contexto limpiado.", bootstyle="secondary")

    def _copy_dep_map_simple(self):
        from collections import defaultdict
        if not self._dep_ready: messagebox.showwarning("Dependencias", "El análisis aún no ha terminado."); return
        files = [e["file"] for e in self._dep_basket] if self._dep_basket else sorted(self.dep_analyzer.graph.keys())
        if not files: messagebox.showwarning("Dependencias", "No hay archivos para mapear."); return
        lines = [f"MAPA SIMPLE DE DEPENDENCIAS ({len(files)} archivos)", "=" * 60]
        by_dir = defaultdict(list)
        for f in files:
            parts = f.rsplit("/", 1); d = parts[0] if len(parts) > 1 else "."; by_dir[d].append(f)
        for d in sorted(by_dir.keys()):
            lines.append(f"\n📁 {d}/")
            for f in sorted(by_dir[d]):
                nd = len(self.dep_analyzer.graph.get(f, [])); nu = len(self.dep_analyzer.reverse_graph.get(f, []))
                fname = f.rsplit("/", 1)[-1]; lines.append(f"   {fname}  [{nd}↓  {nu}↑]")
        self.clipboard_clear(); self.clipboard_append("\n".join(lines))
        scope = "cesta" if self._dep_basket else "proyecto completo"
        messagebox.showinfo("Mapa Simple Copiado", f"Mapa simple copiado ({len(files)} archivos del {scope}).")

    def _copy_dep_map_complex(self):
        from collections import defaultdict
        if not self._dep_ready: messagebox.showwarning("Dependencias", "El análisis aún no ha terminado."); return
        files = [e["file"] for e in self._dep_basket] if self._dep_basket else sorted(self.dep_analyzer.graph.keys())
        if not files: messagebox.showwarning("Dependencias", "No hay archivos para mapear."); return
        files_set = set(files)
        lines = [f"MAPA COMPLEJO DE DEPENDENCIAS ({len(files)} archivos)", "=" * 60]
        by_dir = defaultdict(list)
        for f in files:
            parts = f.rsplit("/", 1); d = parts[0] if len(parts) > 1 else "."; by_dir[d].append(f)
        for d in sorted(by_dir.keys()):
            lines.append(f"\n📁 {d}/")
            for f in sorted(by_dir[d]):
                fname = f.rsplit("/", 1)[-1]; nd = len(self.dep_analyzer.graph.get(f, [])); nu = len(self.dep_analyzer.reverse_graph.get(f, []))
                lines.append(f"\n  📄 {fname}  [{nd}↓  {nu}↑]")
                deps = self.dep_analyzer.graph.get(f, [])
                if deps:
                    dep_strs = [f"{d2.rsplit('/',1)[-1]}{'' if d2 in files_set else '⚠'}" for d2 in deps]
                    lines.append(f"     ↓ importa: {', '.join(dep_strs)}")
                usedby = self.dep_analyzer.reverse_graph.get(f, [])
                if usedby:
                    used_strs = [f"{u.rsplit('/',1)[-1]}{'' if u in files_set else '⚠'}" for u in usedby]
                    lines.append(f"     ↑ usado por: {', '.join(used_strs)}")
        lines.append("\n\n⚠ = archivo fuera del contexto actual")
        self.clipboard_clear(); self.clipboard_append("\n".join(lines))
        scope = "cesta" if self._dep_basket else "proyecto completo"
        messagebox.showinfo("Mapa Complejo Copiado", f"Mapa complejo copiado ({len(files)} archivos del {scope}).")

    def _start_dep_analysis(self):
        self._dep_ready = False
        self.dep_status_label.config(text="⏳ Analizando dependencias...", bootstyle="warning")
        threading.Thread(target=self._run_dep_analysis, daemon=True).start()

    def _run_dep_analysis(self):
        self.dep_analyzer.base_dir = self.base_dir
        self.dep_analyzer.ignored_dirs = self.directorios_a_ignorar
        self.dep_analyzer.analyze_project()
        self.after(0, self._dep_analysis_done)

    def _dep_analysis_done(self):
        self._dep_ready = True
        total = len(self.dep_analyzer.graph)
        self.dep_status_label.config(text=f"✅ {total} archivos analizados", bootstyle="success")
        self._populate_dep_listbox()
        self._refresh_contexts_list()
        self._refresh_report_ctx_list()

    def _populate_dep_listbox(self, filter_text=""):
        self.dep_listbox.delete(0, tk.END)
        all_files = list(self.dep_analyzer.graph.keys())
        ft = filter_text.lower()
        if ft: all_files = [f for f in all_files if ft in f.lower()]
        sort_mode = self.dep_sort_var.get() if hasattr(self, "dep_sort_var") else "nombre"
        if sort_mode == "nombre": all_files.sort()
        elif sort_mode == "imports ↑": all_files.sort(key=lambda f: len(self.dep_analyzer.graph.get(f, [])))
        elif sort_mode == "imports ↓": all_files.sort(key=lambda f: len(self.dep_analyzer.graph.get(f, [])), reverse=True)
        elif sort_mode == "usado por ↑": all_files.sort(key=lambda f: len(self.dep_analyzer.reverse_graph.get(f, [])))
        elif sort_mode == "usado por ↓": all_files.sort(key=lambda f: len(self.dep_analyzer.reverse_graph.get(f, [])), reverse=True)
        self._dep_all_files = all_files
        for rel in all_files:
            ndeps = len(self.dep_analyzer.graph.get(rel, []))
            nused = len(self.dep_analyzer.reverse_graph.get(rel, []))
            self.dep_listbox.insert(tk.END, f"{rel}  [{ndeps}↓ {nused}↑]")

    def _on_dep_listbox_select(self, event):
        sel = self.dep_listbox.curselection()
        if not sel: return
        raw = self.dep_listbox.get(sel[0])
        rel_path = raw.split("  [")[0].strip()
        self._selected_file_for_deps = rel_path
        self._show_dep_detail(rel_path)

    def _show_dep_detail(self, rel_path: str):
        summary = self.dep_analyzer.summary(rel_path)
        short = rel_path.split("/")[-1]
        self.dep_detail_label.config(text=f"📄 {short}   ({rel_path})")
        self.deps_direct_list.delete(0, tk.END)
        for d in summary["direct_deps"]:
            nd = len(self.dep_analyzer.graph.get(d, [])); nu = len(self.dep_analyzer.reverse_graph.get(d, []))
            self.deps_direct_list.insert(tk.END, f"{d}  [{nd}↓ {nu}↑]")
        if not summary["direct_deps"]: self.deps_direct_list.insert(tk.END, "(ninguna)")
        self.deps_all_list.delete(0, tk.END)
        transitives = sorted(set(summary["all_deps"]) - set(summary["direct_deps"]))
        for d in transitives:
            nd = len(self.dep_analyzer.graph.get(d, [])); nu = len(self.dep_analyzer.reverse_graph.get(d, []))
            self.deps_all_list.insert(tk.END, f"{d}  [{nd}↓ {nu}↑]")
        if not transitives: self.deps_all_list.insert(tk.END, "(ninguna adicional)")
        self.deps_usedby_list.delete(0, tk.END)
        for d in summary["direct_dep_by"]:
            nd = len(self.dep_analyzer.graph.get(d, [])); nu = len(self.dep_analyzer.reverse_graph.get(d, []))
            self.deps_usedby_list.insert(tk.END, f"{d}  [{nd}↓ {nu}↑]")
        if not summary["direct_dep_by"]: self.deps_usedby_list.insert(tk.END, "(nadie lo importa directamente)")

    def _navigate_to_dep(self, event):
        widget = event.widget
        sel = widget.curselection()
        if not sel: return
        raw = widget.get(sel[0]).strip()
        if raw.startswith("("): return
        rel = raw.split("  [")[0].strip()
        for i in range(self.dep_listbox.size()):
            label = self.dep_listbox.get(i)
            if label.startswith(rel + "  [") or label == rel:
                self.dep_listbox.selection_clear(0, tk.END)
                self.dep_listbox.selection_set(i)
                self.dep_listbox.see(i)
                self._selected_file_for_deps = rel
                self._show_dep_detail(rel)
                break

    # ---------------------------------------------------------------
    # TAB: DOCKER
    # ---------------------------------------------------------------
    def _create_docker_tab(self, parent_frame):
        main_frame = ttk.Frame(parent_frame, padding="15"); main_frame.pack(fill=BOTH, expand=True)
        controls_frame = ttk.Labelframe(main_frame, text="Control de Contenedores", padding="10"); controls_frame.pack(fill=X, pady=(0, 10))
        ttk.Button(controls_frame, text="🔄 Refrescar Lista", command=self.refresh_docker_containers, bootstyle="info-outline").pack(side=LEFT, padx=(0, 10))
        ttk.Label(controls_frame, text="Contenedor:", bootstyle="secondary").pack(side=LEFT, padx=(0, 5))
        self.docker_combo = ttk.Combobox(controls_frame, state="readonly", width=30); self.docker_combo.pack(side=LEFT, padx=(0, 10))
        ttk.Button(controls_frame, text="📥 Obtener Logs", command=self.fetch_docker_logs, bootstyle="primary").pack(side=LEFT)
        self.docker_status_label = ttk.Label(controls_frame, text="", bootstyle="secondary"); self.docker_status_label.pack(side=LEFT, padx=10)
        paned = ttk.Panedwindow(main_frame, orient=HORIZONTAL); paned.pack(fill=BOTH, expand=True)
        left_frame = ttk.Labelframe(paned, text="📜 Log Completo (stdout/stderr)", padding="5"); paned.add(left_frame, weight=1)
        self.docker_full_log = scrolledtext.ScrolledText(left_frame, wrap=tk.NONE, font=("Consolas", 9), state="disabled"); self.docker_full_log.pack(fill=BOTH, expand=True)
        right_frame = ttk.Labelframe(paned, text="🚨 Solo Errores (Filtrado)", padding="5"); paned.add(right_frame, weight=1)
        copy_err_btn = ttk.Button(right_frame, text="📋 Copiar Solo Errores", command=self.copy_docker_errors, bootstyle="danger-outline"); copy_err_btn.pack(fill=X, pady=(0, 5))
        self.docker_error_log = scrolledtext.ScrolledText(right_frame, wrap=tk.NONE, font=("Consolas", 9), state="disabled", foreground="#FF5252"); self.docker_error_log.pack(fill=BOTH, expand=True)

    def refresh_docker_containers(self):
        try:
            result = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True)
            if result.returncode != 0: messagebox.showerror("Error Docker", "No se pudo conectar con Docker.\n¿Está corriendo el servicio?"); return
            containers = [c for c in result.stdout.strip().split('\n') if c]
            if not containers: self.docker_combo['values'] = []; self.docker_status_label.config(text="No hay contenedores corriendo.")
            else: self.docker_combo['values'] = containers; self.docker_combo.current(0); self.docker_status_label.config(text=f"Encontrados: {len(containers)}")
        except FileNotFoundError: messagebox.showerror("Error", "No se encontró el ejecutable 'docker'.")

    def fetch_docker_logs(self):
        container = self.docker_combo.get()
        if not container: return
        self.docker_status_label.config(text="Obteniendo logs..."); self.update_idletasks()
        def run_fetch():
            try:
                cmd = ["docker", "logs", "--tail", "2000", container]
                result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
                full_log = result.stdout + result.stderr
                error_keywords = ["error", "exception", "traceback", "fail", "fatal", "critical"]
                error_lines = [line for line in full_log.split('\n') if any(k in line.lower() for k in error_keywords)]
                self.after(0, lambda: self._update_docker_ui(full_log, "\n".join(error_lines)))
            except Exception as e: self.after(0, lambda: messagebox.showerror("Error", f"Fallo al leer logs: {e}"))
        threading.Thread(target=run_fetch, daemon=True).start()

    def _update_docker_ui(self, full, errors):
        self.docker_full_log.config(state="normal"); self.docker_full_log.delete("1.0", tk.END); self.docker_full_log.insert(tk.END, full); self.docker_full_log.see(tk.END); self.docker_full_log.config(state="disabled")
        self.docker_error_log.config(state="normal"); self.docker_error_log.delete("1.0", tk.END); self.docker_error_log.insert(tk.END, errors if errors else "(Sin errores detectados)"); self.docker_error_log.see(tk.END); self.docker_error_log.config(state="disabled")
        self.docker_status_label.config(text="Logs actualizados.")

    def copy_docker_errors(self):
        errors = self.docker_error_log.get("1.0", tk.END).strip()
        if errors and "Sin errores" not in errors: self.clipboard_clear(); self.clipboard_append(errors); messagebox.showinfo("Copiado", "Errores copiados.")
        else: messagebox.showwarning("Vacío", "No hay errores para copiar.")

    # ---------------------------------------------------------------
    # TAB: TIMELINE / ROADMAP (mejorado)
    # ---------------------------------------------------------------
    def _create_timeline_tab(self, parent_frame):
        tl_notebook = ttk.Notebook(parent_frame); tl_notebook.pack(fill=BOTH, expand=True, padx=5, pady=5)
        roadmap_frame = ttk.Frame(tl_notebook, padding="10"); tl_notebook.add(roadmap_frame, text="🗺 Roadmap del Proyecto"); self._create_roadmap_view(roadmap_frame)
        history_frame = ttk.Frame(tl_notebook, padding="10"); tl_notebook.add(history_frame, text="📜 Historial de Cambios"); self._create_history_view(history_frame)

    def _create_roadmap_view(self, parent):
        ctrl_frame = ttk.Frame(parent); ctrl_frame.pack(fill=X, pady=(0, 10))
        ttk.Button(ctrl_frame, text="📂 Cargar Roadmap Manualmente", command=self.load_roadmap_dialog, bootstyle="info-outline").pack(side=LEFT)
        self.roadmap_label = ttk.Label(ctrl_frame, text="Ningún roadmap cargado", font=("Helvetica", 10, "bold")); self.roadmap_label.pack(side=LEFT, padx=20)
        self.roadmap_canvas = tk.Canvas(parent, bg="#1e1e1e", highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=self.roadmap_canvas.yview)
        self.roadmap_scroll_frame = ttk.Frame(self.roadmap_canvas, padding="20")
        self.roadmap_scroll_frame.bind("<Configure>", lambda e: self.roadmap_canvas.configure(scrollregion=self.roadmap_canvas.bbox("all")))
        self.roadmap_canvas.create_window((0, 0), window=self.roadmap_scroll_frame, anchor="nw")
        self.roadmap_canvas.configure(yscrollcommand=vsb.set)
        self.roadmap_canvas.pack(side=LEFT, fill=BOTH, expand=True); vsb.pack(side=RIGHT, fill=Y)

    def _create_history_view(self, parent):
        # Leyenda
        legend_frame = ttk.Frame(parent)
        legend_frame.pack(fill=X, pady=(0, 6))
        ttk.Label(legend_frame, text="Leyenda:", font=("Helvetica", 9, "bold")).pack(side=LEFT, padx=(0, 10))
        tk.Label(legend_frame, text="●", fg="#4CAF50", bg="#2b2b2b", font=("Arial", 14)).pack(side=LEFT)
        ttk.Label(legend_frame, text="Cambio de archivos", font=("Helvetica", 9)).pack(side=LEFT, padx=(2, 12))
        tk.Label(legend_frame, text="●", fg="#2196F3", bg="#2b2b2b", font=("Arial", 14)).pack(side=LEFT)
        ttk.Label(legend_frame, text="Reporte generado", font=("Helvetica", 9)).pack(side=LEFT, padx=(2, 0))

        paned = ttk.Panedwindow(parent, orient=HORIZONTAL); paned.pack(fill=BOTH, expand=True)
        left_frame = ttk.Labelframe(paned, text="Eventos", padding="10"); paned.add(left_frame, weight=1)
        self.timeline_canvas = tk.Canvas(left_frame, bg="#2b2b2b", highlightthickness=0); self.timeline_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        vsb = ttk.Scrollbar(left_frame, orient="vertical", command=self.timeline_canvas.yview); vsb.pack(side=RIGHT, fill=Y)
        self.timeline_canvas.configure(yscrollcommand=vsb.set)
        right_frame = ttk.Labelframe(paned, text="Detalles", padding="10"); paned.add(right_frame, weight=2)
        self.timeline_detail_label = ttk.Label(right_frame, text="Selecciona un evento.", font=("Helvetica", 10, "italic")); self.timeline_detail_label.pack(anchor="w", pady=(0, 10))
        self.timeline_text = scrolledtext.ScrolledText(right_frame, wrap=tk.NONE, font=("Consolas", 9), state="disabled"); self.timeline_text.pack(fill=BOTH, expand=True)

    def load_roadmap_dialog(self):
        filename = filedialog.askopenfilename(initialdir=self.base_dir, title="Seleccionar Roadmap", filetypes=(("Markdown", "*.md"), ("All files", "*.*")))
        if filename: self.load_roadmap(Path(filename))

    def load_roadmap(self, path):
        self.current_roadmap_path = path
        if not self.roadmap_parser.assign_ids_if_missing(path):
            messagebox.showwarning("Roadmap", "No se pudo leer o actualizar el archivo roadmap con IDs.")
        data = self.roadmap_parser.parse(path)
        if not data: messagebox.showerror("Error", "No se pudo parsear el roadmap."); return
        self.current_roadmap_data = data
        self.roadmap_label.config(text=f"Proyecto: {data['title']}")
        for widget in self.roadmap_scroll_frame.winfo_children(): widget.destroy()
        total_tasks_global, total_done_global = 0, 0
        for phase in data['phases']:
            total_tasks_global += phase['total']; total_done_global += phase['done']
            p_frame = ttk.Labelframe(self.roadmap_scroll_frame, text=f" {phase['name']} ", padding="10", bootstyle="info")
            p_frame.pack(fill=X, pady=(0, 15), anchor="n")
            prog_frame = ttk.Frame(p_frame); prog_frame.pack(fill=X, pady=(0, 10))
            percent = (phase['done'] / phase['total'] * 100) if phase['total'] > 0 else 0
            ttk.Progressbar(prog_frame, value=percent, maximum=100, bootstyle="success-striped").pack(side=LEFT, fill=X, expand=True, padx=(0, 10))
            ttk.Label(prog_frame, text=f"{int(percent)}% ({phase['done']}/{phase['total']})", font=("Consolas", 10, "bold")).pack(side=LEFT)
            for task in phase['tasks']:
                t_frame = ttk.Frame(p_frame); t_frame.pack(fill=X, pady=2)
                icon = "✅" if task['done'] else "⬜"
                color = "success" if task['done'] else "secondary"
                ttk.Label(t_frame, text=icon, font=("Segoe UI Emoji", 10)).pack(side=LEFT, padx=(0, 5))
                task_display_text = f"[{task['id'] or '???'}] {task['text']}"
                lbl = ttk.Label(t_frame, text=task_display_text, bootstyle=color)
                lbl.pack(side=LEFT)
                if task['done']: lbl.configure(font=("Helvetica", 9, "overstrike"))
        global_percent = (total_done_global / total_tasks_global * 100) if total_tasks_global > 0 else 0
        self.global_project_label.config(text=f"PRJ: {data['title']}")
        self.global_progress['value'] = global_percent
        self.global_percent_label.config(text=f"{int(global_percent)}%")
        self.global_status_msg.config(text=f"Fase Activa: {data['phases'][0]['name'] if data['phases'] else 'N/A'}")
        self._draw_mini_roadmap()

    def _draw_mini_roadmap(self):
        self.mini_map_canvas.delete("all")
        if not self.current_roadmap_data:
            self.mini_map_canvas.create_text(100, 50, text="Sin Roadmap", fill="#666", font=("Consolas", 10))
            return
        x_line, y, step_y = 20, 20, 30
        phases = self.current_roadmap_data['phases']
        first_pending_y, found_pending = 0, False
        for phase in phases:
            self.mini_map_canvas.create_oval(x_line-6, y-6, x_line+6, y+6, fill="#007acc", outline="#fff")
            self.mini_map_canvas.create_text(x_line+15, y, text=phase['name'], anchor="w", fill="#fff", font=("Consolas", 9, "bold")); y += step_y
            for task in phase['tasks']:
                self.mini_map_canvas.create_line(x_line, y-step_y, x_line, y, fill="#444", width=1)
                color, radius = ("#4CAF50", 3) if task['done'] else ("#555", 3)
                if not task['done'] and not found_pending:
                    color, radius = "#FF9800", 5
                    self.mini_map_canvas.create_text(x_line-15, y, text="➤", fill="#FF9800", font=("Arial", 10, "bold"))
                    first_pending_y, found_pending = y, True
                self.mini_map_canvas.create_oval(x_line-radius, y-radius, x_line+radius, y+radius, fill=color, outline="")
                text_color = "#aaa" if task['done'] else ("#fff" if color == "#FF9800" else "#777")
                display_text = f"[{task['id'] or '?'}] {(task['text'][:20] + '..') if len(task['text']) > 20 else task['text']}"
                self.mini_map_canvas.create_text(x_line+15, y, text=display_text, anchor="w", fill=text_color, font=("Consolas", 8)); y += 20
            y += 10
        self.mini_map_canvas.configure(scrollregion=self.mini_map_canvas.bbox("all"))
        if first_pending_y > 0:
            canvas_height = self.mini_map_canvas.winfo_height() or 400
            fraction = (first_pending_y - (canvas_height / 2)) / y
            self.mini_map_canvas.yview_moveto(max(0, fraction))

    def update_timeline_visuals(self):
        """
        Dibuja todos los eventos (cambios de archivos + reportes generados)
        en orden cronológico, diferenciados por color e icono.
        """
        self.timeline_canvas.delete("all")
        all_events = self.history_manager.get_all_events()
        if not all_events: return

        start_x, start_y, step_y = 30, 30, 60
        self.timeline_canvas.create_line(start_x, start_y, start_x, start_y + (len(all_events) * step_y), fill="#555", width=2)

        for i, event in enumerate(all_events):
            y = start_y + (i * step_y)
            is_last = (i == len(all_events) - 1)
            event_type = event.get("event_type", "change")

            if event_type == "report":
                color = "#2196F3"  # Azul para reportes
                icon_text = "📄"
                desc_color = "#90CAF9"
            else:
                color = "#4CAF50" if is_last else "#888"  # Verde para el último cambio, gris para los anteriores
                icon_text = "✏"
                desc_color = "#fff"

            radius = 8
            self.timeline_canvas.create_oval(
                start_x - radius, y - radius, start_x + radius, y + radius,
                fill=color, outline="#fff", width=2, tags=f"node_{i}"
            )
            self.timeline_canvas.create_text(
                start_x + 20, y - 10, text=f"{icon_text}  {event['timestamp']}",
                anchor="w", fill="#aaa", font=("Consolas", 8), tags=f"node_{i}"
            )
            self.timeline_canvas.create_text(
                start_x + 20, y + 5, text=event['description'],
                anchor="w", fill=desc_color, font=("Helvetica", 10, "bold"), tags=f"node_{i}"
            )
            self.timeline_canvas.tag_bind(f"node_{i}", "<Button-1>", lambda ev, s=event: self._show_timeline_details(s))
            self.timeline_canvas.tag_bind(f"node_{i}", "<Enter>", lambda ev: self.timeline_canvas.config(cursor="hand2"))
            self.timeline_canvas.tag_bind(f"node_{i}", "<Leave>", lambda ev: self.timeline_canvas.config(cursor=""))

        self.timeline_canvas.configure(scrollregion=self.timeline_canvas.bbox("all"))
        # Auto-scroll al evento más reciente
        if all_events:
            total_height = start_y + (len(all_events) * step_y)
            self.timeline_canvas.yview_moveto(max(0, (total_height - 300) / total_height))

    def _show_timeline_details(self, snapshot):
        self.timeline_detail_label.config(text=f"[{snapshot.get('event_type','change').upper()}] {snapshot['timestamp']} — {snapshot['description']}")
        self.timeline_text.config(state="normal")
        self.timeline_text.delete("1.0", tk.END)
        event_type = snapshot.get("event_type", "change")
        if event_type == "report":
            details = (
                f"EVENTO: Reporte Generado\n"
                f"Hora:   {snapshot['timestamp']}\n"
                f"Archivo: {snapshot.get('fname', 'N/A')}\n"
                f"Archivos incluidos: {snapshot.get('file_count', 0)}\n"
                f"Opciones: {snapshot.get('options', 'N/A')}\n"
            )
            self.timeline_text.insert(tk.END, details)
        else:
            backups = snapshot.get("backups", {})
            self.timeline_text.insert(tk.END, f"EVENTO: Cambio de Archivos ({len(backups)} archivos)\n\n")
            for rel_path, content in backups.items():
                self.timeline_text.insert(tk.END, f"── {rel_path} ──\n")
                if content is None:
                    self.timeline_text.insert(tk.END, "(archivo nuevo, no existía antes)\n\n")
                else:
                    preview = content[:500] + ("…" if len(content) > 500 else "")
                    self.timeline_text.insert(tk.END, preview + "\n\n")
        self.timeline_text.config(state="disabled")

    # ---------------------------------------------------------------
    # LÓGICA DE APLICACIÓN DE CAMBIOS
    # ---------------------------------------------------------------
    def run_apply_structure(self):
        self.output_console.config(state="normal"); self.output_console.delete("1.0", tk.END); self.output_console.config(state="disabled")
        text = self.input_text.get("1.0", tk.END)
        if not text.strip(): return
        actions = self._parse_structure_text(text)
        if not actions: self.log_to_console("[⚠] No hay comandos válidos.", "WARNING"); return
        analyzed = self._analyze_impact(actions)
        is_dry_run = self.dry_run_var.get()
        if not is_dry_run:
            shrinking = [a for a in analyzed if a.get('is_shrinking')]
            if shrinking:
                msg = "⚠ ADVERTENCIA: Estos archivos reducirán su tamaño:\n" + "\n".join([f"• {a['path'].name}: {a['diff_str']}" for a in shrinking])
                if not messagebox.askyesno("Confirmar", msg + "\n¿Continuar?", icon='warning'): return
            files_to_backup = []
            for action in analyzed:
                if action['type'] in ('file', 'delete', 'append', 'replace'): files_to_backup.append(action['path_str'])
                elif action['type'] == 'move':
                    files_to_backup.append(action['source_str'])
                    dest_path = self.base_dir / action['dest_str']
                    if dest_path.exists(): files_to_backup.append(action['dest_str'])
            if files_to_backup:
                self.history_manager.create_snapshot(list(set(files_to_backup)), self.base_dir, description=f"Cambio masivo ({len(analyzed)} acciones)")
                self.undo_button.config(state="normal"); self.update_timeline_visuals()
        self._execute_actions(analyzed, is_dry_run)

    def undo_last_action(self):
        snapshot = self.history_manager.pop_snapshot()
        if not snapshot: messagebox.showinfo("Info", "No hay más acciones para deshacer."); self.undo_button.config(state="disabled"); return
        if not messagebox.askyesno("Deshacer", f"¿Revertir acción: '{snapshot['description']}'?"): self.history_manager.stack.append(snapshot); return
        self.log_to_console("="*40, "BOLD"); self.log_to_console(f"↶ REVIRTIENDO: {snapshot['description']}", "WARNING")
        for rel_path, content in snapshot['backups'].items():
            full_path = self.base_dir / rel_path
            if content is None:
                if full_path.exists():
                    try:
                        if full_path.is_file(): full_path.unlink()
                        elif full_path.is_dir(): shutil.rmtree(full_path)
                        self.log_to_console(f"[🗑] Eliminado (era nuevo): {rel_path}", "INFO")
                    except Exception as e: self.log_to_console(f"[✗] Error: {e}", "ERROR")
            else:
                try:
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(full_path, 'w', encoding='utf-8') as f: f.write(content)
                    self.log_to_console(f"[↺] Restaurado: {rel_path}", "SUCCESS")
                except Exception as e: self.log_to_console(f"[✗] Error: {e}", "ERROR")
        if not self.history_manager.stack: self.undo_button.config(state="disabled")
        self.update_timeline_visuals()

    def generate_fix_prompt(self):
        history = self.history_manager.get_history()
        if not history: messagebox.showwarning("Sin historial", "No hay acciones recientes para reportar."); return
        last_snapshot = history[-1]
        if not last_snapshot['backups']: messagebox.showwarning("Sin archivos", "El último snapshot no contiene archivos modificados."); return
        rel_path = list(last_snapshot['backups'].keys())[0]
        original_code = last_snapshot['backups'][rel_path]
        full_path = self.base_dir / rel_path
        current_code = ""
        if full_path.exists():
            with open(full_path, 'r', encoding='utf-8') as f: current_code = f.read()
        prompt = f"""🚨 **ERROR TRAS TU ÚLTIMA MODIFICACIÓN** 🚨

Agente, tu último intento de modificar `{rel_path}` ha causado una atrofia/error en el código.

Aquí tienes el contexto para que lo arregles usando `--- REPLACE IN FILE: {rel_path} ---`.

### CÓDIGO ORIGINAL (Antes de tu cambio, funcionaba bien):
```python
{original_code}
```

### CÓDIGO ACTUAL (Con tu modificación fallida):
```python
{current_code}
```

**INSTRUCCIÓN:**
1. Analiza qué rompiste (indentación, variables faltantes, lógica incorrecta).
2. Genera un nuevo bloque `REPLACE IN FILE` para corregirlo. Asegúrate de que el bloque `<<<SEARCH` coincida EXACTAMENTE con el "CÓDIGO ACTUAL" mostrado arriba.
"""
        self.clipboard_clear(); self.clipboard_append(prompt)
        messagebox.showinfo("Prompt Copiado", "Se ha copiado un prompt con el 'Antes y Después' del código.\nPégalo en el chat del LLM para que arregle la atrofia.")

    def _parse_structure_text(self, text):
        pattern = r"(--- (?:START OF FILE|APPEND TO FILE|REPLACE IN FILE|CREATE DIR|DELETE FILE|MOVE FILE|LOAD ROADMAP): .*? ---|--- ROADMAP: DONE .*? ---)"
        blocks = re.split(pattern, text)
        if not blocks[0].strip(): blocks = blocks[1:]
        actions, i = [], 0
        while i < len(blocks):
            header = blocks[i]
            try:
                if header.startswith("--- START OF FILE:"):
                    path_str = header.replace("--- START OF FILE:", "").replace("---", "").strip()
                    content = blocks[i+1] if i + 1 < len(blocks) else ""
                    file_content = content.split("--- END OF FILE ---")[0]
                    if file_content.startswith("\n"): file_content = file_content[1:]
                    actions.append({'type': 'file', 'path_str': path_str, 'content': file_content}); i += 2
                elif header.startswith("--- APPEND TO FILE:"):
                    path_str = header.replace("--- APPEND TO FILE:", "").replace("---", "").strip()
                    content = blocks[i+1] if i + 1 < len(blocks) else ""
                    file_content = content.split("--- END OF FILE ---")[0]
                    if file_content.startswith("\n"): file_content = file_content[1:]
                    actions.append({'type': 'append', 'path_str': path_str, 'content': file_content}); i += 2
                elif header.startswith("--- REPLACE IN FILE:"):
                    path_str = header.replace("--- REPLACE IN FILE:", "").replace("---", "").strip()
                    content = blocks[i+1] if i + 1 < len(blocks) else ""
                    try:
                        search_part = content.split("<<<SEARCH")[1].split("===")[0].strip("\n")
                        replace_part = content.split(">>>REPLACE")[1].split("===")[0].strip("\n")
                        actions.append({'type': 'replace', 'path_str': path_str, 'search_block': search_part, 'replace_block': replace_part})
                    except IndexError:
                        self.log_to_console(f"[✗] Error de sintaxis del LLM en REPLACE IN FILE: {path_str}", "ERROR")
                    i += 2
                elif header.startswith("--- CREATE DIR:"):
                    path_str = header.replace("--- CREATE DIR:", "").replace("---", "").strip()
                    actions.append({'type': 'dir', 'path_str': path_str}); i += 2
                elif header.startswith("--- DELETE FILE:"):
                    path_str = header.replace("--- DELETE FILE:", "").replace("---", "").strip()
                    actions.append({'type': 'delete', 'path_str': path_str}); i += 1
                elif header.startswith("--- MOVE FILE:"):
                    path_part = header.replace("--- MOVE FILE:", "").replace("---", "").strip()
                    if " TO " in path_part:
                        source_str, dest_str = path_part.split(" TO ", 1)
                        actions.append({'type': 'move', 'source_str': source_str.strip(), 'dest_str': dest_str.strip()})
                    i += 1
                elif header.startswith("--- LOAD ROADMAP:"):
                    path_str = header.replace("--- LOAD ROADMAP:", "").replace("---", "").strip()
                    actions.append({'type': 'roadmap', 'path_str': path_str}); i += 1
                elif header.startswith("--- ROADMAP: DONE"):
                    raw_id = header.replace("--- ROADMAP: DONE", "").replace("---", "").strip()
                    id_match = re.match(r'(\d+)', raw_id)
                    task_id = id_match.group(1) if id_match else raw_id
                    actions.append({'type': 'roadmap_done', 'task_id': task_id}); i += 1
                else: i += 1
            except: i += 1
        return actions

    def _analyze_impact(self, actions):
        analyzed = []
        for action in actions:
            path_keys = ['path_str', 'source_str', 'dest_str']
            for key in path_keys:
                if key in action:
                    original_path = action[key]
                    normalized_path = original_path.replace('/', os.sep).replace('\\', os.sep)
                    prefix_to_check = f"{self.base_dir.name}{os.sep}"
                    if normalized_path.startswith(prefix_to_check):
                        action[key] = normalized_path[len(prefix_to_check):]
            action['diff_val'] = 0; action['diff_str'] = ""; action['is_shrinking'] = False; action['is_new'] = False
            if action['type'] == 'file':
                full_path = self.base_dir / action['path_str']; action['path'] = full_path; new_len = len(action['content'])
                if full_path.exists() and full_path.is_file():
                    try:
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f: old_len = len(f.read())
                        diff = new_len - old_len; action['diff_val'] = diff
                        if diff > 0: action['diff_str'] = f"(+{diff} chars)"
                        elif diff < 0: action['diff_str'] = f"({diff} chars)"; action['is_shrinking'] = True
                        else: action['diff_str'] = "(Igual)"
                    except: action['diff_str'] = "(?)"
                else: action['is_new'] = True; action['diff_str'] = f"(NUEVO: {new_len} chars)"
            elif action['type'] == 'append':
                full_path = self.base_dir / action['path_str']; action['path'] = full_path
                new_len = len(action['content']); action['diff_val'] = new_len; action['diff_str'] = f"(AÑADIR: +{new_len} chars)"
            elif action['type'] == 'replace':
                full_path = self.base_dir / action['path_str']; action['path'] = full_path
                diff = len(action['replace_block']) - len(action['search_block']); action['diff_val'] = diff
                if diff > 0: action['diff_str'] = f"(REEMPLAZO: +{diff} chars)"
                elif diff < 0: action['diff_str'] = f"(REEMPLAZO: {diff} chars)"; action['is_shrinking'] = True
                else: action['diff_str'] = "(REEMPLAZO: Igual)"
            elif action['type'] == 'move':
                action['source_path'] = self.base_dir / action['source_str']; action['dest_path'] = self.base_dir / action['dest_str']
                if not action['source_path'].exists(): action['diff_str'] = "(ERROR: Origen no existe)"
                elif action['dest_path'].exists(): action['diff_str'] = "(ADVERTENCIA: Sobrescribirá destino)"
                else: action['diff_str'] = "(Mover)"
            elif action['type'] in ['delete', 'dir', 'roadmap']: action['path'] = self.base_dir / action.get('path_str', '')
            analyzed.append(action)
        return analyzed

    def _execute_actions(self, actions, dry_run):
        roadmap_actions = [a for a in actions if a['type'] == 'roadmap_done']
        other_actions = [a for a in actions if a['type'] != 'roadmap_done']
        for action in other_actions:
            if action['type'] == 'file':
                full_path = action['path']; self.log_to_console(f"[📝] Archivo: {full_path}", "INFO")
                diff_tag = "DIFF_PLUS" if action['is_new'] or action['diff_val'] > 0 else ("DIFF_MINUS" if action['diff_val'] < 0 else "INFO")
                if not dry_run:
                    try:
                        full_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(full_path, 'w', encoding='utf-8') as f: f.write(action['content'])
                        self.log_to_console(f"[✓] Guardado ", "SUCCESS", end=""); self.log_to_console(action['diff_str'], diff_tag)
                        if full_path.name.endswith(".ctx.md"):
                            self._refresh_contexts_list(); self._refresh_report_ctx_list()
                    except Exception as e: self.log_to_console(f"[✗] Error: {e}", "ERROR")
                else: self.log_to_console(f"[✓] (Simulado) ", "SUCCESS", end=""); self.log_to_console(action['diff_str'], diff_tag)
            elif action['type'] == 'append':
                full_path = action['path']; self.log_to_console(f"[➕] Añadiendo a: {full_path}", "INFO")
                if not dry_run:
                    try:
                        full_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(full_path, 'a', encoding='utf-8') as f: f.write("\n" + action['content'])
                        self.log_to_console(f"[✓] Contenido añadido ", "SUCCESS", end=""); self.log_to_console(action['diff_str'], "DIFF_PLUS")
                        if full_path.name.endswith("roadmap.md"): self.load_roadmap(full_path)
                    except Exception as e: self.log_to_console(f"[✗] Error: {e}", "ERROR")
                else: self.log_to_console(f"[✓] (Simulado) Añadido", "SUCCESS", end=""); self.log_to_console(action['diff_str'], "DIFF_PLUS")
            elif action['type'] == 'replace':
                full_path = action['path']; self.log_to_console(f"[🔄] Reemplazando en: {full_path}", "INFO")
                if not full_path.exists(): self.log_to_console(f"[✗] REPLACE falló: El archivo {full_path.name} no existe.", "ERROR"); continue
                with open(full_path, 'r', encoding='utf-8') as f: original_content = f.read()
                if action['search_block'] not in original_content:
                    self.log_to_console(f"[✗] REPLACE falló en {full_path.name}: El bloque SEARCH no coincide exactamente.", "ERROR"); continue
                if not dry_run:
                    new_content = original_content.replace(action['search_block'], action['replace_block'])
                    with open(full_path, 'w', encoding='utf-8') as f: f.write(new_content)
                    self.log_to_console(f"[✓] Reemplazo parcial exitoso ", "SUCCESS", end=""); self.log_to_console(action['diff_str'], "INFO")
                else: self.log_to_console(f"[✓] (Simulado) Reemplazo ", "SUCCESS", end=""); self.log_to_console(action['diff_str'], "INFO")
            elif action['type'] == 'dir':
                full_path = action['path']
                if not dry_run: full_path.mkdir(parents=True, exist_ok=True)
                self.log_to_console(f"[📁] Directorio {'simulado' if dry_run else 'creado'}: {full_path}", "SUCCESS")
            elif action['type'] == 'delete':
                full_path = action['path']
                if not dry_run:
                    if full_path.exists():
                        if full_path.is_dir(): shutil.rmtree(full_path)
                        else: full_path.unlink()
                        self.log_to_console(f"[🗑] Borrado: {full_path}", "SUCCESS")
                    else: self.log_to_console(f"[⚠] No existía: {full_path}", "WARNING")
                else: self.log_to_console(f"[🗑] (Simulado) Borrar: {full_path}", "SUCCESS")
            elif action['type'] == 'move':
                source_path, dest_path = action['source_path'], action['dest_path']
                self.log_to_console(f"[✈️] Mover: {action['source_str']} -> {action['dest_str']}", "INFO")
                if not dry_run:
                    try:
                        if not source_path.exists(): self.log_to_console(f"[✗] Error: El archivo de origen no existe.", "ERROR"); continue
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(source_path), str(dest_path)); self.log_to_console(f"[✓] Movido exitosamente.", "SUCCESS")
                    except Exception as e: self.log_to_console(f"[✗] Error al mover: {e}", "ERROR")
                else: self.log_to_console(f"[✓] (Simulado) Movido.", "SUCCESS")
            elif action['type'] == 'roadmap':
                if not dry_run: self.load_roadmap(action['path'])
                self.log_to_console(f"[🗺] Cargando Roadmap: {action['path']}", "INFO")
        if roadmap_actions:
            task_ids_to_mark = {a['task_id'].zfill(3) for a in roadmap_actions}
            self.log_to_console(f"[✅] Marcando {len(task_ids_to_mark)} tareas en lote...", "INFO")
            if dry_run:
                self.log_to_console(f"[✓] (Simulado) Tareas {', '.join(sorted(task_ids_to_mark))} marcadas.", "SUCCESS"); return
            roadmap_path = self.current_roadmap_path
            if not roadmap_path or not roadmap_path.exists():
                self.log_to_console(f"[✗] Error: No hay un roadmap cargado o no se encuentra.", "ERROR"); return
            try:
                with open(roadmap_path, 'r', encoding='utf-8') as f: lines = f.readlines()
                modified_lines, tasks_changed_count = [], 0
                task_finder_pattern = re.compile(r'^\s*-\s\[\s\]\s+(?:\[(\d+)\]|(\d+):)')
                for line in lines:
                    match = task_finder_pattern.match(line.strip())
                    if match:
                        current_id = (match.group(1) or match.group(2)).zfill(3)
                        if current_id in task_ids_to_mark:
                            modified_lines.append(line.replace("- [ ]", "- [x]", 1)); tasks_changed_count += 1; task_ids_to_mark.remove(current_id)
                        else: modified_lines.append(line)
                    else: modified_lines.append(line)
                if tasks_changed_count > 0:
                    with open(roadmap_path, 'w', encoding='utf-8') as f: f.writelines(modified_lines)
                    self.log_to_console(f"[✓] {tasks_changed_count} tareas actualizadas en {roadmap_path.name}.", "SUCCESS")
                    self.load_roadmap(roadmap_path)
                else: self.log_to_console("[⚠] Ninguna tarea pendiente coincidió con los IDs proporcionados.", "WARNING")
                if task_ids_to_mark: self.log_to_console(f"[⚠] IDs no encontrados o ya completados: {', '.join(sorted(task_ids_to_mark))}", "WARNING")
            except Exception as e: self.log_to_console(f"[✗] Error al modificar {roadmap_path.name}: {e}", "ERROR")

    def copy_path_to_clipboard(self): self.clipboard_clear(); self.clipboard_append(str(self.base_dir))

    def open_in_explorer(self):
        try:
            if platform.system() == "Windows": os.startfile(str(self.base_dir))
            elif platform.system() == "Darwin": subprocess.Popen(["open", str(self.base_dir)])
            else: subprocess.Popen(["xdg-open", str(self.base_dir)])
        except Exception as e: messagebox.showerror("Error", f"No se pudo abrir el explorador: {e}")

    def clear_input(self): self.input_text.delete("1.0", tk.END)

    # ---------------------------------------------------------------
    # SCANNER Y ÁRBOL
    # ---------------------------------------------------------------
    def setup_report_generator_config(self):
        self.script_path_abs = os.path.abspath(__file__)
        self.directorios_a_ignorar = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', '.next', 'build', 'dist'}
        self.archivos_a_ignorar_por_nombre = {'package-lock.json', 'yarn.lock'}

    def start_scan_thread(self):
        self.reporter_status_label.config(text="Escaneando...")
        self.tree.delete(*self.tree.get_children())
        threading.Thread(target=self._scan_and_analyze, daemon=True).start()

    def _scan_and_analyze(self):
        data = self._build_tree_data_recursive(self.base_dir)
        self.after(0, self._populate_tree_from_data, data)
        self.dep_analyzer.base_dir = self.base_dir
        self.dep_analyzer.ignored_dirs = self.directorios_a_ignorar
        self.dep_analyzer.analyze_project()
        self.after(0, self._dep_analysis_done)

    def _build_tree_data_recursive(self, current_path):
        data = []
        try:
            for entry in sorted(os.scandir(current_path), key=lambda e: (e.is_file(), e.name.lower())):
                if entry.is_dir():
                    if entry.name in self.directorios_a_ignorar: continue
                    data.append({'type': 'dir', 'name': entry.name, 'path': entry.path, 'children': self._build_tree_data_recursive(entry.path)})
                else:
                    if entry.name in self.archivos_a_ignorar_por_nombre or entry.path == self.script_path_abs: continue
                    data.append({'type': 'file', 'name': entry.name, 'path': entry.path})
        except: pass
        return data

    def _populate_tree_from_data(self, data):
        self._insert_tree_items(data, ""); self.reporter_status_label.config(text="Listo"); self._update_stats()

    def _insert_tree_items(self, items, parent):
        for item in items:
            rel = Path(item['path']).relative_to(self.base_dir)
            if item['type'] == 'dir':
                cid = self.tree.insert(parent, "end", text=f"📁 {item['name']}", values=(str(rel), "☐", ""), open=False, tags=('dir',))
                self._insert_tree_items(item['children'], cid)
            else:
                sz = os.path.getsize(item['path'])
                self.tree.insert(parent, "end", text=f"📄 {item['name']}", values=(str(rel), "☐", f"{sz} B"), tags=('file',))

    def _on_tree_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item: return
        if self.tree.identify_column(event.x) == "#1":
            val = self.tree.item(item, "values")
            new_val = "☑" if val[1] == "☐" else "☐"
            self._toggle_recursive(item, new_val)
            self._update_stats()
            self._refresh_report_preview()

    def _toggle_recursive(self, item, val):
        self.tree.set(item, "inc", val)
        for child in self.tree.get_children(item): self._toggle_recursive(child, val)

    def _update_stats(self):
        total = 0
        def recurse(p):
            nonlocal total
            for c in self.tree.get_children(p):
                if 'file' in self.tree.item(c, 'tags') and self.tree.item(c, 'values')[1] == "☑":
                    try: total += os.path.getsize(self.base_dir / self.tree.item(c, 'values')[0])
                    except: pass
                recurse(c)
        recurse(""); self.total_chars_label.config(text=f"~{total} bytes sel.")

    def _on_tree_selection_change(self, event):
        sel = self.tree.selection()
        if not sel: return
        item = sel[0]
        if 'file' in self.tree.item(item, 'tags'):
            vals = self.tree.item(item, "values")
            if vals:
                rel = vals[0].replace(os.sep, '/')
                self._selected_file_for_deps = rel
                if self._dep_ready: self._show_dep_detail(rel)

    def _select_deps_for_selected_tree_item(self):
        if not self._dep_ready:
            messagebox.showwarning("Dependencias", "El análisis de dependencias aún no terminó.\nEspera un momento o usa la pestaña 🔗 Dependencias.")
            return
        sel = self.tree.selection()
        if not sel: messagebox.showinfo("Selección", "Selecciona un archivo en el árbol primero."); return
        item = sel[0]
        if 'file' not in self.tree.item(item, 'tags'): messagebox.showinfo("Selección", "Selecciona un archivo (no una carpeta)."); return
        vals = self.tree.item(item, "values")
        rel_path = vals[0].replace(os.sep, '/')
        self._selected_file_for_deps = rel_path
        all_deps = self.dep_analyzer.get_all_dependencies(rel_path)
        chain = all_deps | {rel_path}

        def mark_chain(parent_item):
            for child in self.tree.get_children(parent_item):
                child_vals = self.tree.item(child, "values")
                if child_vals and 'file' in self.tree.item(child, 'tags'):
                    child_rel = child_vals[0].replace(os.sep, '/')
                    new_val = "☑" if child_rel in chain else self.tree.item(child, "values")[1]
                    self.tree.set(child, "inc", new_val)
                mark_chain(child)

        def deselect_all(parent_item):
            for child in self.tree.get_children(parent_item):
                self.tree.set(child, "inc", "☐"); deselect_all(child)

        deselect_all(""); mark_chain("")
        self._update_stats(); self._refresh_report_preview()
        messagebox.showinfo("Cadena seleccionada", f"Seleccionados {len(chain)} archivo(s):\n{rel_path}\n+ {len(all_deps)} dep(s) transitiva(s)")

    # ---------------------------------------------------------------
    # CONTEXTO Y COPY HELPERS
    # ---------------------------------------------------------------
    def copy_project_map(self):
        map_text = self._build_map_text(files_for_sel_map=None)
        self.clipboard_clear(); self.clipboard_append(map_text)
        messagebox.showinfo("Mapa Copiado", "La estructura de archivos completa se ha copiado al portapapeles.")

    def copy_roadmap_context(self):
        if not self.current_roadmap_data:
            messagebox.showwarning("Sin Roadmap", "No hay un roadmap cargado para generar el contexto.")
            return
        batch_size = self.batch_size_var.get()
        lines = [f"CONTEXTO DEL ROADMAP: {self.current_roadmap_data['title']}"]
        for phase in self.current_roadmap_data['phases']:
            lines.append(f"\n## FASE: {phase['name']}")
            phase_pending = [f"- [ ] {t['id']}: {t['text']}" for t in phase['tasks'] if not t['done']]
            phase_done = [f"- [x] {t['id']}: {t['text']}" for t in phase['tasks'] if t['done']]
            if phase_pending: lines.extend(phase_pending)
            if phase_done: lines.extend(phase_done)
        lines.append("\n" + "="*40)
        lines.append("INSTRUCCIÓN PARA EL AGENTE:")
        lines.append(f"1. Analiza las tareas pendientes. Tu objetivo es completar un lote de {batch_size} tareas en esta respuesta.")
        lines.append("2. Genera TODOS los comandos de archivo necesarios concatenados.")
        lines.append("3. Al final de tu respuesta, usa múltiples '--- ROADMAP: DONE ID ---' para marcar todas las tareas procesadas.")
        final_text = "```\n" + "\n".join(lines) + "\n```"
        self.clipboard_clear(); self.clipboard_append(final_text)
        messagebox.showinfo("Contexto Copiado", f"Contexto del roadmap copiado.\nSe exige al LLM procesar {batch_size} tareas.")

    def copy_llm_context(self):
        roadmap_status = "No cargado"
        if self.current_roadmap_data:
            total = sum(p['total'] for p in self.current_roadmap_data['phases'])
            done = sum(p['done'] for p in self.current_roadmap_data['phases'])
            percent = int((done/total)*100) if total > 0 else 0
            roadmap_status = f"{self.current_roadmap_data['title']} - Progreso: {percent}% ({done}/{total} tareas)"
        batch_size = self.batch_size_var.get()
        dep_status = f"{len(self.dep_analyzer.graph)} archivos analizados" if self._dep_ready else "pendiente"
        context_msg = (
            f"INSTRUCCIÓN MAESTRA PARA EL AGENTE CONSTRUCTOR:\n"
            f"Eres un Arquitecto de Software experto. Tu objetivo es avanzar en el proyecto usando el 'Protocolo de Construcción Atómica'.\n\n"
            f"CONTEXTO DEL PROYECTO:\n"
            f"  - Ruta Base: {self.base_dir}\n"
            f"  - Estado Roadmap: {roadmap_status}\n"
            f"  - Análisis de Dependencias: {dep_status}\n\n"
            f"⚙️ PARÁMETROS DE EJECUCIÓN (BATCH PROCESSING):\n"
            f"  - Tamaño de Lote Objetivo: {batch_size} archivos/tareas por respuesta.\n"
            f"  - Tienes permitido y se espera que generes múltiples bloques de comandos en una sola respuesta para ahorrar tokens.\n\n"
            f"🤝 PRUEBA DE COMPRENSIÓN (HANDSHAKE INICIAL):\n"
            f"Si esta es la PRIMERA VEZ que recibes este prompt en esta conversación, NO generes código real todavía.\n"
            f"Demuestra que entiendes el protocolo de lotes generando un único bloque de código que contenga exactamente {batch_size} archivos VACÍOS (ej. test1.txt, test2.txt...) usando el comando '--- START OF FILE: ruta ---'.\n\n"
            f"ACCIÓN INMEDIATA (Si ya pasaste el Handshake):\n"
            f"1. Solicita al usuario el 'Contexto del Roadmap' para ver las tareas pendientes.\n"
            f"2. Usa la pestaña '🧠 Contextos' o '🔗 Dependencias' (si el usuario te la proporciona) para entender el contexto antes de modificar.\n"
            f"3. Procede a completar las siguientes {batch_size} tareas lógicas.\n"
            f"4. Al final, marca las {batch_size} tareas como completadas usando múltiples '--- ROADMAP: DONE ID ---'."
        )
        self.clipboard_clear(); self.clipboard_append(context_msg)
        messagebox.showinfo("Contexto Copiado", f"Prompt maestro copiado.\nSe ha instruido al LLM para procesar lotes de {batch_size} archivos.")

    # ---------------------------------------------------------------
    # ESTILOS Y CONSOLA
    # ---------------------------------------------------------------
    def _configure_styles(self):
        s = ttk.Style()
        s.configure('Treeview', font=('Consolas', 9), rowheight=22)
        s.configure('TButton', font=('Helvetica', 9))

    def _configure_console_tags(self):
        self.output_console.tag_config("SUCCESS", foreground="#4CAF50", font=("Consolas", 10, "bold"))
        self.output_console.tag_config("INFO", foreground="#2196F3")
        self.output_console.tag_config("WARNING", foreground="#FFC107", font=("Consolas", 10, "bold"))
        self.output_console.tag_config("ERROR", foreground="#F44336", font=("Consolas", 10, "bold"))
        self.output_console.tag_config("BOLD", font=("Consolas", 11, "bold"))
        self.output_console.tag_config("DIFF_PLUS", foreground="#00E676")
        self.output_console.tag_config("DIFF_MINUS", foreground="#FF5252")

    def log_to_console(self, msg, tag, end="\n"):
        self.output_console.config(state="normal")
        self.output_console.insert(tk.END, msg + end, tag)
        self.output_console.config(state="disabled")
        self.output_console.see(tk.END)


# --- APLICACIÓN PRINCIPAL (GESTOR DE PESTAÑAS) ---
class ConstructorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Constructor Multi-Workspace v8.4.0 - Reporte Unificado")
        self.root.geometry("1400x900")
        toolbar = ttk.Frame(self.root, padding="5"); toolbar.pack(fill=X, side=TOP)
        ttk.Button(toolbar, text="➕ Nuevo Workspace (Abrir Carpeta)", command=self.add_project_tab, bootstyle="primary").pack(side=LEFT, padx=5)
        ttk.Label(toolbar, text="Gestor de Proyectos", font=("Helvetica", 12, "bold")).pack(side=RIGHT, padx=10)
        self.project_notebook = ttk.Notebook(self.root); self.project_notebook.pack(fill=BOTH, expand=True, padx=5, pady=5)
        self.add_project_tab(os.getcwd())

    def add_project_tab(self, initial_dir=None):
        if not initial_dir: initial_dir = filedialog.askdirectory(title="Seleccionar Carpeta del Proyecto")
        if initial_dir:
            path_obj = Path(initial_dir)
            workspace = ProjectWorkspace(self.project_notebook, path_obj)
            self.project_notebook.add(workspace, text=f"📂 {path_obj.name}")
            self.project_notebook.select(workspace)


if __name__ == "__main__":
    root = ttkbootstrap.Window(themename="darkly")
    app = ConstructorApp(root)
    root.mainloop()