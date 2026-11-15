"""
View - a small, safe template engine (Blade/Jinja-like subset). It never uses eval().

    {{ user.name }}            escaped output (dotted lookup: dict key, attribute, list index)
    {!! html !!}               raw output (only for trusted HTML)
    {% if a %}..{% elif b %}..{% else %}..{% endif %}
    {% for x in items %}..{% else %}empty{% endfor %}      (loop.index, loop.first, loop.last ...)
    {% include "partials.header" %}
    {% extends "layouts.app" %}  +  {% block content %}..{% endblock %}
    {# a comment: never rendered #}

Conditions: `x`, `not x`, or one comparison `x == "a"`, `x != 3`, `x > y` (<, >=, <=).
Callables are never invoked from a template; compute values in your controller.
"""

import html
import os
import re
from typing import Any, Dict, List

_TOKEN = re.compile(r"(\{!!.*?!!\}|\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\})", re.S)
_SEGMENT = re.compile(r"^[A-Za-z0-9_-]+$")
_FOR = re.compile(r"^for\s+([A-Za-z_]\w*)\s+in\s+(.+)$")
_COMPARE = re.compile(r"^(.+?)\s*(==|!=|>=|<=|>|<)\s*(.+)$")
_MAX_DEPTH = 25


class ViewError(Exception):
    pass


# ── parsing ─────────────────────────────────────────────────────────────────

def _parse(source: str) -> list:
    tokens = _TOKEN.split(source)
    nodes, pos, stop = _parse_nodes(tokens, 0, ())
    if stop is not None:
        raise ViewError(f"Unexpected {{% {stop} %}}")
    return nodes


def _parse_nodes(tokens: list, pos: int, until: tuple):
    """Return (nodes, next_pos, terminating_tag_content)."""
    nodes: list = []
    while pos < len(tokens):
        tok = tokens[pos]
        pos += 1
        if tok.startswith("{#"):
            continue                                   # a comment: renders nothing
        if tok.startswith("{!!"):
            nodes.append(("var", tok[3:-3].strip(), True))
        elif tok.startswith("{{"):
            nodes.append(("var", tok[2:-2].strip(), False))
        elif tok.startswith("{%"):
            body = tok[2:-2].strip()
            word = body.split(None, 1)[0] if body else ""
            if word in until:
                return nodes, pos, body
            if word == "if":
                branches, else_nodes = [], []
                cond = body[2:].strip()
                while True:
                    inner, pos, ended = _parse_nodes(tokens, pos, ("elif", "else", "endif"))
                    branches.append((cond, inner))
                    if ended is None:
                        raise ViewError("Missing {% endif %}")
                    if ended.startswith("elif"):
                        cond = ended[4:].strip()
                    elif ended == "else":
                        else_nodes, pos, ended = _parse_nodes(tokens, pos, ("endif",))
                        if ended is None:
                            raise ViewError("Missing {% endif %}")
                        break
                    else:
                        break
                nodes.append(("if", branches, else_nodes))
            elif word == "for":
                m = _FOR.match(body)
                if not m:
                    raise ViewError(f"Invalid for tag: {{% {body} %}}")
                inner, pos, ended = _parse_nodes(tokens, pos, ("else", "endfor"))
                else_nodes: list = []
                if ended is None:
                    raise ViewError("Missing {% endfor %}")
                if ended == "else":
                    else_nodes, pos, ended = _parse_nodes(tokens, pos, ("endfor",))
                    if ended is None:
                        raise ViewError("Missing {% endfor %}")
                nodes.append(("for", m.group(1), m.group(2).strip(), inner, else_nodes))
            elif word == "block":
                name = body[5:].strip()
                inner, pos, ended = _parse_nodes(tokens, pos, ("endblock",))
                if ended is None:
                    raise ViewError("Missing {% endblock %}")
                nodes.append(("block", name, inner))
            elif word in ("include", "extends"):
                m = re.match(r"""^\w+\s+(['"])(.+)\1$""", body)
                if not m:
                    raise ViewError(f"Invalid {word} tag: {{% {body} %}}")
                nodes.append((word, m.group(2)))
            else:
                raise ViewError(f"Unknown tag: {{% {body} %}}")
        elif tok:
            nodes.append(("text", tok))
    if until:
        return nodes, pos, None
    return nodes, pos, None


# ── evaluation ──────────────────────────────────────────────────────────────

