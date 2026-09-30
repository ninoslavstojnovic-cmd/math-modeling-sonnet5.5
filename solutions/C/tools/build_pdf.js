// 论文.md -> 论文.pdf（markdown-it + KaTeX + 无头Chromium）。依赖：npm i katex markdown-it；用法：NODE_PATH=<node_modules> node tools/build_pdf.js
const fs = require('fs'), path = require('path'), { execFileSync } = require('child_process');
const katex = require('katex'), MarkdownIt = require('markdown-it');
const root = path.resolve(__dirname, '..');
let src = fs.readFileSync(path.join(root, '论文.md'), 'utf8');
const maths = [];
const stash = (tex, display) => { maths.push(katex.renderToString(tex, { displayMode: display, throwOnError: false })); return `@@M${maths.length - 1}@@`; };
src = src.replace(/\$\$([\s\S]+?)\$\$/g, (_, t) => stash(t, true)).replace(/\$([^$\n]+?)\$/g, (_, t) => stash(t, false));
const md = new MarkdownIt({ html: true, linkify: false });
let html = md.render(src).replace(/@@M(\d+)@@/g, (_, i) => maths[+i]);
const katexDir = path.dirname(require.resolve('katex/package.json'));
const doc = `<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="file://${katexDir}/dist/katex.min.css"><style>
@page{size:A4;margin:18mm 16mm}body{font-family:"WenQuanYi Zen Hei","Noto Sans CJK SC",sans-serif;font-size:10.5pt;line-height:1.6;color:#111}
h1{text-align:center;font-size:18pt}h2{font-size:14pt;border-bottom:1px solid #999;padding-bottom:2px;margin-top:1.2em}h3{font-size:12pt}
table{border-collapse:collapse;margin:8px 0;font-size:9pt}th,td{border:1px solid #888;padding:2px 6px}img{max-width:100%}code{font-size:9pt}pre{background:#f4f4f4;padding:6px;font-size:8.5pt;white-space:pre-wrap}
.katex-display{overflow-x:auto;overflow-y:hidden}</style></head><body>${html}</body></html>`;
const out = path.join(root, '.paper.html'); fs.writeFileSync(out, doc);
const chrome = process.env.CHROME || '/opt/pw-browsers/chromium';
execFileSync(chrome, ['--headless', '--no-sandbox', '--disable-gpu', '--allow-file-access-from-files', '--no-pdf-header-footer', `--print-to-pdf=${path.join(root, '论文.pdf')}`, `file://${out}`], { stdio: 'inherit' });
fs.unlinkSync(out);
