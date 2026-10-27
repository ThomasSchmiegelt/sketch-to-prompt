"""sketch-to-prompt: rotate a 3D part in the browser, draw lines on it, add text, hand it to an AI as a prompt.

    sketch-to-prompt <folder with STL files> [--port 8765] [--out sketches] [--lang de|en]

Every subfolder with STL files is one model, every STL file in it one part (toggle, translucent).
STL files directly in <folder> are models of their own. "Send" writes <out>/<time>/ with
  sketch.png   the view with your lines
  sketch.json  text, camera, every line as screen points AND as 3D points on the part (+ R, phi about the z axis)
  prompt.md    the same as readable text for any AI chat (attach sketch.png)
and <out>/latest.txt with the path of the newest sketch (an AI agent can wait for this file).
Standard library only; serves on 127.0.0.1.
"""
import argparse, base64, json, math, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def find_models(root: Path) -> dict:
    """{model name: [STL paths]}"""
    models = {}
    for p in sorted(root.glob("*.stl")) + sorted(root.glob("*.STL")):
        models[p.stem] = [p]
    for d in sorted(x for x in root.iterdir() if x.is_dir()):
        parts = sorted(d.glob("*.stl")) + sorted(d.glob("*.STL"))
        if parts:
            models[d.name] = parts
    return models


def length(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def prompt_markdown(d: dict) -> str:
    """Readable prompt: text, view, lines with start/end point, length, how much of it lies on the part."""
    k = d.get("camera", {}); u = d.get("unit", "")
    f = lambda v: "(" + ", ".join(f"{x:.3f}" for x in v) + ")"
    out = [f"# Sketch on model '{d.get('model')}'", "", d.get("text", "").strip() or "(no text)", "",
           "## View", f"- camera at {f(k.get('position', [0, 0, 0]))} looking at {f(k.get('target', [0, 0, 0]))}, "
           f"up {f(k.get('up', [0, 0, 1]))}, field of view {k.get('fov_deg', 0):.0f} deg",
           f"- visible parts: {', '.join(d.get('parts_visible', []))}; translucent: {', '.join(d.get('parts_translucent', [])) or 'none'}",
           f"- coordinates in model units ({u or 'as in the STL file'}); R and phi about the z axis", "",
           "## Lines (see sketch.png; numbers are drawn at the start of each line)"]
    for l in d.get("lines", []):
        p = l["points"]; xyz = [q["xyz"] for q in p]
        on = sum(q["on_part"] for q in p)
        out += [f"- **Line {l['nr']}** ({l['color']}, {len(p)} points, {on}/{len(p)} on the part, length {length(xyz):.3f}): "
                f"start {f(xyz[0])} [R {p[0]['R']:.3f}, phi {p[0]['phi_deg']:.2f} deg, {p[0].get('part') or 'free'}], "
                f"end {f(xyz[-1])} [R {p[-1]['R']:.3f}, phi {p[-1]['phi_deg']:.2f} deg, {p[-1].get('part') or 'free'}]"]
    if not d.get("lines"):
        out.append("- none")
    out += ["", "All points are in sketch.json."]
    return "\n".join(out) + "\n"


def make_handler(models: dict, out: Path, lang: str):
    page = resources.files("sketch_to_prompt").joinpath("static/index.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def reply(self, code, data: bytes, ctype: str):
            self.send_response(code); self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

        def do_GET(self):
            u = urlparse(self.path); q = parse_qs(u.query)
            if u.path == "/":
                return self.reply(200, page, "text/html; charset=utf-8")
            if u.path == "/config":
                return self.reply(200, json.dumps({"lang": lang, "models": {m: [p.name for p in ps] for m, ps in models.items()}}).encode(),
                                  "application/json")
            if u.path == "/part":
                m, name = q.get("model", [""])[0], q.get("part", [""])[0]
                for p in models.get(m, []):
                    if p.name == name:
                        return self.reply(200, p.read_bytes(), "application/octet-stream")
            self.reply(404, b"not found", "text/plain")

        def do_POST(self):
            if self.path != "/sketch":
                return self.reply(404, b"", "text/plain")
            d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            o = out / time.strftime("%Y-%m-%d_%H-%M-%S"); o.mkdir(parents=True, exist_ok=True)
            img = d.pop("image", "")
            if img.startswith("data:image/png;base64,"):
                (o / "sketch.png").write_bytes(base64.b64decode(img.split(",", 1)[1]))
            (o / "sketch.json").write_text(json.dumps(d, indent=1, ensure_ascii=False))
            (o / "prompt.md").write_text(prompt_markdown(d))
            (out / "latest.txt").write_text(str(o.resolve()) + "\n")
            print("SKETCH", o, flush=True)
            self.reply(200, json.dumps({"folder": str(o)}).encode(), "application/json")

    return Handler


def main(argv=None):
    ap = argparse.ArgumentParser(description="Draw on a 3D part in the browser and hand the sketch to an AI.")
    ap.add_argument("folder", type=Path, help="folder with STL files (subfolder = model with several parts)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--out", type=Path, default=Path("sketches"), help="where sketches are written")
    ap.add_argument("--lang", choices=["de", "en"], default="de")
    a = ap.parse_args(argv)
    models = find_models(a.folder)
    if not models:
        raise SystemExit(f"No STL files in {a.folder}")
    a.out.mkdir(parents=True, exist_ok=True)
    print(f"{len(models)} model(s) from {a.folder}; sketches go to {a.out.resolve()}")
    print(f"Open http://127.0.0.1:{a.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(models, a.out, a.lang)).serve_forever()


if __name__ == "__main__":
    main()
