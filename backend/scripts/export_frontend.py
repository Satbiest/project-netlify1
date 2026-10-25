"""Render public UI assets for Netlify. This never reads server settings/.env."""
import argparse
from pathlib import Path
import shutil
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

BACKEND = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = BACKEND.parent / 'frontend' / 'public'
PUBLIC_ASSETS = ('static/css/app.css', 'static/js/app.js', 'static/favicon.svg', 'data/demo.json')


def build(output: Path = DEFAULT_OUTPUT) -> Path:
    environment = Environment(loader=FileSystemLoader(str(BACKEND / 'templates')),
        autoescape=select_autoescape(['html']), undefined=StrictUndefined)
    html = environment.get_template('index.html').render(
        static_frontend=True, demo_enabled=True, max_upload_mb=5, max_job_chars=12000)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'index.html').write_text(html, encoding='utf-8')
    for relative in PUBLIC_ASSETS:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(BACKEND / relative, target)
    (output / '_headers').write_text(
        '/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: same-origin\n'
        '  X-Frame-Options: SAMEORIGIN\n/config.js\n  Cache-Control: no-cache\n'
        '/static/js/app.js\n  Cache-Control: no-cache\n', encoding='utf-8')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(f'Public frontend exported: {build(args.output)}')
