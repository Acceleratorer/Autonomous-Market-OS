# Autonomous Market OS — Deployment Options Report

**Ngày lập:** 2026-10-29
**Phạm vi:** `D:\\Code\\Github\\HKUDS`
**Repository được phát hiện:** `Autonomous-Market-OS`
**Remote:** `https://github.com/Acceleratorer/Autonomous-Market-OS.git`
**Mục đích:** tài liệu tham khảo triển khai; báo cáo này không thực hiện deploy.

## 1. Kết luận điều hành

Project có ba bề mặt và phải triển khai tách biệt:

| Bề mặt | Công nghệ | Target phù hợp | Kết luận |
|---|---|---|---|
| Static preview | HTML/CSS, đúng 3 file | DirectAdmin/shared hosting | Sẵn sàng về artifact; chưa public thành công |
| Local operator | Next.js 16, React 19, Node.js >=20.9 | VPS/PaaS có Node runtime | Chỉ loopback; chưa đủ điều kiện public |
| Gateway | Python 3.11+, HTTP, file-backed state | VPS/container/private service | Có local deployment probe; còn thiếu production controls |

Khuyến nghị:

1. Public preview: deploy `apps/web/public/` vào `/market-os/`.
2. Operator thật: chạy Next.js và Python gateway trên VPS hoặc PaaS.
3. Nếu giữ DirectAdmin: chỉ dùng nó cho static preview; operator đặt ở host khác.
4. Không expose Python gateway trực tiếp ra Internet.

## 2. Phạm vi và snapshot đã kiểm tra

Trong `D:\\Code\\Github\\HKUDS` hiện chỉ có một Git repository thực tế:

```text
D:\\Code\\Github\\HKUDS\\Autonomous-Market-OS
```

Các thư mục workspace/output khác không phải application repository độc lập. Nếu checkout thêm repository con sau này, cần inventory lại trước khi chọn target.

Snapshot:

- Branch: `main`
- HEAD lúc lập báo cáo: `f356e439694f9cc6e0cfca37261e4cebcc8b3697`
- Commit gần nhất: `docs: record U5.23 CI closeout`
- Worktree đang có tracked changes và nhiều scratch/untracked files.
- Không dùng `git add .`, `git clean`, `git reset --hard` hoặc `git checkout --` khi chuẩn bị deploy.

## 3. Kiến trúc hiện tại

```text
GitHub Actions
  test -> build -> immutable artifact -> staging -> verify -> promote
                                                       |
                                                       v
DirectAdmin /accel.io.vn/market-os/
  index.html + .htaccess + DEPLOYMENT.txt

Private operator path:
Browser -> Next.js :3000 -> Python gateway :8787 -> private state
```

### 3.1 Static preview

Canonical source:

```text
apps/web/public/
├── index.html
├── .htaccess
└── DEPLOYMENT.txt
```

Builder: `scripts/build_web_artifact.py`.

Builder kiểm tra:

- đúng 3 file;
- parity với `docs/hosting/market-os/`;
- không có script, form, network API, credential marker hoặc external URL trong HTML;
- artifact deterministic;
- manifest SHA-256.

Artifact là synthetic, paper-only, read-only và không có portfolio state, API, credentials hay mutation route.

### 3.2 Next.js operator

Location: `apps/web/next-operator/`.

Commands:

```text
npm ci
npm run typecheck
npm run build
npm run start
```

Yêu cầu Node.js >=20.9. App hiện bind `127.0.0.1:3000` và đọc Python gateway tại `127.0.0.1:8787`. Đây là local/private shape, không phải public production deployment.

### 3.3 Python gateway

Gateway sở hữu domain/API và persistence. Connected production cần:

- service identity/ACL riêng;
- private state root;
- backup/restore đã diễn tập;
- CPU/RAM/disk limits;
- request/provider/shutdown timeouts;
- structured logs, retention và alerting;
- authenticated subject identity;
- portfolio authorization/allowlist;
- session expiry/revocation;
- rate limits và request-size limits;
- direct-origin protection.

## 4. Phương án A — Static preview trên DirectAdmin

### 4.1 Target

```text
Local:  apps/web/public/
Remote: /domains/accel.io.vn/public_html/market-os
URL:    https://accel.io.vn/market-os/
```

### 4.2 Workflow có sẵn

Files:

```text
.github/workflows/deploy-market-os.yml
scripts/deploy_market_os_directadmin.sh
```

Flow:

1. Chạy static contract test.
2. Kiểm tra source/legacy parity.
3. Build artifact theo commit SHA.
4. Upload archive lên DirectAdmin.
5. Extract vào staging ngoài `public_html`.
6. Kiểm tra đủ `index.html`, `.htaccess`, `DEPLOYMENT.txt`.
7. Đưa release hiện tại vào rollback slot.
8. Promote staging.
9. So sánh SHA-256 HTML production với artifact.
10. Kiểm tra các route cũ: `/`, `/waifu`, `/wuwa-map`.
11. Nếu verify fail, restore release trước.

