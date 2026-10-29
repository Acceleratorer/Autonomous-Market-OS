# Web

`public/` holds the existing static, read-only preview and its hosting files.
It contains no portfolio data or connection to the local gateway. The legacy
copy under `docs/hosting/market-os/` is retained for existing consumers;
`python scripts/build_web_artifact.py --check` checks that both copies match.

Build a local static artifact with `python scripts/build_web_artifact.py
--output <new-directory>`. The U5.2 contract checks exact file-set parity and
the no-script/no-network/no-credential boundary. Add `--manifest <path>` for a
deterministic handoff manifest. Deployment and a connected web application
remain separate gates. U5.8 adds `next-operator/`, a local-only Next.js
application using TypeScript, React, Node.js, and Tailwind CSS. It is a separate
read-only surface; it does not replace the disconnected static preview or the
compatibility HTML shell.

To use the local Next.js operator, start the existing gateway from the
repository root in one terminal:

```powershell
python -m apps.gateway --host 127.0.0.1 --port 8787
```

Then install and run the web app from `apps/web/next-operator` in another:

```powershell
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`. The app server is bound to loopback and reads
only the Python gateway at `127.0.0.1:8787`. The Node/Next surface owns no
portfolio accounting, risk, recovery, or mutation logic. Node.js 20.9 or newer
is required.

The CI artifact contains `market-os/` plus the sidecar
`market-os.manifest.json`; the manifest is kept outside the exact three-file
static directory.

`operator/` holds the compatibility local GET-only shell. Its product-facing assets are
`index.html`, `operator.js`, and `operator.css`; the gateway keeps the former
`app.js` and `styles.css` URLs as compatibility aliases.
