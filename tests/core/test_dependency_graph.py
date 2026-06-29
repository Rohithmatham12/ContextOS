"""Tests for contextos/core/dependency_graph.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from contextos.cli.main import app
from contextos.core.dependency_graph import (
    DependencyGraph,
    DGEdge,
    DGNode,
    _find_cycles,
    build_graph,
    load_graph,
    write_graph,
)
from contextos.core.scanner import scan

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _edges_by_kind(graph: DependencyGraph, kind: str) -> list[tuple[str, str]]:
    return [(e.source, e.target) for e in graph.edges if e.kind == kind]


# ---------------------------------------------------------------------------
# Python — local imports
# ---------------------------------------------------------------------------


class TestPythonLocalImports:
    def test_absolute_import_resolves_to_local_file(self, tmp_path: Path) -> None:
        _write(tmp_path / "pkg" / "__init__.py", "")
        _write(tmp_path / "pkg" / "utils.py", "def helper(): pass\n")
        _write(tmp_path / "pkg" / "main.py", "from pkg.utils import helper\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        local = _edges_by_kind(graph, "local")
        assert ("pkg/main.py", "pkg/utils.py") in local

    def test_relative_import_dot_module(self, tmp_path: Path) -> None:
        _write(tmp_path / "pkg" / "__init__.py", "")
        _write(tmp_path / "pkg" / "utils.py", "x = 1\n")
        _write(tmp_path / "pkg" / "main.py", "from .utils import x\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        local = _edges_by_kind(graph, "local")
        assert ("pkg/main.py", "pkg/utils.py") in local

    def test_from_dot_import_name(self, tmp_path: Path) -> None:
        """from . import submodule — each name is tried as a submodule."""
        _write(tmp_path / "pkg" / "__init__.py", "")
        _write(tmp_path / "pkg" / "sub.py", "x = 1\n")
        _write(tmp_path / "pkg" / "main.py", "from . import sub\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        local = _edges_by_kind(graph, "local")
        assert ("pkg/main.py", "pkg/sub.py") in local

    def test_double_dot_relative_import(self, tmp_path: Path) -> None:
        _write(tmp_path / "pkg" / "__init__.py", "")
        _write(tmp_path / "pkg" / "shared.py", "x = 1\n")
        _write(tmp_path / "pkg" / "sub" / "__init__.py", "")
        _write(tmp_path / "pkg" / "sub" / "view.py", "from ..shared import x\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        local = _edges_by_kind(graph, "local")
        assert ("pkg/sub/view.py", "pkg/shared.py") in local

    def test_import_statement_resolves_to_init(self, tmp_path: Path) -> None:
        _write(tmp_path / "pkg" / "__init__.py", "")
        _write(tmp_path / "main.py", "import pkg\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        local = _edges_by_kind(graph, "local")
        assert ("main.py", "pkg/__init__.py") in local

    def test_no_duplicate_edges(self, tmp_path: Path) -> None:
        _write(tmp_path / "pkg" / "__init__.py", "")
        _write(tmp_path / "pkg" / "utils.py", "x = 1\n")
        _write(
            tmp_path / "pkg" / "main.py",
            "from pkg.utils import x\nfrom pkg.utils import y\n",
        )
        result = scan(tmp_path)
        graph = build_graph(result)
        local = [(e.source, e.target) for e in graph.edges if e.kind == "local"]
        assert local.count(("pkg/main.py", "pkg/utils.py")) == 1

    def test_syntax_error_returns_empty(self, tmp_path: Path) -> None:
        _write(tmp_path / "bad.py", "def (broken syntax:\n    pass\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        sources = {e.source for e in graph.edges}
        assert "bad.py" not in sources


# ---------------------------------------------------------------------------
# Python — package imports
# ---------------------------------------------------------------------------


class TestPythonPackageImports:
    def test_stdlib_import_classified_as_package(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "import os\nimport sys\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        pkg = _edges_by_kind(graph, "package")
        assert ("main.py", "os") in pkg
        assert ("main.py", "sys") in pkg

    def test_third_party_import_classified_as_package(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "import fastapi\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        pkg = _edges_by_kind(graph, "package")
        assert ("main.py", "fastapi") in pkg

    def test_submodule_import_strips_to_top_package(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "import os.path\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        pkg = _edges_by_kind(graph, "package")
        assert ("main.py", "os") in pkg

    def test_from_package_import(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "from pathlib import Path\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        pkg = _edges_by_kind(graph, "package")
        assert ("main.py", "pathlib") in pkg


# ---------------------------------------------------------------------------
# JS/TS — local imports
# ---------------------------------------------------------------------------


class TestJSLocalImports:
    def test_es_module_relative_import(self, tmp_path: Path) -> None:
        _write(tmp_path / "src" / "utils.js", "export function x() {}\n")
        _write(tmp_path / "src" / "app.js", "import { x } from './utils';\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        local = _edges_by_kind(graph, "local")
        assert ("src/app.js", "src/utils.js") in local

    def test_ts_extension_resolution(self, tmp_path: Path) -> None:
        _write(tmp_path / "src" / "utils.ts", "export const x = 1;\n")
        _write(tmp_path / "src" / "app.ts", "import { x } from './utils';\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        local = _edges_by_kind(graph, "local")
        assert ("src/app.ts", "src/utils.ts") in local

    def test_parent_dir_relative_import(self, tmp_path: Path) -> None:
        _write(tmp_path / "lib" / "helper.ts", "export const h = 1;\n")
        _write(tmp_path / "src" / "app.ts", "import { h } from '../lib/helper';\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        local = _edges_by_kind(graph, "local")
        assert ("src/app.ts", "lib/helper.ts") in local

    def test_index_file_resolution(self, tmp_path: Path) -> None:
        _write(tmp_path / "components" / "index.ts", "export const C = 1;\n")
        _write(tmp_path / "app.ts", "import { C } from './components';\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        local = _edges_by_kind(graph, "local")
        assert ("app.ts", "components/index.ts") in local

    def test_require_statement_resolved(self, tmp_path: Path) -> None:
        _write(tmp_path / "utils.js", "module.exports = {};\n")
        _write(tmp_path / "app.js", "const u = require('./utils');\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        local = _edges_by_kind(graph, "local")
        assert ("app.js", "utils.js") in local

    def test_tsx_extension_resolved(self, tmp_path: Path) -> None:
        _write(tmp_path / "Button.tsx", "export const Button = () => null;\n")
        _write(tmp_path / "App.tsx", "import { Button } from './Button';\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        local = _edges_by_kind(graph, "local")
        assert ("App.tsx", "Button.tsx") in local


# ---------------------------------------------------------------------------
# JS/TS — package imports
# ---------------------------------------------------------------------------


class TestJSPackageImports:
    def test_npm_package_import(self, tmp_path: Path) -> None:
        _write(tmp_path / "app.js", "import React from 'react';\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        pkg = _edges_by_kind(graph, "package")
        assert ("app.js", "react") in pkg

    def test_scoped_package_import(self, tmp_path: Path) -> None:
        _write(tmp_path / "app.ts", "import { Component } from '@angular/core';\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        pkg = _edges_by_kind(graph, "package")
        assert ("app.ts", "@angular") in pkg

    def test_subpath_import_strips_to_package(self, tmp_path: Path) -> None:
        _write(tmp_path / "app.js", "import { createRoot } from 'react-dom/client';\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        pkg = _edges_by_kind(graph, "package")
        assert ("app.js", "react-dom") in pkg

    def test_require_package(self, tmp_path: Path) -> None:
        _write(tmp_path / "app.js", "const express = require('express');\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        pkg = _edges_by_kind(graph, "package")
        assert ("app.js", "express") in pkg

    def test_type_only_import_classified_as_package(self, tmp_path: Path) -> None:
        _write(tmp_path / "app.ts", "import type { FC } from 'react';\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        pkg = _edges_by_kind(graph, "package")
        assert ("app.ts", "react") in pkg

    def test_side_effect_import_classified_as_package(self, tmp_path: Path) -> None:
        _write(tmp_path / "app.ts", "import 'reflect-metadata';\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        pkg = _edges_by_kind(graph, "package")
        assert ("app.ts", "reflect-metadata") in pkg


# ---------------------------------------------------------------------------
# Unresolved imports
# ---------------------------------------------------------------------------


class TestUnresolvedImports:
    def test_missing_python_relative_marked_unresolved(self, tmp_path: Path) -> None:
        _write(tmp_path / "pkg" / "__init__.py", "")
        _write(tmp_path / "pkg" / "main.py", "from .missing import something\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        assert "pkg/main.py" in graph.unresolved
        assert any(".missing" in u for u in graph.unresolved["pkg/main.py"])

    def test_missing_js_relative_marked_unresolved(self, tmp_path: Path) -> None:
        _write(tmp_path / "app.js", "import { x } from './does_not_exist';\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        assert "app.js" in graph.unresolved
        assert "./does_not_exist" in graph.unresolved["app.js"]

    def test_package_import_not_in_unresolved(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "import os\nimport fastapi\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        assert "main.py" not in graph.unresolved

    def test_resolved_local_not_in_unresolved(self, tmp_path: Path) -> None:
        _write(tmp_path / "pkg" / "__init__.py", "")
        _write(tmp_path / "pkg" / "utils.py", "x = 1\n")
        _write(tmp_path / "pkg" / "main.py", "from .utils import x\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        assert "pkg/main.py" not in graph.unresolved

    def test_from_dot_import_unknown_name_not_unresolved(self, tmp_path: Path) -> None:
        """from . import SomeClass — name might be a class, not a module; not unresolved."""
        _write(tmp_path / "pkg" / "__init__.py", "from .core import SomeClass\n")
        _write(tmp_path / "pkg" / "core.py", "class SomeClass: pass\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        unresolved_all: list[str] = []
        for items in graph.unresolved.values():
            unresolved_all.extend(items)
        assert "SomeClass" not in unresolved_all


# ---------------------------------------------------------------------------
# Circular imports
# ---------------------------------------------------------------------------


class TestCircularImports:
    def test_simple_two_node_cycle(self, tmp_path: Path) -> None:
        _write(tmp_path / "pkg" / "__init__.py", "")
        _write(tmp_path / "pkg" / "a.py", "from pkg.b import y\n")
        _write(tmp_path / "pkg" / "b.py", "from pkg.a import x\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        assert len(graph.cycles) > 0
        cycle_nodes = {n for cycle in graph.cycles for n in cycle}
        assert "pkg/a.py" in cycle_nodes
        assert "pkg/b.py" in cycle_nodes

    def test_three_node_cycle(self, tmp_path: Path) -> None:
        _write(tmp_path / "pkg" / "__init__.py", "")
        _write(tmp_path / "pkg" / "a.py", "from pkg.b import y\n")
        _write(tmp_path / "pkg" / "b.py", "from pkg.c import z\n")
        _write(tmp_path / "pkg" / "c.py", "from pkg.a import x\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        assert len(graph.cycles) > 0

    def test_acyclic_graph_no_cycles(self, tmp_path: Path) -> None:
        _write(tmp_path / "pkg" / "__init__.py", "")
        _write(tmp_path / "pkg" / "base.py", "x = 1\n")
        _write(tmp_path / "pkg" / "mid.py", "from pkg.base import x\n")
        _write(tmp_path / "pkg" / "top.py", "from pkg.mid import x\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        assert graph.cycles == []

    def test_js_cycle_detected(self, tmp_path: Path) -> None:
        _write(tmp_path / "a.js", "import { y } from './b';\n")
        _write(tmp_path / "b.js", "import { x } from './a';\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        assert len(graph.cycles) > 0

    def test_self_import_cycle(self, tmp_path: Path) -> None:
        _write(tmp_path / "pkg" / "__init__.py", "")
        _write(tmp_path / "pkg" / "a.py", "from pkg.a import x\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        assert len(graph.cycles) > 0

    def test_cycle_entries_are_file_paths(self, tmp_path: Path) -> None:
        _write(tmp_path / "pkg" / "__init__.py", "")
        _write(tmp_path / "pkg" / "a.py", "from pkg.b import y\n")
        _write(tmp_path / "pkg" / "b.py", "from pkg.a import x\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        for cycle in graph.cycles:
            for node in cycle:
                assert node.endswith(".py")


# ---------------------------------------------------------------------------
# _find_cycles unit tests
# ---------------------------------------------------------------------------


class TestFindCyclesDirect:
    def _edge(self, src: str, tgt: str) -> DGEdge:
        return DGEdge(source=src, target=tgt, kind="local", raw_import="")

    def test_no_edges_no_cycles(self) -> None:
        assert _find_cycles([]) == []

    def test_simple_cycle(self) -> None:
        edges = [self._edge("a", "b"), self._edge("b", "a")]
        cycles = _find_cycles(edges)
        assert len(cycles) == 1

    def test_self_loop(self) -> None:
        edges = [self._edge("a", "a")]
        cycles = _find_cycles(edges)
        assert len(cycles) == 1

    def test_linear_chain_no_cycle(self) -> None:
        edges = [self._edge("a", "b"), self._edge("b", "c")]
        assert _find_cycles(edges) == []

    def test_package_edges_ignored(self) -> None:
        edges = [
            DGEdge(source="a", target="b", kind="package", raw_import=""),
            DGEdge(source="b", target="a", kind="package", raw_import=""),
        ]
        assert _find_cycles(edges) == []

    def test_three_node_cycle(self) -> None:
        edges = [self._edge("a", "b"), self._edge("b", "c"), self._edge("c", "a")]
        cycles = _find_cycles(edges)
        assert len(cycles) == 1
        assert len(cycles[0]) == 4  # [a, b, c, a]

    def test_no_duplicate_cycles(self) -> None:
        edges = [self._edge("a", "b"), self._edge("b", "a")]
        cycles = _find_cycles(edges)
        # Even though both nodes are starting points, cycle deduplication ensures 1
        assert len(cycles) == 1


# ---------------------------------------------------------------------------
# DependencyGraph data model
# ---------------------------------------------------------------------------


class TestDependencyGraphModel:
    def _simple_graph(self) -> DependencyGraph:
        nodes = [DGNode(id="a.py", language="Python"), DGNode(id="b.py", language="Python")]
        edges = [DGEdge(source="a.py", target="b.py", kind="local", raw_import="import b")]
        return DependencyGraph(nodes=nodes, edges=edges, unresolved={}, cycles=[])

    def test_to_dict_has_required_keys(self) -> None:
        d = self._simple_graph().to_dict()
        assert "nodes" in d
        assert "edges" in d
        assert "unresolved" in d
        assert "cycles" in d

    def test_nodes_serialized(self) -> None:
        d = self._simple_graph().to_dict()
        assert d["nodes"][0]["id"] == "a.py"
        assert d["nodes"][0]["language"] == "Python"

    def test_edges_serialized(self) -> None:
        d = self._simple_graph().to_dict()
        e = d["edges"][0]
        assert e["source"] == "a.py"
        assert e["target"] == "b.py"
        assert e["kind"] == "local"

    def test_from_dict_round_trip(self) -> None:
        g = self._simple_graph()
        restored = DependencyGraph.from_dict(g.to_dict())
        assert len(restored.nodes) == len(g.nodes)
        assert len(restored.edges) == len(g.edges)
        assert restored.nodes[0].id == "a.py"
        assert restored.edges[0].kind == "local"

    def test_from_dict_empty(self) -> None:
        g = DependencyGraph.from_dict({})
        assert g.nodes == []
        assert g.edges == []
        assert g.unresolved == {}
        assert g.cycles == []

    def test_note_field_present(self) -> None:
        d = self._simple_graph().to_dict()
        assert "_note" in d


# ---------------------------------------------------------------------------
# write_graph / load_graph round-trip
# ---------------------------------------------------------------------------


class TestWriteLoadGraph:
    def test_write_creates_file(self, tmp_path: Path) -> None:
        g = DependencyGraph(nodes=[], edges=[], unresolved={}, cycles=[])
        out = tmp_path / "dep.json"
        write_graph(g, out)
        assert out.exists()

    def test_file_is_valid_json(self, tmp_path: Path) -> None:
        _write(tmp_path / "a.py", "import os\n")
        result = scan(tmp_path)
        g = build_graph(result)
        out = tmp_path / "dep.json"
        write_graph(g, out)
        data = json.loads(out.read_text())
        assert isinstance(data, dict)

    def test_load_restores_graph(self, tmp_path: Path) -> None:
        _write(tmp_path / "pkg" / "__init__.py", "")
        _write(tmp_path / "pkg" / "utils.py", "x = 1\n")
        _write(tmp_path / "pkg" / "main.py", "from pkg.utils import x\n")
        result = scan(tmp_path)
        g = build_graph(result)
        out = tmp_path / "dep.json"
        write_graph(g, out)
        g2 = load_graph(out)
        assert len(g2.nodes) == len(g.nodes)
        assert len(g2.edges) == len(g.edges)

    def test_cycles_persisted(self, tmp_path: Path) -> None:
        _write(tmp_path / "pkg" / "__init__.py", "")
        _write(tmp_path / "pkg" / "a.py", "from pkg.b import y\n")
        _write(tmp_path / "pkg" / "b.py", "from pkg.a import x\n")
        result = scan(tmp_path)
        g = build_graph(result)
        out = tmp_path / "dep.json"
        write_graph(g, out)
        g2 = load_graph(out)
        assert len(g2.cycles) > 0


# ---------------------------------------------------------------------------
# build_graph properties
# ---------------------------------------------------------------------------


class TestBuildGraphProperties:
    def test_all_scanned_files_are_nodes(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "pass\n")
        _write(tmp_path / "README.md", "# hi\n")
        _write(tmp_path / "config.yml", "key: val\n")
        result = scan(tmp_path)
        graph = build_graph(result)
        node_ids = {n.id for n in graph.nodes}
        assert "main.py" in node_ids
        assert "README.md" in node_ids
        assert "config.yml" in node_ids

    def test_empty_repo_returns_empty_graph(self, tmp_path: Path) -> None:
        result = scan(tmp_path)
        graph = build_graph(result)
        assert graph.nodes == []
        assert graph.edges == []
        assert graph.unresolved == {}
        assert graph.cycles == []

    def test_non_code_files_have_no_edges(self, tmp_path: Path) -> None:
        _write(tmp_path / "README.md", "# hi\n")
        _write(tmp_path / "data.json", '{"key": "val"}\n')
        result = scan(tmp_path)
        graph = build_graph(result)
        assert graph.edges == []


# ---------------------------------------------------------------------------
# Scan CLI integration
# ---------------------------------------------------------------------------


class TestScanCLIIntegration:
    def test_scan_writes_dependency_graph(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "import os\n")
        result = runner.invoke(app, ["scan", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / ".contextos" / "dependency_graph.json").exists()

    def test_dependency_graph_json_valid(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "import os\n")
        runner.invoke(app, ["scan", str(tmp_path)])
        out = tmp_path / ".contextos" / "dependency_graph.json"
        data = json.loads(out.read_text())
        assert "nodes" in data
        assert "edges" in data
        assert "unresolved" in data
        assert "cycles" in data

    def test_no_index_skips_dependency_graph(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "import os\n")
        runner.invoke(app, ["scan", str(tmp_path), "--no-index"])
        assert not (tmp_path / ".contextos" / "dependency_graph.json").exists()

    def test_graph_nodes_match_scanned_files(self, tmp_path: Path) -> None:
        _write(tmp_path / "a.py", "pass\n")
        _write(tmp_path / "b.py", "pass\n")
        runner.invoke(app, ["scan", str(tmp_path)])
        data = json.loads((tmp_path / ".contextos" / "dependency_graph.json").read_text())
        node_ids = {n["id"] for n in data["nodes"]}
        assert "a.py" in node_ids
        assert "b.py" in node_ids

    def test_cycle_detected_end_to_end(self, tmp_path: Path) -> None:
        _write(tmp_path / "pkg" / "__init__.py", "")
        _write(tmp_path / "pkg" / "a.py", "from pkg.b import y\n")
        _write(tmp_path / "pkg" / "b.py", "from pkg.a import x\n")
        runner.invoke(app, ["scan", str(tmp_path)])
        data = json.loads((tmp_path / ".contextos" / "dependency_graph.json").read_text())
        assert len(data["cycles"]) > 0

    @pytest.mark.parametrize(
        "lang,filename,content",
        [
            ("Python", "app.py", "import os\nfrom pathlib import Path\n"),
            ("JS", "app.js", "import React from 'react';\n"),
            ("TS", "app.ts", "import { useState } from 'react';\n"),
        ],
    )
    def test_package_edges_appear_per_language(
        self,
        tmp_path: Path,
        lang: str,
        filename: str,
        content: str,
    ) -> None:
        _write(tmp_path / filename, content)
        result = runner.invoke(app, ["scan", str(tmp_path)])
        assert result.exit_code == 0
        data = json.loads((tmp_path / ".contextos" / "dependency_graph.json").read_text())
        pkg_targets = {e["target"] for e in data["edges"] if e["kind"] == "package"}
        assert len(pkg_targets) > 0