Rollback slot:

```text
/domains/accel.io.vn/.market-os-rollback
```

### 4.3 GitHub Secrets cần có

Repository: `Acceleratorer/Autonomous-Market-OS`.

```text
DIRECTADMIN_HOST
DIRECTADMIN_USER
DIRECTADMIN_PASSWORD
DIRECTADMIN_CA_BUNDLE
```

Chỉ lưu giá trị trong GitHub Secrets; không ghi password vào report, source, workflow log hoặc `.env` tracked.

### 4.4 Hosting evidence

Đã kiểm tra DirectAdmin account của `accel.io.vn`:

- Có DirectAdmin Evolution, File Manager và Terminal.
- Disk observed: khoảng `623.5 MB / 1 GB`.
- Databases: `0 / 1`.
- `node --version`: `node: command not found`.
- `npm --version`: `npm: command not found`.
- Không thấy Node.js Application Manager.
- `https://accel.io.vn/market-os/` trả HTTP 404 tại thời điểm kiểm tra.

Kết luận: host này phù hợp để serve static files, không phù hợp để chạy Next.js Node process.

### 4.5 TLS blocker

DirectAdmin API host:

```text
svh-22298.azdigihost.com:2222
```

OpenSSL quan sát chain cũ:

```text
leaf: CN=*.azdigihost.com
notAfter: May 29 23:59:59 2026 GMT
Verify return code: 10 (certificate has expired)
```

Workflow hiện giữ certificate verification và không dùng `--insecure`. Vì vậy static deploy phải chờ hosting gia hạn certificate hoặc cung cấp endpoint/certificate hợp lệ. Không dùng leaf pin hết hạn làm workaround.

### 4.6 Runbook khi blocker được xử lý

```text
1. Hosting gia hạn SSL DirectAdmin.
2. Xác minh lại chain bằng OpenSSL/curl.
3. Tạo đủ 4 GitHub Secrets.
4. Chạy local checks.
5. Sau khi local milestones đóng và hosting prerequisites sẵn sàng, chạy `workflow_dispatch` trên `main`; push thường không deploy.
6. Theo dõi quality job.
7. Theo dõi deploy job.
8. Kiểm tra /market-os/ và preserved routes.
9. Nếu promotion fail, kiểm tra automatic rollback.
```

Static deploy không cần Node.js trên DirectAdmin; Node.js trong GitHub runner chỉ phục vụ test/build.

## 5. Phương án B — Next.js + Python trên VPS

Đây là phương án phù hợp nhất cho operator thật:

```text
HTTPS :443
  -> Caddy/Nginx
  -> Next.js :3000
  -> Python gateway :8787
  -> private state volume
```

Dùng systemd hoặc Docker Compose để có restart policy, healthcheck và resource limits.

Shape build/runtime:

```bash
cd apps/web/next-operator
npm ci
npm run typecheck
npm run build

python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m apps.gateway --host 127.0.0.1 --port 8787
npm run start
```

Đây là deployment shape tham khảo, không phải lệnh đã chạy production.

URL options:

- `operator.accel.io.vn`: routing đơn giản hơn.
- `accel.io.vn/market-os`: cần Next.js `basePath`, asset rewrite và deep-link tests.

Không được:

- expose port 8787;
- bind gateway public khi chưa có auth boundary;
- đưa state/credentials vào browser bundle;
- coi Cloudflare Access/VPN là thay thế cho application authorization.

## 6. Phương án C — PaaS/container host

Render, Railway, Fly.io hoặc VPS managed có thể chạy:

| Thành phần | Cách chạy |
|---|---|
| Next.js | Web service, Node >=20.9 |
| Python gateway | Private service/worker |
| State | Persistent disk hoặc database phù hợp |
| Ingress | HTTPS platform/reverse proxy |
| Deploy | GitHub Actions/provider integration |

PaaS giải quyết process runtime tốt hơn shared hosting nhưng không tự giải quyết auth, authorization, storage isolation, backup hay rollback.

## 7. Phương án D — Hybrid

```text
accel.io.vn/market-os/  -> DirectAdmin static preview
operator.accel.io.vn    -> VPS/PaaS private Next.js
Python gateway           -> cùng VPS hoặc private backend
```

Đây là phương án ít ảnh hưởng site hiện tại nhất. Cần kiểm soát DNS, auth, identity propagation và smoke test riêng cho từng origin.

## 8. CI/CD lifecycle chuẩn

### Pull request

```text
PR
├─ locked dependency install
├─ unit/integration tests
├─ static contract/parity
├─ typecheck/build
├─ security/secret scan
├─ artifact manifest/hash
└─ review gate
```

Không deploy production từ PR.