def _lookup(path: str, ctx: Dict[str, Any]) -> Any:
    cur: Any = ctx
    for part in path.split("."):
        if isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur[part]
        elif isinstance(cur, (list, tuple)) and part.isdigit():
            i = int(part)
            if i >= len(cur):
                return None
            cur = cur[i]
        elif part.startswith("_"):
            return None
        else:
            cur = getattr(cur, part, None)
        if cur is None:
            return None
    return None if callable(cur) else cur


def _operand(text: str, ctx: Dict[str, Any]) -> Any:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1]
    low = text.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("none", "null"):
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return _lookup(text, ctx)


def _truthy(cond: str, ctx: Dict[str, Any]) -> bool:
    cond = cond.strip()
    if cond.startswith("not "):
        return not _truthy(cond[4:], ctx)
    m = _COMPARE.match(cond)
    if m:
        left, op, right = _operand(m.group(1), ctx), m.group(2), _operand(m.group(3), ctx)
        try:
            return {"==": left == right, "!=": left != right,
                    ">": left > right, "<": left < right,
                    ">=": left >= right, "<=": left <= right}[op]
        except TypeError:
            return False
    return bool(_operand(cond, ctx))


def _blocks_of(nodes: list, found: Dict[str, list] = None) -> Dict[str, list]:
    found = {} if found is None else found
    for node in nodes:
        if node[0] == "block":
            found[node[1]] = node[2]
            _blocks_of(node[2], found)
    return found


class ViewFactory:
    """Finds, parses (with caching) and renders templates under `views_path`."""

    def __init__(self, views_path: str):
        self.views_path = views_path
        self._cache: Dict[str, tuple] = {}

    def exists(self, name: str) -> bool:
        try:
            return os.path.isfile(self._path(name))
        except ViewError:
            return False

    def render(self, name: str, data: dict = None) -> str:
        return self._render_template(name, dict(data or {}), {}, 0)

    # ── internals ───────────────────────────────────────────────────────────

    def _path(self, name: str) -> str:
        segments = name.split(".")
        if not all(_SEGMENT.match(s) for s in segments):
            raise ViewError(f"Invalid view name: {name!r}")
        return os.path.join(self.views_path, *segments) + ".html"

    def _load(self, name: str) -> list:
        path = self._path(name)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            raise ViewError(f"View [{name}] not found.") from None
        cached = self._cache.get(path)
        if cached and cached[0] == mtime:
            return cached[1]
        with open(path, encoding="utf-8") as f:
            nodes = _parse(f.read())
        self._cache[path] = (mtime, nodes)
        return nodes

    def _render_template(self, name: str, ctx: dict, blocks: dict, depth: int) -> str:
        if depth > _MAX_DEPTH:
            raise ViewError("View nesting too deep (circular include/extends?).")
        nodes = self._load(name)
        extends = next((n for n in nodes if n[0] == "extends"), None)
        if extends:
            merged = {**_blocks_of(nodes), **blocks}          # child blocks win
            return self._render_template(extends[1], ctx, merged, depth + 1)
        return self._render_nodes(nodes, ctx, blocks, depth)

    def _render_nodes(self, nodes: List[tuple], ctx: dict, blocks: dict, depth: int) -> str:
        out: List[str] = []
        for node in nodes:
            kind = node[0]
            if kind == "text":
                out.append(node[1])
            elif kind == "var":
                value = _lookup(node[1], ctx)
                text = "" if value is None else str(value)
                out.append(text if node[2] else html.escape(text, quote=True))
            elif kind == "if":
                for cond, body in node[1]:
                    if _truthy(cond, ctx):
                        out.append(self._render_nodes(body, ctx, blocks, depth))
                        break
                else:
                    out.append(self._render_nodes(node[2], ctx, blocks, depth))
            elif kind == "for":
                _, var, path, body, else_nodes = node
                items = _lookup(path, ctx)
                items = list(items) if isinstance(items, (list, tuple, set, dict)) or hasattr(items, "__iter__") and not isinstance(items, (str, bytes)) else []
                if not items:
                    out.append(self._render_nodes(else_nodes, ctx, blocks, depth))
                total = len(items)
                for i, item in enumerate(items):
                    inner = {**ctx, var: item, "loop": {
                        "index": i + 1, "index0": i, "first": i == 0,
                        "last": i == total - 1, "length": total}}
                    out.append(self._render_nodes(body, inner, blocks, depth))
            elif kind == "include":
                out.append(self._render_template(node[1], ctx, {}, depth + 1))
            elif kind == "block":
                body = blocks.get(node[1], node[2])
                out.append(self._render_nodes(body, ctx, blocks, depth))
            # "extends" nodes render nothing by themselves
        return "".join(out)
