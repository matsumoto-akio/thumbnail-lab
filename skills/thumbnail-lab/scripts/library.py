"""Bridge between an image-capable agent and the local comparison app."""
import argparse
import base64
import json
from pathlib import Path
import urllib.request
import urllib.parse
import uuid
from datetime import datetime, timezone


def request(url, data=None):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost") or parsed.username or parsed.password:
        raise ValueError("Use the local Thumbnail Lab server URL")
    req = urllib.request.Request(url.rstrip("/") + "/api/state", headers={"Content-Type": "application/json", "X-Thumbnail-Lab": "1"}, data=json.dumps(data).encode() if data is not None else None)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def channel_for(state, channel_id):
    matches = [c for c in state["channels"] if c["id"] == channel_id or c["name"] == channel_id]
    if len(matches) != 1:
        raise ValueError("Specify one exact channel id or unique name")
    return matches[0]


def image_file(path):
    data = Path(path).read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime, ext = "image/png", ".png"
    elif data.startswith(b"\xff\xd8\xff"):
        mime, ext = "image/jpeg", ".jpg"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        mime, ext = "image/webp", ".webp"
    else:
        raise ValueError("Use PNG, JPEG or WebP images")
    if len(data) > 4 * 1024 * 1024:
        raise ValueError("Each image must be at most 4 MB")
    return {"id": str(uuid.uuid4()), "name": Path(path).stem + ext, "data": "data:" + mime + ";base64," + base64.b64encode(data).decode()}


def context(channel, output):
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=True)
    refs = [r for r in channel["refs"] if r.get("favorite")][:5]
    if not refs:
        raise ValueError("No selected references; select or register approved references first")
    paths = []
    for index, ref in enumerate(refs):
        header, encoded = ref["data"].split(",", 1)
        ext = {"data:image/png;base64": ".png", "data:image/jpeg;base64": ".jpg", "data:image/webp;base64": ".webp"}[header]
        target = folder / ("reference-" + str(index + 1) + ext)
        target.write_bytes(base64.b64decode(encoded, validate=True))
        paths.append(str(target.resolve()))
    memories = [{"topic": b["topic"], "chosen": b["adopted"] + 1, "reason": b["reason"]} for b in channel["batches"] if b.get("adopted") is not None and b.get("remember") and b.get("reason", "").strip()][-20:]
    return {"channel": channel["id"], "name": channel["name"], "rules": channel.get("rules", ""), "references": paths, "memories": memories}


def import_batch(channel, args):
    if any(b["id"] == args.batch_id for b in channel["batches"]):
        raise ValueError("Batch id already registered; inspect existing batch instead of duplicating it")
    images = [image_file(p) for p in args.images]
    brief = {"id": args.batch_id, "topic": args.topic, "headline": args.headline, "notes": "", "created": datetime.now(timezone.utc).isoformat(), "images": images, "adopted": None, "reason": "", "remember": True, "prompt": "スキルで生成・登録", "referenceIds": [r["id"] for r in channel["refs"] if r.get("favorite")][:5]}
    return {**channel, "batches": [*channel["batches"], brief]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8769")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    ctx = commands.add_parser("context")
    ctx.add_argument("--channel", required=True)
    ctx.add_argument("--out", required=True)
    imp = commands.add_parser("import")
    imp.add_argument("--channel", required=True)
    imp.add_argument("--batch-id", required=True)
    imp.add_argument("--topic", required=True)
    imp.add_argument("--headline", default="")
    imp.add_argument("--images", nargs=5, required=True)
    args = parser.parse_args()
    snapshot = request(args.url)
    state = snapshot["data"]
    if args.command == "list":
        result = [{"id": c["id"], "name": c["name"], "references": len(c["refs"])} for c in state["channels"]]
    else:
        channel = channel_for(state, args.channel)
        if args.command == "context":
            result = context(channel, args.out)
        else:
            updated = import_batch(channel, args)
            data = {**state, "active": channel["id"], "channels": [updated if c["id"] == channel["id"] else c for c in state["channels"]]}
            result = request(args.url, {"version": snapshot["version"], "data": data})
            result = {**result, "batch": args.batch_id, "compare": args.url.rstrip("/") + "/#compare"}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