### Static preview artifact and manual promotion

```text
main push
└─ CI tests/build and packages the disconnected static artifact; no deployment

workflow_dispatch on main
├─ quality checks and immutable SHA artifact
├─ validate deployment prerequisites/secrets
├─ stage outside public_html
├─ health/smoke/route checks
├─ explicit production promotion
├─ served artifact hash verification
└─ one rollback release retained
```

### Rollback

Trigger khi:

- production HTTP status sai;
- served hash không khớp artifact;
- route cũ bị ảnh hưởng;
- health/readiness/smoke fail;
- process không start hoặc không healthy.

Rollback thủ công:

```text
1. Ghi lại release SHA lỗi.
2. Dừng promotion/concurrency.
3. Restore rollback slot hoặc image trước.
4. Chạy health/smoke/hash checks.
5. Ghi incident/root cause.
6. Chỉ mở promotion sau regression fix.
```

State không được rollback bằng cách rewrite event history. Rollback code/image và restore state snapshot có kiểm soát.

## 9. Readiness matrix

| Gate | Static DirectAdmin | Next.js/Python private host |
|---|---:|---:|
| Deterministic artifact | Đạt | Đạt một phần |
| Local tests | Đạt | Đạt local; cần connected tests |
| Node trên target | Không cần | DirectAdmin không đạt |
| Python trên target | Không cần | Cần >=3.11 + supervisor |
| TLS | DirectAdmin certificate đang blocker | Cần certificate hợp lệ |
| Authentication | Không cần cho static | Chưa đạt |
| Authorization | Không cần cho static | Chưa đạt |
| Storage isolation | Không có state | Chưa đạt |
| Resource limits | Không cần | Chưa cấu hình production |
| Timeouts | Không cần | Cần hoàn thiện |
| Structured logs | Deploy output có | Cần sink/retention/alerting |
| Backup/restore | Artifact rollback có | Cần state drill |
| Rollback | Có một slot | Cần image/code + state policy |
| Public approval | Chưa deploy | Chưa được phép |

## 10. Reusable checklist

### Chọn target

- [ ] Static hay connected operator?
- [ ] URL/path/subdomain?
- [ ] Có persistence không?
- [ ] Node/Python/process manager có trên target không?
- [ ] Identity/authentication/authorization?
- [ ] Backup, rollback, log retention?

### Static deploy

- [ ] `python scripts/build_web_artifact.py --check`
- [ ] `python -m pytest -q market_os/tests/test_app_surfaces.py`
- [ ] `npx --yes tsx tests/market-os-readonly-dashboard.test.ts`
- [ ] DirectAdmin certificate còn hạn
- [ ] Đủ 4 GitHub Secrets
- [ ] Không có secret trong diff/log
- [ ] Không stage scratch/unrelated files
- [ ] Production hash và preserved routes pass

### Connected deploy

- [ ] Auth subject đã chọn và test
- [ ] Identity assertion verify từ ingress đến Python
- [ ] Portfolio allowlist/storage isolation
- [ ] Session expiry/revocation
- [ ] Direct-origin protection
- [ ] Rate/request-size/concurrency limits
- [ ] Service identity/ACL riêng
- [ ] Staging smoke/health
- [ ] Backup/restore drill
- [ ] Rollback drill

## 11. File tham chiếu

- Static source: `apps/web/public/`
- Static builder: `scripts/build_web_artifact.py`
- Deploy workflow: `.github/workflows/deploy-market-os.yml`
- Deploy script: `scripts/deploy_market_os_directadmin.sh`
- Next operator: `apps/web/next-operator/`
- Gateway docs: `apps/gateway/README.md`
- Static readiness: `docs/U5.2-STATIC-DEPLOYMENT-READINESS.md`
- Connected contract: `docs/U5.5-AUTHENTICATED-CONNECTED-WEB-CONTRACT.md`
- Deployment matrix: `docs/U5.7-WEB-STACK-DEPLOYMENT-MATRIX.md`
- DirectAdmin ADR: `docs/decisions/ADR-0046-directadmin-static-market-os-deployment.md`
- Local review: `docs/DEPLOYMENT-REVIEW.md`
- Probe: `market_os/deployment_probe.py`
- CI: `.github/workflows/ci.yml`
- Security: `.github/workflows/security.yml`

## 12. Report state

```text
Deployment performed: NO
DNS changed: NO
DirectAdmin files changed: NO
Node process created: NO
GitHub Secrets created: NO
Commit created by this report: NO
Push performed by this report: NO
```

Static preview là phương án gần production nhất về mặt code nhưng đang bị chặn bởi TLS DirectAdmin. Next.js operator bị chặn bởi việc hosting không có Node/npm và bởi các gate authentication/authorization/operations. Khi blocker thay đổi, dùng report này làm runbook; không suy luận deploy thành công chỉ vì build local pass.
