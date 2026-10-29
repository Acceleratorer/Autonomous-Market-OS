import "server-only";

const LOCAL_API_PORT = process.env.MARKET_OS_API_PORT ?? "8787";
if (!/^[1-9]\d{0,4}$/.test(LOCAL_API_PORT) || Number(LOCAL_API_PORT) > 65535) {
  throw new Error("MARKET_OS_API_PORT must be a valid local TCP port");
}
const LOCAL_API_ORIGIN = `http://127.0.0.1:${LOCAL_API_PORT}`;
const PORTFOLIO_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const DATASET_REVISION_PATTERN = /^btc-history-(?:[0-9a-f]{20}|manifest-[0-9a-f]{20})$/;
const BTC_DATASET_ONLY_PATTERN = /^btc-history-[0-9a-f]{20}$/;
const MANIFEST_ID_PATTERN = /^btc-history-manifest-[0-9a-f]{20}$/;
const DECIMAL_PATTERN = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/;
const MAX_JS_DATE_TIME_MS = 8_640_000_000_000_000;

type JsonObject = Record<string, unknown>;

export type LocalApiErrorKind = "unavailable" | "missing" | "rejected" | "invalid";

export class LocalApiError extends Error {
  constructor(readonly kind: LocalApiErrorKind) {
    super(kind);
    this.name = "LocalApiError";
  }
}

export type PortfolioCatalogEntry = {
  portfolioId: string;
  mode: "isolated" | "shared";
  memberCount: number;
  openOrders: number;
};

export type PortfolioCatalogPage = {
  portfolios: PortfolioCatalogEntry[];
  page: {
    limit: number;
    afterPortfolioId: string | null;
    hasMore: boolean;
    nextAfterPortfolioId: string | null;
    skippedCount: number;
  };
};

export type BtcHistoryDataset = {
  datasetRevision: string;
  symbol: string;
  venue: string;
  interval: string;
  canonicalFingerprint: string;
  candleCount: number;
  firstOpenTimeMs: number;
  lastCloseTimeMs: number;
};

export type BtcHistoryDatasetPage = {
  datasets: BtcHistoryDataset[];
  page: {
    limit: number;
    afterDatasetRevision: string | null;
    hasMore: boolean;
    nextAfterDatasetRevision: string | null;
  };
};

export type BtcHistoryCandle = {
  openTimeMs: number;
  closeTimeMs: number;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
};

export type BtcHistoryCandlePage = {
  dataset: BtcHistoryDataset;
  candles: BtcHistoryCandle[];
  page: {
    limit: number;
    afterOpenTimeMs: number | null;
    hasMore: boolean;
    nextAfterOpenTimeMs: number | null;
  };
};

export type BtcIngestionManifestSummary = {
  manifestId: string;
  datasetRevision: string;
  runId: string;
  rawFingerprint: string;
  manifestSha256: string;
  requestedStartMs: number;
  requestedEndMsExclusive: number;
  networkRequests: number;
};

export type BtcIngestionManifestPage = {
  datasetRevision: string;
  manifests: BtcIngestionManifestSummary[];
  page: {
    limit: number;
    afterManifestId: string | null;
    hasMore: boolean;
    nextAfterManifestId: string | null;
  };
};

export type BtcIngestionManifest = BtcIngestionManifestSummary & {
  schema: string;
  apiVersion: string;
  contractVersion: string;
  symbol: string;
  venue: string;
  interval: string;
  sourceIdentity: string;
  endpointClass: string;
  endpointHost: string | null;
  observedStartMs: number | null;
  observedEndMsExclusive: number | null;
  sourceTimestampMin: string | null;
  sourceTimestampMax: string | null;
  receiptTimestampMin: string | null;
  receiptTimestampMax: string | null;
  availabilityTimestampMax: string | null;
  canonicalizationTimestamp: string;
  canonicalFingerprint: string;
  outcomeFingerprint: string;
  canonicalCandleCount: number;
  rawRecordCount: number;
  outcomeCounts: Record<string, number>;
  rawPageCount: number;
  gapCount: number;
  parentRevisionCount: number;
  parquetSha256: string;
  packageVersions: Record<"duckdb" | "pyarrow", string>;
  pythonVersion: string;
};

export type BtcIngestionOutcome = {
  outcomeIndex: number;
  rawPageSha256: string;
  rowIndex: number;
  sourceRecordFingerprint: string;
  openTimeMs: number | null;
  status: string;
  reason: string | null;
  reasonTruncated: boolean;
  acceptedCanonical: boolean;
};

export type BtcIngestionGap = { startTimeMs: number; endTimeMs: number };

export type BtcIngestionProvenance = {
  rawPageSha256: string;
  rowIndex: number;
  sourceRecordFingerprint: string;
  payloadBytes: number;
  payloadPreview: string;
  payloadTruncated: boolean;
};

export type BtcIngestionRecordPage<T, Cursor> = {
  datasetRevision: string;
  manifestId: string;
  totalCount: number;
  records: T[];
  page: {
    limit: number;
    after: Cursor | null;
    hasMore: boolean;
    nextAfter: Cursor | null;
  };
};

export type BtcResearchScore = {
  status: "measured" | "unavailable";
  n: number;
  logLoss: number | null;
  brier: number | null;
  accuracy: number | null;
};

export type BtcB2RunSummary = {
  engine: "b2";
  runId: string;
  datasetRevision: string;
  sampleCount: number;
  replayFingerprint: string;
  artifactCount: number;
  featureFingerprint: string;
  labelFingerprint: string;
  baselines: string[];
};

export type BtcB3RunSummary = {
  engine: "b3";
  runId: string;
  datasetRevision: string;
  sampleCount: number;
  replayFingerprint: string;
  artifactCount: number;
  experimentVersion: string;
  featureFingerprint: string;
  fixtureFingerprint: string;
  requestFingerprint: string;
  responseFingerprint: string;
  promotionDecision: "not-promoted";
};

export type BtcResearchRunSummary = BtcB2RunSummary | BtcB3RunSummary;

export type BtcResearchRunPage = {
  engine: "b2" | "b3";
  runs: BtcResearchRunSummary[];
  page: {
    limit: number;
    afterRunId: string | null;
    hasMore: boolean;
    nextAfterRunId: string | null;
  };
};

export type BtcB2Metrics = Record<"naive_0_5" | "empirical_rate" | "conditional_rate", {
  raw: BtcResearchScore;
  calibrated: BtcResearchScore;
}>;

export type BtcB3Report = {
  schema: string;
  status: string;
  experiment: {
    version: string;
    questionId: string;
    decisionQuestion: string;
    answerSchema: { type: string; options: string[]; returns: string[] };
  };
  coverage: Record<"E1_numerical_only" | "E2_numerical_plus_jev", {
    status: string;
    candidateN: number;
    predictedN: number;
    abstentionN: number;
    coverage: number | null;
    abstentionRate: number | null;
    outcomes: Record<string, number>;
  }>;
  sourceBoundary: {
    datasetRevision: string;
    featureFingerprint: string;
    fixtureId: string;
    fixtureFingerprint: string;
    networkRequests: number;
    providerRequests: number;
  };
  failureCounts: Record<string, number>;
  fixtureCaseKinds: Record<string, number>;
  latencyUsageCost: { latency: string; usage: string; cost: string };
  matchedControls: {
    status: string;
    n: number;
    sameInputs: boolean;
    control: string;
    candidate: string;
    controlMetrics: BtcResearchScore;
    candidateMetrics: BtcResearchScore;
    deltasCandidateMinusControl: Record<string, number | null>;
    uncertainty: { status: string; reason: string };
  };
  promotion: {
    decision: "not-promoted";
    reason: string;
    matchedControlStatus: string;
    requiredNextEvidence: string[];
  };
  scientificBoundary: string;
};

export type BtcResearchRunDetail = {
  engine: "b2" | "b3";
  run: BtcResearchRunSummary;
  result: BtcB2Metrics | BtcB3Report;
};

export type PortfolioSummary = {
  cashUsdt: string;
  btcQuantity: string;
  markPrice: string;
  realizedPnlUsdt: string;
  totalFeesUsdt: string;
  marketEventCount: number;
  openOrders: number;
};

export type PortfolioReservation = {
  orderId: string;
  strategyId: string;
  cashUsdt: string;
  btcQuantity: string;
  buyQuantity: string;
};

export type PortfolioOrder = {
  orderId: string;
  strategyId: string;
  side: string;
  orderType: string;
  quantity: string;
  limitPrice: string;
  state: string;
};

export type PortfolioRiskRecord = {
  sequence: string;
  kind: string;
  reasonCode: string;
};

export type PortfolioRiskPage = {
  limit: number;
  beforeSequence: string | null;
  hasMore: boolean;
  nextBeforeSequence: string | null;
};

export type PortfolioEquityPoint = {
  eventTimeMs: number;
  equityUsdt: string;
};

export type PortfolioEquityHistory = {
  points: PortfolioEquityPoint[];
  minimumEquityUsdt: string | null;
  maximumEquityUsdt: string | null;
  page: {
    limit: number;
    returnedCount: number;
    totalCount: number;
    hasMore: boolean;
  };
};

export type PortfolioOrderPage = {
  limit: number;
  beforeOrderId: string | null;
  hasMore: boolean;
  nextBeforeOrderId: string | null;
};

export type PortfolioMemberPage = {
  limit: number;
  afterStrategyId: string | null;
  hasMore: boolean;
  nextAfterStrategyId: string | null;
  totalCount: number;
};

export type PortfolioReservationPage = {
  limit: number;
  beforeOrderId: string | null;
  hasMore: boolean;
  nextBeforeOrderId: string | null;
  totalCount: number;
};

export type PortfolioInspectionCursors = {
  beforeSequence?: string;
  beforeOrderId?: string;
  afterStrategyId?: string;
  beforeReservationOrderId?: string;
};

export type PortfolioDetail = {
  portfolioId: string;
  mode: "isolated" | "shared";
  strategyIds: string[];
  fixtureLineage: string;
  policyFingerprint: string;
  schema: string;
  symbol: string;
  summary: PortfolioSummary;
  equityHistory: PortfolioEquityHistory;
  reservations: {
    cashUsdt: string;
    btcQuantity: string;
    buyQuantity: string;
    rows: PortfolioReservation[];
    page: PortfolioReservationPage;
  };
  memberPage: PortfolioMemberPage;
  orders: PortfolioOrder[];
  orderPage: PortfolioOrderPage;
  riskRecords: PortfolioRiskRecord[];
  riskPage: PortfolioRiskPage;
};

export function isPortfolioId(value: string): boolean {
  return PORTFOLIO_ID_PATTERN.test(value);
}

export function isBtcDatasetRevision(value: string): boolean {
  return DATASET_REVISION_PATTERN.test(value);
}

function parseBtcHistoryDataset(value: unknown): BtcHistoryDataset {
  const row = asObject(value);
  const datasetRevision = asText(row.dataset_revision);
  const symbol = asText(row.symbol);
  const venue = asText(row.venue);
  const interval = asText(row.interval);
  const canonicalFingerprint = asText(row.canonical_fingerprint);
  const candleCount = asCount(row.candle_count);
  const firstOpenTimeMs = asCount(row.first_open_time_ms);
  const lastCloseTimeMs = asCount(row.last_close_time_ms);
  if (
    !isBtcDatasetRevision(datasetRevision)
    || !/^[A-Za-z0-9._-]{1,64}$/.test(symbol)
    || !/^[A-Za-z0-9._-]{1,64}$/.test(venue)
    || !/^[A-Za-z0-9._-]{1,64}$/.test(interval)
    || !/^[0-9a-f]{64}$/.test(canonicalFingerprint)
    || candleCount < 1
    || firstOpenTimeMs > MAX_JS_DATE_TIME_MS
    || lastCloseTimeMs > MAX_JS_DATE_TIME_MS
    || firstOpenTimeMs >= lastCloseTimeMs
  ) {
    throw new LocalApiError("invalid");
  }
  return {
    datasetRevision,
    symbol,
    venue,
    interval,
    canonicalFingerprint,
    candleCount,
    firstOpenTimeMs,
    lastCloseTimeMs,
  };
}

function asCandleDecimal(value: unknown, { allowZero = false } = {}): string {
  const decimal = asDecimal(value);
  const numeric = Number(decimal);
  if (!Number.isFinite(numeric) || numeric < 0 || (!allowZero && numeric === 0)) {
    throw new LocalApiError("invalid");
  }
  return decimal;
}

async function readJson(path: string): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(new URL(path, LOCAL_API_ORIGIN), {
      method: "GET",
      headers: { accept: "application/json" },
      credentials: "omit",
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(4000),
    });
  } catch {
    throw new LocalApiError("unavailable");
  }

  if (response.status === 404) throw new LocalApiError("missing");
  if (response.status === 400) throw new LocalApiError("invalid");
  if (response.status === 409) throw new LocalApiError("rejected");
  if (!response.ok) throw new LocalApiError("unavailable");
  if (!response.headers.get("content-type")?.toLowerCase().includes("application/json")) {
    throw new LocalApiError("invalid");
  }

  try {
    return await response.json();
  } catch {
    throw new LocalApiError("invalid");
  }
}

function asObject(value: unknown): JsonObject {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new LocalApiError("invalid");
  }
  return value as JsonObject;
}

function asArray(value: unknown): unknown[] {
  if (!Array.isArray(value)) throw new LocalApiError("invalid");
  return value;
}

function asText(value: unknown, { allowEmpty = false } = {}): string {
  if (typeof value !== "string" || value.length > 512 || (!allowEmpty && value.length === 0)) {
    throw new LocalApiError("invalid");
  }
  return value;
}

function optionalText(value: unknown, fallback = "—"): string {
  return typeof value === "string" && value.length <= 512 ? value : fallback;
}

function asSequence(value: unknown): string {
  if (typeof value === "string" && /^[1-9]\d{0,63}$/.test(value)) return value;
  throw new LocalApiError("invalid");
}

function optionalCursor(value: unknown): string | null {
  if (value === null) return null;
  if (typeof value === "string" && /^[1-9]\d{0,63}$/.test(value)) return value;
  throw new LocalApiError("invalid");
}

function optionalOrderCursor(value: unknown): string | null {
  if (value === null) return null;
  if (typeof value === "string" && value.length > 0 && value.length <= 160 && !/[\u0000-\u001f]/.test(value)) {
    return value;
  }
  throw new LocalApiError("invalid");
}

function asDecimal(value: unknown): string {
  if (typeof value === "string" && value.length <= 128 && DECIMAL_PATTERN.test(value)) return value;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  throw new LocalApiError("invalid");
}

function asCount(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    throw new LocalApiError("invalid");
  }
  return value;
}

function asBoolean(value: unknown): boolean {
  if (typeof value !== "boolean") throw new LocalApiError("invalid");
  return value;
}

function optionalStrategyCursor(value: unknown): string | null {
  if (value === null) return null;
  if (typeof value === "string" && PORTFOLIO_ID_PATTERN.test(value)) return value;
  throw new LocalApiError("invalid");
}

function matchingPortfolioId(value: unknown, expectedId: string): JsonObject {
  const object = asObject(value);
  if (asText(object.portfolio_id) !== expectedId) throw new LocalApiError("invalid");
  return object;
}

export async function getPortfolioCatalog(options: { limit?: number; afterPortfolioId?: string } = {}): Promise<PortfolioCatalogPage> {
  const limit = options.limit ?? 25;
  const afterPortfolioId = options.afterPortfolioId;
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 100) throw new LocalApiError("invalid");
  if (afterPortfolioId !== undefined && !PORTFOLIO_ID_PATTERN.test(afterPortfolioId)) throw new LocalApiError("invalid");
  const query = new URLSearchParams({ limit: String(limit) });
  if (afterPortfolioId !== undefined) query.set("after_portfolio_id", afterPortfolioId);
  const payload = asObject(await readJson(`/v1/b4/portfolios?${query}`));
  if (payload.api_version !== "market-os.b4-catalog@v1") throw new LocalApiError("invalid");
  const entries = asArray(payload.portfolios);
  if (entries.length > limit) throw new LocalApiError("invalid");
  const portfolios: PortfolioCatalogEntry[] = entries.map((value): PortfolioCatalogEntry => {
    const portfolio = asObject(value);
    const portfolioId = asText(portfolio.portfolio_id);
    if (!isPortfolioId(portfolioId)) throw new LocalApiError("invalid");
    if (portfolio.mode !== "isolated" && portfolio.mode !== "shared") throw new LocalApiError("invalid");
    const mode = portfolio.mode === "isolated" ? "isolated" : "shared";
    const memberCount = asCount(portfolio.member_count);
    if (memberCount < 1 || (mode === "isolated" && memberCount !== 1) || (mode === "shared" && memberCount < 2)) {
      throw new LocalApiError("invalid");
    }
    return {
      portfolioId,
      mode,
      memberCount,
      openOrders: asCount(portfolio.open_orders),
    };
  });
  const pageValue = asObject(payload.page);
  const page = {
    limit: asCount(pageValue.limit),
    afterPortfolioId: pageValue.after_portfolio_id === null ? null : asText(pageValue.after_portfolio_id),
    hasMore: asBoolean(pageValue.has_more),
    nextAfterPortfolioId: pageValue.next_after_portfolio_id === null ? null : asText(pageValue.next_after_portfolio_id),
    skippedCount: asCount(pageValue.skipped_count),
  };
  if (page.limit !== limit || page.afterPortfolioId !== (afterPortfolioId ?? null)) throw new LocalApiError("invalid");
  if (page.hasMore !== (page.nextAfterPortfolioId !== null)) throw new LocalApiError("invalid");
  if (page.hasMore && (portfolios.length === 0 || page.nextAfterPortfolioId !== portfolios.at(-1)?.portfolioId)) {
    throw new LocalApiError("invalid");
  }
  return { portfolios, page };
}

export async function getBtcHistoryDatasetCatalog(
  options: { limit?: number; afterDatasetRevision?: string } = {},
): Promise<BtcHistoryDatasetPage> {
  const limit = options.limit ?? 25;
  const afterDatasetRevision = options.afterDatasetRevision;
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 100) throw new LocalApiError("invalid");
  if (afterDatasetRevision !== undefined && !isBtcDatasetRevision(afterDatasetRevision)) {
    throw new LocalApiError("invalid");
  }
  const query = new URLSearchParams({ limit: String(limit) });
  if (afterDatasetRevision !== undefined) query.set("after_dataset_revision", afterDatasetRevision);
  const payload = asObject(await readJson(`/v1/btc/history/datasets?${query}`));
  if (payload.api_version !== "market-os.btc-history-catalog@v1") throw new LocalApiError("invalid");

  const entries = asArray(payload.datasets);
  if (entries.length > limit) throw new LocalApiError("invalid");
  const datasets = entries.map(parseBtcHistoryDataset);

  const pageValue = asObject(payload.page);
  const page = {
    limit: asCount(pageValue.limit),
    afterDatasetRevision: pageValue.after_dataset_revision === null
      ? null
      : asText(pageValue.after_dataset_revision),
    hasMore: asBoolean(pageValue.has_more),
    nextAfterDatasetRevision: pageValue.next_after_dataset_revision === null
      ? null
      : asText(pageValue.next_after_dataset_revision),
  };
  if (
    page.limit !== limit
    || page.afterDatasetRevision !== (afterDatasetRevision ?? null)
    || page.hasMore !== (page.nextAfterDatasetRevision !== null)
  ) {
    throw new LocalApiError("invalid");
  }
  if (datasets.some((dataset, index) =>
    index > 0 && datasets[index - 1].datasetRevision >= dataset.datasetRevision
  )) {
    throw new LocalApiError("invalid");
  }
  if (page.hasMore && (datasets.length !== limit || page.nextAfterDatasetRevision !== datasets.at(-1)?.datasetRevision)) {
    throw new LocalApiError("invalid");
  }
  if (afterDatasetRevision && datasets.some((dataset) => dataset.datasetRevision <= afterDatasetRevision)) {
    throw new LocalApiError("invalid");
  }
  return { datasets, page };
}

export async function getBtcHistoryCandlePage(
  datasetRevision: string,
  options: { limit?: number; afterOpenTimeMs?: number } = {},
): Promise<BtcHistoryCandlePage> {
  const limit = options.limit ?? 25;
  const afterOpenTimeMs = options.afterOpenTimeMs;
  if (!isBtcDatasetRevision(datasetRevision) || !Number.isSafeInteger(limit) || limit < 1 || limit > 100) {
    throw new LocalApiError("invalid");
  }
  if (
    afterOpenTimeMs !== undefined
    && (!Number.isSafeInteger(afterOpenTimeMs) || afterOpenTimeMs < 0 || afterOpenTimeMs > MAX_JS_DATE_TIME_MS)
  ) {
    throw new LocalApiError("invalid");
  }
  const query = new URLSearchParams({ limit: String(limit) });
  if (afterOpenTimeMs !== undefined) query.set("after_open_time_ms", String(afterOpenTimeMs));
  const payload = asObject(await readJson(
    `/v1/btc/history/datasets/${encodeURIComponent(datasetRevision)}/candles?${query}`,
  ));
  if (payload.api_version !== "market-os.btc-history-candles@v1") throw new LocalApiError("invalid");

  const dataset = parseBtcHistoryDataset(payload.dataset);
  if (dataset.datasetRevision !== datasetRevision) throw new LocalApiError("invalid");
  const entries = asArray(payload.candles);
  if (entries.length > limit) throw new LocalApiError("invalid");
  const candles = entries.map((value): BtcHistoryCandle => {
    const row = asObject(value);
    const openTimeMs = asCount(row.open_time_ms);
    const closeTimeMs = asCount(row.close_time_ms);
    const candle = {
      openTimeMs,
      closeTimeMs,
      open: asCandleDecimal(row.open),
      high: asCandleDecimal(row.high),
      low: asCandleDecimal(row.low),
      close: asCandleDecimal(row.close),
      volume: asCandleDecimal(row.volume, { allowZero: true }),
    };
    if (
      openTimeMs > MAX_JS_DATE_TIME_MS
      || closeTimeMs > MAX_JS_DATE_TIME_MS
      || openTimeMs >= closeTimeMs
      || openTimeMs < dataset.firstOpenTimeMs
      || closeTimeMs > dataset.lastCloseTimeMs
    ) {
      throw new LocalApiError("invalid");
    }
    return candle;
  });
  if (candles.some((candle, index) =>
    (index > 0 && candles[index - 1].openTimeMs >= candle.openTimeMs)
    || (afterOpenTimeMs !== undefined && candle.openTimeMs <= afterOpenTimeMs)
  )) {
    throw new LocalApiError("invalid");
  }

  const pageValue = asObject(payload.page);
  const page = {
    limit: asCount(pageValue.limit),
    afterOpenTimeMs: pageValue.after_open_time_ms === null ? null : asCount(pageValue.after_open_time_ms),
    hasMore: asBoolean(pageValue.has_more),
    nextAfterOpenTimeMs: pageValue.next_after_open_time_ms === null
      ? null
      : asCount(pageValue.next_after_open_time_ms),
  };
  if (
    page.limit !== limit
    || page.afterOpenTimeMs !== (afterOpenTimeMs ?? null)
    || page.hasMore !== (page.nextAfterOpenTimeMs !== null)
    || (page.hasMore && (
      candles.length !== limit
      || page.nextAfterOpenTimeMs !== candles.at(-1)?.openTimeMs
    ))
    || (!page.hasMore && page.nextAfterOpenTimeMs !== null)
  ) {
    throw new LocalApiError("invalid");
  }
  return { dataset, candles, page };
}

function parseBtcManifestSummary(value: unknown, expectedDatasetRevision: string): BtcIngestionManifestSummary {
  const row = asObject(value);
  const manifestId = asText(row.manifest_id);
  const datasetRevision = asText(row.dataset_revision);
  const runId = asText(row.run_id);
  const rawFingerprint = asText(row.raw_fingerprint);
  const manifestSha256 = asText(row.manifest_sha256);
  const requestedStartMs = asCount(row.requested_start_ms);
  const requestedEndMsExclusive = asCount(row.requested_end_ms_exclusive);
  const networkRequests = asCount(row.network_requests);
  if (
    !MANIFEST_ID_PATTERN.test(manifestId)
    || !BTC_DATASET_ONLY_PATTERN.test(datasetRevision)
    || datasetRevision !== expectedDatasetRevision
    || !/^[0-9a-f]{64}$/.test(runId)
    || !/^[0-9a-f]{64}$/.test(rawFingerprint)
    || !/^[0-9a-f]{64}$/.test(manifestSha256)
    || requestedStartMs >= requestedEndMsExclusive
    || requestedEndMsExclusive > MAX_JS_DATE_TIME_MS
    || networkRequests > 300
  ) {
    throw new LocalApiError("invalid");
  }
  return {
    manifestId,
    datasetRevision,
    runId,
    rawFingerprint,
    manifestSha256,
    requestedStartMs,
    requestedEndMsExclusive,
    networkRequests,
  };
}

function parseOptionalTimestamp(value: unknown): string | null {
  if (value === null) return null;
  const timestamp = asText(value);
  const parsed = Date.parse(timestamp);
  if (!Number.isFinite(parsed) || Math.abs(parsed) > MAX_JS_DATE_TIME_MS) throw new LocalApiError("invalid");
  return timestamp;
}

export async function getBtcHistoryManifestPage(
  datasetRevision: string,
  options: { limit?: number; afterManifestId?: string } = {},
): Promise<BtcIngestionManifestPage> {
  const limit = options.limit ?? 25;
  const afterManifestId = options.afterManifestId;
  if (!BTC_DATASET_ONLY_PATTERN.test(datasetRevision) || !Number.isSafeInteger(limit) || limit < 1 || limit > 100) {
    throw new LocalApiError("invalid");
  }
  if (afterManifestId !== undefined && !MANIFEST_ID_PATTERN.test(afterManifestId)) throw new LocalApiError("invalid");
  const query = new URLSearchParams({ limit: String(limit) });
  if (afterManifestId !== undefined) query.set("after_manifest_id", afterManifestId);
  const payload = asObject(await readJson(
    `/v1/btc/history/datasets/${encodeURIComponent(datasetRevision)}/manifests?${query}`,
  ));
  if (payload.api_version !== "market-os.btc-history-manifests@v1") throw new LocalApiError("invalid");
  if (asText(payload.dataset_revision) !== datasetRevision) throw new LocalApiError("invalid");
  const entries = asArray(payload.manifests);
  if (entries.length > limit) throw new LocalApiError("invalid");
  const manifests = entries.map((entry) => parseBtcManifestSummary(entry, datasetRevision));
  if (manifests.some((manifest, index) =>
    index > 0 && manifests[index - 1].manifestId >= manifest.manifestId
  )) {
    throw new LocalApiError("invalid");
  }
  if (afterManifestId && manifests.some((manifest) => manifest.manifestId <= afterManifestId)) {
    throw new LocalApiError("invalid");
  }
  const pageValue = asObject(payload.page);
  const page = {
    limit: asCount(pageValue.limit),
    afterManifestId: pageValue.after_manifest_id === null ? null : asText(pageValue.after_manifest_id),
    hasMore: asBoolean(pageValue.has_more),
    nextAfterManifestId: pageValue.next_after_manifest_id === null
      ? null
      : asText(pageValue.next_after_manifest_id),
  };
  if (
    page.limit !== limit
    || page.afterManifestId !== (afterManifestId ?? null)
    || page.hasMore !== (page.nextAfterManifestId !== null)
    || (page.hasMore && (manifests.length !== limit || page.nextAfterManifestId !== manifests.at(-1)?.manifestId))
  ) {
    throw new LocalApiError("invalid");
  }
  return { datasetRevision, manifests, page };
}

export async function getBtcHistoryManifest(
  datasetRevision: string,
  manifestId: string,
): Promise<BtcIngestionManifest> {
  if (!BTC_DATASET_ONLY_PATTERN.test(datasetRevision) || !MANIFEST_ID_PATTERN.test(manifestId)) {
    throw new LocalApiError("missing");
  }
  const payload = asObject(await readJson(
    `/v1/btc/history/datasets/${encodeURIComponent(datasetRevision)}/manifests/${encodeURIComponent(manifestId)}`,
  ));
  if (payload.api_version !== "market-os.btc-history-manifests@v1") throw new LocalApiError("invalid");
  const row = asObject(payload.manifest);
  const summary = parseBtcManifestSummary(row, datasetRevision);
  if (summary.manifestId !== manifestId) throw new LocalApiError("invalid");
  const outcomeCountsValue = asObject(row.outcome_counts);
  const outcomeEntries = Object.entries(outcomeCountsValue);
  if (outcomeEntries.length > 32) throw new LocalApiError("invalid");
  const outcomeCounts: Record<string, number> = {};
  for (const [name, value] of outcomeEntries) {
    if (!/^[a-z][a-z0-9_]{0,47}$/.test(name)) throw new LocalApiError("invalid");
    outcomeCounts[name] = asCount(value);
  }
  const packageVersionsValue = asObject(row.package_versions);
  if (Object.keys(packageVersionsValue).sort().join(",") !== "duckdb,pyarrow") throw new LocalApiError("invalid");
  const endpointHost = row.endpoint_host === null ? null : asText(row.endpoint_host);
  const endpointClass = asText(row.endpoint_class);
  if (
    (endpointClass === "public-market-data" && endpointHost === null)
    || (endpointClass !== "public-market-data" && endpointHost !== null)
    || !["public-market-data", "synthetic-fixture"].includes(endpointClass)
  ) {
    throw new LocalApiError("invalid");
  }
  const detail: BtcIngestionManifest = {
    ...summary,
    schema: asText(row.schema),
    apiVersion: asText(row.api_version),
    contractVersion: asText(row.contract_version),
    symbol: asText(row.symbol),
    venue: asText(row.venue),
    interval: asText(row.interval),
    sourceIdentity: asText(row.source_identity),
    endpointClass,
    endpointHost,
    observedStartMs: row.observed_start_ms === null ? null : asCount(row.observed_start_ms),
    observedEndMsExclusive: row.observed_end_ms_exclusive === null ? null : asCount(row.observed_end_ms_exclusive),
    sourceTimestampMin: parseOptionalTimestamp(row.source_timestamp_min),
    sourceTimestampMax: parseOptionalTimestamp(row.source_timestamp_max),
    receiptTimestampMin: parseOptionalTimestamp(row.receipt_timestamp_min),
    receiptTimestampMax: parseOptionalTimestamp(row.receipt_timestamp_max),
    availabilityTimestampMax: parseOptionalTimestamp(row.availability_timestamp_max),
    canonicalizationTimestamp: asText(row.canonicalization_timestamp),
    canonicalFingerprint: asText(row.canonical_fingerprint),
    outcomeFingerprint: asText(row.outcome_fingerprint),
    canonicalCandleCount: asCount(row.canonical_candle_count),
    rawRecordCount: asCount(row.raw_record_count),
    outcomeCounts,
    rawPageCount: asCount(row.raw_page_count),
    gapCount: asCount(row.gap_count),
    parentRevisionCount: asCount(row.parent_revision_count),
    parquetSha256: asText(row.parquet_sha256),
    packageVersions: {
      duckdb: asText(packageVersionsValue.duckdb),
      pyarrow: asText(packageVersionsValue.pyarrow),
    },
    pythonVersion: asText(row.python_version),
  };
  if (
    detail.schema !== "market-os.btc-history-manifest.v1"
    || detail.apiVersion !== "market-os.btc-history.v1"
    || !/^[0-9a-f]{64}$/.test(detail.canonicalFingerprint)
    || !/^[0-9a-f]{64}$/.test(detail.outcomeFingerprint)
    || !/^[0-9a-f]{64}$/.test(detail.parquetSha256)
  ) {
    throw new LocalApiError("invalid");
  }
  return detail;
}

async function readBtcManifestRecords(
  datasetRevision: string,
  manifestId: string,
  resource: "outcomes" | "gaps" | "provenance",
  query: URLSearchParams,
): Promise<JsonObject> {
  if (!BTC_DATASET_ONLY_PATTERN.test(datasetRevision) || !MANIFEST_ID_PATTERN.test(manifestId)) {
    throw new LocalApiError("missing");
  }
  const payload = asObject(await readJson(
    `/v1/btc/history/datasets/${encodeURIComponent(datasetRevision)}/manifests/${encodeURIComponent(manifestId)}/${resource}?${query}`,
  ));
  if (
    payload.api_version !== "market-os.btc-history-manifest-records@v1"
    || asText(payload.dataset_revision) !== datasetRevision
    || asText(payload.manifest_id) !== manifestId
  ) {
    throw new LocalApiError("invalid");
  }
  return payload;
}

function manifestRecordPageParts(
  payload: JsonObject,
  collection: string,
  limit: number,
  after: number | string | null,
  nextAfter: number | string | null,
  afterField: string,
  nextField: string,
): { entries: unknown[]; totalCount: number; hasMore: boolean } {
  const entries = asArray(payload[collection]);
  const totalCount = asCount(payload.total_count);
  const page = asObject(payload.page);
  const pageLimit = asCount(page.limit);
  const rawAfter = page[afterField];
  const pageAfter = rawAfter === null ? null : typeof after === "number" ? asCount(rawAfter) : asText(rawAfter);
  const hasMore = asBoolean(page.has_more);
  const rawNext = page[nextField];
  const pageNext = rawNext === null ? null : typeof nextAfter === "number" ? asCount(rawNext) : asText(rawNext);
  if (
    entries.length > limit
    || pageLimit !== limit
    || pageAfter !== after
    || hasMore !== (pageNext !== null)
    || (hasMore && entries.length !== limit)
    || pageNext !== nextAfter
  ) {
    throw new LocalApiError("invalid");
  }
  return { entries, totalCount, hasMore };
}

export async function getBtcIngestionOutcomesPage(
  datasetRevision: string,
  manifestId: string,
  options: { limit?: number; afterOutcomeIndex?: number } = {},
): Promise<BtcIngestionRecordPage<BtcIngestionOutcome, number>> {
  const limit = options.limit ?? 25;
  const after = options.afterOutcomeIndex ?? null;
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 100 || (after !== null && (!Number.isSafeInteger(after) || after < 0 || after > 200_000))) {
    throw new LocalApiError("invalid");
  }
  const query = new URLSearchParams({ limit: String(limit) });
  if (after !== null) query.set("after_outcome_index", String(after));
  const payload = await readBtcManifestRecords(datasetRevision, manifestId, "outcomes", query);
  const entries = asArray(payload.outcomes);
  if (entries.length > limit) throw new LocalApiError("invalid");
  const outcomes = entries.map((entry): BtcIngestionOutcome => {
    const row = asObject(entry);
    const outcomeIndex = asCount(row.outcome_index);
    const rawPageSha256 = asText(row.raw_page_sha256);
    const rowIndex = asCount(row.row_index);
    const sourceRecordFingerprint = asText(row.source_record_fingerprint);
    const openTimeMs = row.open_time_ms === null ? null : asCount(row.open_time_ms);
    const status = asText(row.status);
    const reason = row.reason === null ? null : asText(row.reason, { allowEmpty: true });
    const reasonTruncated = asBoolean(row.reason_truncated);
    const acceptedCanonical = asBoolean(row.accepted_canonical);
    if (
      outcomeIndex > 200_000
      || !/^[0-9a-f]{64}$/.test(rawPageSha256)
      || rowIndex >= 1000
      || !/^[0-9a-f]{64}$/.test(sourceRecordFingerprint)
      || (openTimeMs !== null && openTimeMs > MAX_JS_DATE_TIME_MS)
      || !/^[a-z][a-z0-9_]{0,47}$/.test(status)
      || (reason !== null && reason.length > 512)
      || (openTimeMs === null && acceptedCanonical)
    ) {
      throw new LocalApiError("invalid");
    }
    return { outcomeIndex, rawPageSha256, rowIndex, sourceRecordFingerprint, openTimeMs, status, reason, reasonTruncated, acceptedCanonical };
  });
  if (outcomes.some((row, index) => row.outcomeIndex <= (index === 0 ? after ?? -1 : outcomes[index - 1].outcomeIndex))) {
    throw new LocalApiError("invalid");
  }
  const pageValue = asObject(payload.page);
  const next = pageValue.next_after_outcome_index === null ? null : asCount(pageValue.next_after_outcome_index);
  const { totalCount, hasMore } = manifestRecordPageParts(
    payload, "outcomes", limit, after, next, "after_outcome_index", "next_after_outcome_index",
  );
  if (totalCount > 200_000 || (outcomes.length && outcomes.at(-1)?.outcomeIndex! >= totalCount) || (hasMore && next !== outcomes.at(-1)?.outcomeIndex)) {
    throw new LocalApiError("invalid");
  }
  return {
    datasetRevision, manifestId, totalCount, records: outcomes,
    page: { limit, after, hasMore, nextAfter: next },
  };
}

export async function getBtcIngestionGapsPage(
  datasetRevision: string,
  manifestId: string,
  options: { limit?: number; afterStartTimeMs?: number } = {},
): Promise<BtcIngestionRecordPage<BtcIngestionGap, number>> {
  const limit = options.limit ?? 25;
  const after = options.afterStartTimeMs ?? null;
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 100 || (after !== null && (!Number.isSafeInteger(after) || after < 0 || after > MAX_JS_DATE_TIME_MS))) {
    throw new LocalApiError("invalid");
  }
  const query = new URLSearchParams({ limit: String(limit) });
  if (after !== null) query.set("after_start_time_ms", String(after));
  const payload = await readBtcManifestRecords(datasetRevision, manifestId, "gaps", query);
  const entries = asArray(payload.gaps);
  if (entries.length > limit) throw new LocalApiError("invalid");
  const gaps = entries.map((entry): BtcIngestionGap => {
    const row = asObject(entry);
    const startTimeMs = asCount(row.start_time_ms);
    const endTimeMs = asCount(row.end_time_ms);
    if (
      startTimeMs > MAX_JS_DATE_TIME_MS
      || endTimeMs > MAX_JS_DATE_TIME_MS
      || startTimeMs >= endTimeMs
      || startTimeMs % 60_000 !== 0
      || endTimeMs % 60_000 !== 0
      || endTimeMs - startTimeMs < 60_000
    ) {
      throw new LocalApiError("invalid");
    }
    return { startTimeMs, endTimeMs };
  });
  if (gaps.some((row, index) => row.startTimeMs <= (index === 0 ? after ?? -1 : gaps[index - 1].startTimeMs))) {
    throw new LocalApiError("invalid");
  }
  const pageValue = asObject(payload.page);
  const next = pageValue.next_after_start_time_ms === null ? null : asCount(pageValue.next_after_start_time_ms);
  const { totalCount, hasMore } = manifestRecordPageParts(
    payload, "gaps", limit, after, next, "after_start_time_ms", "next_after_start_time_ms",
  );
  if (totalCount > 100_000 || (gaps.length && gaps.at(-1)?.startTimeMs! >= MAX_JS_DATE_TIME_MS) || (hasMore && next !== gaps.at(-1)?.startTimeMs)) {
    throw new LocalApiError("invalid");
  }
  return {
    datasetRevision, manifestId, totalCount, records: gaps,
    page: { limit, after, hasMore, nextAfter: next },
  };
}

export async function getBtcIngestionProvenancePage(
  datasetRevision: string,
  manifestId: string,
  options: { limit?: number; afterRawPageSha256?: string; afterRowIndex?: number } = {},
): Promise<BtcIngestionRecordPage<BtcIngestionProvenance, { rawPageSha256: string; rowIndex: number }>> {
  const limit = options.limit ?? 25;
  const after = options.afterRawPageSha256 === undefined && options.afterRowIndex === undefined
    ? null
    : { rawPageSha256: options.afterRawPageSha256 ?? "", rowIndex: options.afterRowIndex ?? -1 };
  if (
    !Number.isSafeInteger(limit) || limit < 1 || limit > 100
    || (after !== null && (!/^[0-9a-f]{64}$/.test(after.rawPageSha256) || !Number.isSafeInteger(after.rowIndex) || after.rowIndex < 0 || after.rowIndex >= 1000))
  ) {
    throw new LocalApiError("invalid");
  }
  const query = new URLSearchParams({ limit: String(limit) });
  if (after !== null) {
    query.set("after_raw_page_sha256", after.rawPageSha256);
    query.set("after_row_index", String(after.rowIndex));
  }
  const payload = await readBtcManifestRecords(datasetRevision, manifestId, "provenance", query);
  const entries = asArray(payload.provenance);
  if (entries.length > limit) throw new LocalApiError("invalid");
  const records = entries.map((entry): BtcIngestionProvenance => {
    const row = asObject(entry);
    const rawPageSha256 = asText(row.raw_page_sha256);
    const rowIndex = asCount(row.row_index);
    const sourceRecordFingerprint = asText(row.source_record_fingerprint);
    const payloadBytes = asCount(row.payload_bytes);
    const payloadPreview = asText(row.payload_preview, { allowEmpty: true });
    const payloadTruncated = asBoolean(row.payload_truncated);
    if (
      !/^[0-9a-f]{64}$/.test(rawPageSha256)
      || rowIndex >= 1000
      || !/^[0-9a-f]{64}$/.test(sourceRecordFingerprint)
      || payloadBytes > 256 * 1024
      || !/^[\x00-\x7f]*$/.test(payloadPreview)
      || payloadPreview.length !== Math.min(payloadBytes, 512)
      || payloadTruncated !== (payloadBytes > 512)
    ) {
      throw new LocalApiError("invalid");
    }
    return { rawPageSha256, rowIndex, sourceRecordFingerprint, payloadBytes, payloadPreview, payloadTruncated };
  });
  const compareKeys = (
    left: { rawPageSha256: string; rowIndex: number },
    right: { rawPageSha256: string; rowIndex: number },
  ) => left.rawPageSha256.localeCompare(right.rawPageSha256) || left.rowIndex - right.rowIndex;
  if (records.some((row, index) => compareKeys(row, index === 0 && after !== null
    ? after
    : records[index - 1] ?? { rawPageSha256: "", rowIndex: -1 }) <= 0)) {
    throw new LocalApiError("invalid");
  }
  const pageValue = asObject(payload.page);
  const nextHash = pageValue.next_after_raw_page_sha256 === null ? null : asText(pageValue.next_after_raw_page_sha256);
  const nextRow = pageValue.next_after_row_index === null ? null : asCount(pageValue.next_after_row_index);
  const next = nextHash === null && nextRow === null ? null
    : nextHash !== null && nextRow !== null ? { rawPageSha256: nextHash, rowIndex: nextRow }
      : (() => { throw new LocalApiError("invalid"); })();
  const page = asObject(payload.page);
  const limitEcho = asCount(page.limit);
  const afterHash = page.after_raw_page_sha256 === null ? null : asText(page.after_raw_page_sha256);
  const afterRow = page.after_row_index === null ? null : asCount(page.after_row_index);
  const afterEcho = afterHash === null && afterRow === null ? null
    : afterHash !== null && afterRow !== null ? { rawPageSha256: afterHash, rowIndex: afterRow }
      : (() => { throw new LocalApiError("invalid"); })();
  const hasMore = asBoolean(page.has_more);
  const totalCount = asCount(payload.total_count);
  if (
    limitEcho !== limit
    || JSON.stringify(afterEcho) !== JSON.stringify(after)
    || hasMore !== (next !== null)
    || (hasMore && (records.length !== limit || JSON.stringify(next) !== JSON.stringify(records.at(-1) && { rawPageSha256: records.at(-1)!.rawPageSha256, rowIndex: records.at(-1)!.rowIndex })))
    || totalCount > 100_000
    || records.length > totalCount
  ) {
    throw new LocalApiError("invalid");
  }
  return {
    datasetRevision, manifestId, totalCount, records,
    page: { limit, after, hasMore, nextAfter: next },
  };
}

function researchRunPattern(engine: "b2" | "b3"): RegExp {
  return engine === "b2" ? /^btc-b2-[0-9a-f]{20}$/ : /^btc-b3-[0-9a-f]{20}$/;
}

function parseResearchRunSummary(value: unknown, engine: "b2" | "b3"): BtcResearchRunSummary {
  const row = asObject(value);
  const runId = asText(row.run_id);
  const datasetRevision = asText(row.dataset_revision);
  const sampleCount = asCount(row.sample_count);
  const replayFingerprint = asText(row.replay_fingerprint);
  const artifactCount = asCount(row.artifact_count);
  const featureFingerprint = asText(row.feature_fingerprint);
  if (
    !researchRunPattern(engine).test(runId)
    || !BTC_DATASET_ONLY_PATTERN.test(datasetRevision)
    || sampleCount > 100_000
    || !/^[0-9a-f]{64}$/.test(replayFingerprint)
    || !/^[0-9a-f]{64}$/.test(featureFingerprint)
    || artifactCount !== (engine === "b2" ? 8 : 11)
  ) {
    throw new LocalApiError("invalid");
  }
  if (engine === "b2") {
    const labelFingerprint = asText(row.label_fingerprint);
    const baselines = asArray(row.baselines).map((item) => asText(item));
    if (
      !/^[0-9a-f]{64}$/.test(labelFingerprint)
      || baselines.join(",") !== "naive_0_5,empirical_rate,conditional_rate"
    ) {
      throw new LocalApiError("invalid");
    }
    return {
      engine,
      runId,
      datasetRevision,
      sampleCount,
      replayFingerprint,
      artifactCount,
      featureFingerprint,
      labelFingerprint,
      baselines,
    };
  }
  const fixtureFingerprint = asText(row.fixture_fingerprint);
  const requestFingerprint = asText(row.request_fingerprint);
  const responseFingerprint = asText(row.response_fingerprint);
  const promotionDecision = asText(row.promotion_decision);
  if (
    !/^[0-9a-f]{64}$/.test(fixtureFingerprint)
    || !/^[0-9a-f]{64}$/.test(requestFingerprint)
    || !/^[0-9a-f]{64}$/.test(responseFingerprint)
    || promotionDecision !== "not-promoted"
  ) {
    throw new LocalApiError("invalid");
  }
  return {
    engine,
    runId,
    datasetRevision,
    sampleCount,
    replayFingerprint,
    artifactCount,
    experimentVersion: asText(row.experiment_version),
    featureFingerprint,
    fixtureFingerprint,
    requestFingerprint,
    responseFingerprint,
    promotionDecision,
  };
}

function parseResearchScore(value: unknown): BtcResearchScore {
  const row = asObject(value);
  const status = asText(row.status);
  const n = asCount(row.n);
  const nullableMetric = (metric: unknown, { bounded = false } = {}): number | null => {
    if (metric === null) return null;
    if (typeof metric !== "number" || !Number.isFinite(metric) || metric < 0 || (bounded && metric > 1)) {
      throw new LocalApiError("invalid");
    }
    return metric;
  };
  if (status !== "measured" && status !== "unavailable") throw new LocalApiError("invalid");
  if ((status === "measured") !== (n > 0) || n > 100_000) throw new LocalApiError("invalid");
  return {
    status,
    n,
    logLoss: nullableMetric(row.log_loss),
    brier: nullableMetric(row.brier, { bounded: true }),
    accuracy: nullableMetric(row.accuracy, { bounded: true }),
  };
}

function parseOutcomeCounts(value: unknown): Record<string, number> {
  const row = asObject(value);
  const entries = Object.entries(row);
  if (entries.length > 32) throw new LocalApiError("invalid");
  const counts: Record<string, number> = {};
  for (const [name, amount] of entries) {
    if (!/^[a-z][a-z0-9_-]{0,63}$/.test(name)) throw new LocalApiError("invalid");
    counts[name] = asCount(amount);
  }
  return counts;
}

function parseB2Metrics(value: unknown): BtcB2Metrics {
  const object = asObject(value);
  const names = ["naive_0_5", "empirical_rate", "conditional_rate"] as const;
  if (Object.keys(object).sort().join(",") !== [...names].sort().join(",")) throw new LocalApiError("invalid");
  const metrics = {} as BtcB2Metrics;
  for (const name of names) {
    const arms = asObject(object[name]);
    if (Object.keys(arms).sort().join(",") !== "calibrated,raw") throw new LocalApiError("invalid");
    metrics[name] = {
      raw: parseResearchScore(arms.raw),
      calibrated: parseResearchScore(arms.calibrated),
    };
  }
  return metrics;
}

function parseB3Report(value: unknown): BtcB3Report {
  const row = asObject(value);
  const experimentValue = asObject(row.experiment);
  const answerSchemaValue = asObject(experimentValue.answer_schema);
  const answerSchema = {
    type: asText(answerSchemaValue.type),
    options: asArray(answerSchemaValue.options).map((item) => asText(item)),
    returns: asArray(answerSchemaValue.returns).map((item) => asText(item)),
  };
  if (answerSchema.type !== "choice" || answerSchema.options.length > 8 || answerSchema.returns.length > 8) {
    throw new LocalApiError("invalid");
  }
  const sourceValue = asObject(row.source_boundary);
  const sourceBoundary = {
    datasetRevision: asText(sourceValue.dataset_revision),
    featureFingerprint: asText(sourceValue.feature_fingerprint),
    fixtureId: asText(sourceValue.fixture_id),
    fixtureFingerprint: asText(sourceValue.fixture_fingerprint),
    networkRequests: asCount(sourceValue.network_requests),
    providerRequests: asCount(sourceValue.provider_requests),
  };
  if (
    !BTC_DATASET_ONLY_PATTERN.test(sourceBoundary.datasetRevision)
    || !/^[0-9a-f]{64}$/.test(sourceBoundary.featureFingerprint)
    || !/^[0-9a-f]{64}$/.test(sourceBoundary.fixtureFingerprint)
    || sourceBoundary.networkRequests !== 0
    || sourceBoundary.providerRequests !== 0
  ) {
    throw new LocalApiError("invalid");
  }
  const coverageValue = asObject(row.coverage);
  const coverage: BtcB3Report["coverage"] = {
    E1_numerical_only: parseCoverage(coverageValue.E1_numerical_only),
    E2_numerical_plus_jev: parseCoverage(coverageValue.E2_numerical_plus_jev),
  };
  const latencyValue = asObject(row.latency_usage_cost);
  const latencyUsageCost = {
    latency: asText(latencyValue.latency),
    usage: asText(latencyValue.usage),
    cost: asText(latencyValue.cost),
  };
  if (Object.values(latencyUsageCost).some((item) => item !== "unknown-not-observed-offline")) {
    throw new LocalApiError("invalid");
  }
  const matchedValue = asObject(row.matched_controls);
  const uncertaintyValue = asObject(matchedValue.uncertainty);
  const deltaValue = asObject(matchedValue.deltas_candidate_minus_control);
  const deltas: Record<string, number | null> = {};
  for (const [name, amount] of Object.entries(deltaValue)) {
    if (!["log_loss", "brier", "accuracy"].includes(name)) throw new LocalApiError("invalid");
    if (amount !== null && (typeof amount !== "number" || !Number.isFinite(amount))) throw new LocalApiError("invalid");
    deltas[name] = amount as number | null;
  }
  const promotionValue = asObject(row.promotion);
  const requiredNextEvidence = asArray(promotionValue.required_next_evidence).map((item) => asText(item));
  if (requiredNextEvidence.length > 16 || promotionValue.decision !== "not-promoted") throw new LocalApiError("invalid");
  const report: BtcB3Report = {
    schema: asText(row.schema),
    status: asText(row.status),
    experiment: {
      version: asText(experimentValue.version),
      questionId: asText(experimentValue.question_id),
      decisionQuestion: asText(experimentValue.decision_question),
      answerSchema,
    },
    sourceBoundary,
    coverage,
    failureCounts: parseOutcomeCounts(row.failure_counts),
    fixtureCaseKinds: parseOutcomeCounts(row.fixture_case_kinds),
    latencyUsageCost,
    matchedControls: {
      status: asText(matchedValue.status),
      n: asCount(matchedValue.n),
      sameInputs: asBoolean(matchedValue.same_inputs),
      control: asText(matchedValue.control),
      candidate: asText(matchedValue.candidate),
      controlMetrics: parseResearchScore(matchedValue.control_metrics),
      candidateMetrics: parseResearchScore(matchedValue.candidate_metrics),
      deltasCandidateMinusControl: deltas,
      uncertainty: {
        status: asText(uncertaintyValue.status),
        reason: asText(uncertaintyValue.reason),
      },
    },
    promotion: {
      decision: "not-promoted",
      reason: asText(promotionValue.reason),
      matchedControlStatus: asText(promotionValue.matched_control_status),
      requiredNextEvidence,
    },
    scientificBoundary: asText(row.scientific_boundary),
  };
  if (
    report.schema !== "market-os.u3-b3.report.v1"
    || report.status !== "implemented-and-verified-offline"
    || report.matchedControls.sameInputs !== true
  ) {
    throw new LocalApiError("invalid");
  }
  return report;
}

function parseCoverage(value: unknown): BtcB3Report["coverage"]["E1_numerical_only"] {
  const row = asObject(value);
  const status = asText(row.status);
  const candidateN = asCount(row.candidate_n);
  const predictedN = asCount(row.predicted_n);
  const abstentionN = asCount(row.abstention_n);
  if (
    (status !== "measured" && status !== "unavailable")
    || (status === "measured") !== (candidateN > 0)
    || predictedN > candidateN
    || abstentionN !== candidateN - predictedN
  ) {
    throw new LocalApiError("invalid");
  }
  return {
    status,
    candidateN,
    predictedN,
    abstentionN,
    coverage: row.coverage === null ? null : boundedRatio(row.coverage),
    abstentionRate: row.abstention_rate === null ? null : boundedRatio(row.abstention_rate),
    outcomes: parseOutcomeCounts(row.outcomes),
  };
}

function boundedRatio(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1) {
    throw new LocalApiError("invalid");
  }
  return value;
}

export async function getBtcResearchRunPage(
  engine: "b2" | "b3",
  options: { limit?: number; afterRunId?: string } = {},
): Promise<BtcResearchRunPage> {
  const limit = options.limit ?? 25;
  const afterRunId = options.afterRunId;
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 100) throw new LocalApiError("invalid");
  if (afterRunId !== undefined && !researchRunPattern(engine).test(afterRunId)) throw new LocalApiError("invalid");
  const query = new URLSearchParams({ limit: String(limit) });
  if (afterRunId !== undefined) query.set("after_run_id", afterRunId);
  const payload = asObject(await readJson(`/v1/btc/research/${engine}/runs?${query}`));
  if (payload.api_version !== "market-os.btc-research-inspection@v1" || payload.engine !== engine) {
    throw new LocalApiError("invalid");
  }
  const entries = asArray(payload.runs);
  if (entries.length > limit) throw new LocalApiError("invalid");
  const runs = entries.map((entry) => parseResearchRunSummary(entry, engine));
  if (runs.some((run, index) => index > 0 && runs[index - 1].runId >= run.runId)) throw new LocalApiError("invalid");
  if (afterRunId && runs.some((run) => run.runId <= afterRunId)) throw new LocalApiError("invalid");
  const pageValue = asObject(payload.page);
  const page = {
    limit: asCount(pageValue.limit),
    afterRunId: pageValue.after_run_id === null ? null : asText(pageValue.after_run_id),
    hasMore: asBoolean(pageValue.has_more),
    nextAfterRunId: pageValue.next_after_run_id === null ? null : asText(pageValue.next_after_run_id),
  };
  if (
    page.limit !== limit
    || page.afterRunId !== (afterRunId ?? null)
    || page.hasMore !== (page.nextAfterRunId !== null)
    || (page.hasMore && (runs.length !== limit || page.nextAfterRunId !== runs.at(-1)?.runId))
  ) {
    throw new LocalApiError("invalid");
  }
  return { engine, runs, page };
}

export async function getBtcResearchRun(engine: "b2" | "b3", runId: string): Promise<BtcResearchRunDetail> {
  if (!researchRunPattern(engine).test(runId)) throw new LocalApiError("missing");
  const payload = asObject(await readJson(
    `/v1/btc/research/${engine}/runs/${encodeURIComponent(runId)}`,
  ));
  if (payload.api_version !== "market-os.btc-research-inspection@v1" || payload.engine !== engine) {
    throw new LocalApiError("invalid");
  }
  const run = parseResearchRunSummary(payload.run, engine);
  if (run.runId !== runId) throw new LocalApiError("invalid");
  const result = engine === "b2" ? parseB2Metrics(payload.result) : parseB3Report(payload.result);
  if (engine === "b3" && (result as BtcB3Report).sourceBoundary.datasetRevision !== run.datasetRevision) {
    throw new LocalApiError("invalid");
  }
  return { engine, run, result };
}

export async function getPortfolioDetail(
  portfolioId: string,
  cursors: PortfolioInspectionCursors = {},
): Promise<PortfolioDetail> {
  const { beforeSequence, beforeOrderId, afterStrategyId, beforeReservationOrderId } = cursors;
  if (!isPortfolioId(portfolioId)) throw new LocalApiError("missing");
  if (beforeSequence !== undefined && !/^[1-9]\d{0,63}$/.test(beforeSequence)) {
    throw new LocalApiError("missing");
  }
  if (beforeOrderId !== undefined && (beforeOrderId.length === 0 || beforeOrderId.length > 160 || /[\u0000-\u001f]/.test(beforeOrderId))) {
    throw new LocalApiError("missing");
  }
  if (afterStrategyId !== undefined && !PORTFOLIO_ID_PATTERN.test(afterStrategyId)) {
    throw new LocalApiError("missing");
  }
  if (beforeReservationOrderId !== undefined && (beforeReservationOrderId.length === 0 || beforeReservationOrderId.length > 160 || /[\u0000-\u001f]/.test(beforeReservationOrderId))) {
    throw new LocalApiError("missing");
  }

  const query = new URLSearchParams({ risk_limit: "8", order_limit: "25", member_limit: "25", reservation_limit: "25" });
  if (beforeSequence) query.set("risk_before_sequence", beforeSequence);
  if (beforeOrderId) query.set("order_before_id", beforeOrderId);
  if (afterStrategyId) query.set("member_after_strategy_id", afterStrategyId);
  if (beforeReservationOrderId) query.set("reservation_before_order_id", beforeReservationOrderId);
  const root = `/v3/b4/portfolios/${portfolioId}/inspection?${query}`;
  const inspection = asObject(await readJson(root));
  if (inspection.api_version !== "market-os.b4-portfolio-inspection@v3") throw new LocalApiError("invalid");
  if (asText(inspection.portfolio_id) !== portfolioId) throw new LocalApiError("invalid");
  const summaryObject = matchingPortfolioId(inspection.summary, portfolioId);
  const genesis = matchingPortfolioId(inspection.genesis, portfolioId);
  if (genesis.member_strategy_ids !== undefined) throw new LocalApiError("invalid");
  const history = matchingPortfolioId(inspection.equity_history, portfolioId);
  const memberPayload = matchingPortfolioId(inspection.members, portfolioId);
  const reservations = matchingPortfolioId(inspection.reservations, portfolioId);
  const orderPayload = matchingPortfolioId(inspection.orders, portfolioId);
  const riskPayload = matchingPortfolioId(inspection.risk, portfolioId);

  const equityRows = asArray(history.points);
  const equityPageValue = asObject(history.page);
  const equityPage = {
    limit: asCount(equityPageValue.limit),
    returnedCount: asCount(equityPageValue.returned_count),
    totalCount: asCount(equityPageValue.total_count),
    hasMore: asBoolean(equityPageValue.has_more),
  };
  if (
    equityPageValue.scope !== "latest"
    || equityPage.limit !== 100
    || equityPage.returnedCount !== equityRows.length
    || equityPage.totalCount < equityPage.returnedCount
    || equityPage.returnedCount !== Math.min(equityPage.totalCount, equityPage.limit)
    || equityPage.hasMore !== (equityPage.totalCount > equityPage.returnedCount)
  ) {
    throw new LocalApiError("invalid");
  }
  const equityPoints = equityRows.map((value): PortfolioEquityPoint => {
    const row = asObject(value);
    return { eventTimeMs: asCount(row.event_time_ms), equityUsdt: asDecimal(row.equity_usdt) };
  });
  if (equityPoints.some((point, index) => index > 0 && equityPoints[index - 1].eventTimeMs > point.eventTimeMs)) {
    throw new LocalApiError("invalid");
  }
  const minimumEquityUsdt = history.minimum_equity_usdt === null ? null : asDecimal(history.minimum_equity_usdt);
  const maximumEquityUsdt = history.maximum_equity_usdt === null ? null : asDecimal(history.maximum_equity_usdt);
  if (
    equityPoints.length === 0 && (minimumEquityUsdt !== null || maximumEquityUsdt !== null)
    || equityPoints.length > 0 && (minimumEquityUsdt === null || maximumEquityUsdt === null)
  ) {
    throw new LocalApiError("invalid");
  }
  if (equityPoints.length > 0 && minimumEquityUsdt !== null && maximumEquityUsdt !== null) {
    const minimum = Number(minimumEquityUsdt);
    const maximum = Number(maximumEquityUsdt);
    const values = equityPoints.map((point) => Number(point.equityUsdt));
    if (
      Number.isFinite(minimum)
      && Number.isFinite(maximum)
      && values.every(Number.isFinite)
      && (minimum < 0 || maximum < minimum || values.some((value) => value < minimum || value > maximum))
    ) {
      throw new LocalApiError("invalid");
    }
  }

  const strategyId = asText(genesis.strategy_id);
  const mode = genesis.shared_portfolio_id ? "shared" : "isolated";
  const memberValues = asArray(memberPayload.strategy_ids);
  const memberPageValue = asObject(memberPayload.page);
  const memberPage: PortfolioMemberPage = {
    limit: asCount(memberPageValue.limit),
    afterStrategyId: optionalStrategyCursor(memberPageValue.after_strategy_id),
    hasMore: memberPageValue.has_more === true,
    nextAfterStrategyId: optionalStrategyCursor(memberPageValue.next_after_strategy_id),
    totalCount: asCount(memberPageValue.total_count),
  };
  if (
    typeof memberPageValue.has_more !== "boolean"
    || memberPage.limit < 1
    || memberPage.limit > 100
    || memberValues.length > memberPage.limit
    || memberPage.totalCount < memberValues.length
  ) {
    throw new LocalApiError("invalid");
  }
  if (afterStrategyId !== undefined && memberPage.afterStrategyId !== afterStrategyId) {
    throw new LocalApiError("invalid");
  }
  if (
    memberPage.hasMore !== (memberPage.nextAfterStrategyId !== null)
    || memberPage.hasMore && memberValues.length !== memberPage.limit
    || memberPage.hasMore && memberPage.nextAfterStrategyId !== asText(memberValues.at(-1))
  ) {
    throw new LocalApiError("invalid");
  }
  const memberIds = memberValues.map((value) => {
    const memberId = asText(value);
    if (!PORTFOLIO_ID_PATTERN.test(memberId)) throw new LocalApiError("invalid");
    return memberId;
  });
  if (memberIds.some((memberId, index) => index > 0 && memberIds[index - 1] >= memberId)) {
    throw new LocalApiError("invalid");
  }

  const reservationValues = asArray(reservations.reservations);
  const reservationPageValue = asObject(reservations.page);
  const reservationPage: PortfolioReservationPage = {
    limit: asCount(reservationPageValue.limit),
    beforeOrderId: optionalOrderCursor(reservationPageValue.before_order_id),
    hasMore: reservationPageValue.has_more === true,
    nextBeforeOrderId: optionalOrderCursor(reservationPageValue.next_before_order_id),
    totalCount: asCount(reservationPageValue.total_count),
  };
  if (
    typeof reservationPageValue.has_more !== "boolean"
    || reservationPage.limit < 1
    || reservationPage.limit > 100
    || reservationValues.length > reservationPage.limit
    || reservationPage.totalCount < reservationValues.length
    || reservationPage.hasMore && reservationValues.length !== reservationPage.limit
  ) {
    throw new LocalApiError("invalid");
  }
  if (beforeReservationOrderId !== undefined && reservationPage.beforeOrderId !== beforeReservationOrderId) {
    throw new LocalApiError("invalid");
  }
  if (
    reservationPage.hasMore !== (reservationPage.nextBeforeOrderId !== null)
    || reservationPage.hasMore && reservationValues.length !== reservationPage.limit
  ) {
    throw new LocalApiError("invalid");
  }
  const reservationRows = reservationValues.map((value) => {
    const row = asObject(value);
    const orderId = optionalOrderCursor(row.order_id);
    if (orderId === null) throw new LocalApiError("invalid");
    return {
      orderId,
      strategyId: asText(row.strategy_id),
      cashUsdt: asDecimal(row.cash_usdt),
      btcQuantity: asDecimal(row.btc_quantity),
      buyQuantity: asDecimal(row.buy_quantity),
    };
  });
  if (reservationPage.hasMore && reservationPage.nextBeforeOrderId !== reservationRows.at(-1)?.orderId) {
    throw new LocalApiError("invalid");
  }

  const orderRows = asArray(orderPayload.orders);
  const orderPageValue = asObject(orderPayload.page);
  const orderPage: PortfolioOrderPage = {
    limit: asCount(orderPageValue.limit),
    beforeOrderId: optionalOrderCursor(orderPageValue.before_order_id),
    hasMore: orderPageValue.has_more === true,
    nextBeforeOrderId: optionalOrderCursor(orderPageValue.next_before_order_id),
  };
  if (
    typeof orderPageValue.has_more !== "boolean"
    || orderPage.limit < 1
    || orderPage.limit > 100
    || orderRows.length > orderPage.limit
  ) {
    throw new LocalApiError("invalid");
  }
  if (beforeOrderId !== undefined && orderPage.beforeOrderId !== beforeOrderId) {
    throw new LocalApiError("invalid");
  }
  if (orderPage.hasMore !== (orderPage.nextBeforeOrderId !== null) || orderPage.hasMore && orderRows.length !== orderPage.limit) {
    throw new LocalApiError("invalid");
  }

  const orders = orderRows.map((value) => {
    const row = asObject(value);
    return {
      orderId: asText(row.order_id),
      strategyId: optionalText(row.strategy_id, strategyId),
      side: asText(row.side),
      orderType: asText(row.order_type),
      quantity: asDecimal(row.quantity),
      limitPrice: row.limit_price === null ? "Market" : asDecimal(row.limit_price),
      state: asText(row.state),
    };
  });

  const riskRows = asArray(riskPayload.records);
  const riskPageValue = asObject(riskPayload.page);
  const riskPage: PortfolioRiskPage = {
    limit: asCount(riskPageValue.limit),
    beforeSequence: optionalCursor(riskPageValue.before_sequence),
    hasMore: riskPageValue.has_more === true,
    nextBeforeSequence: optionalCursor(riskPageValue.next_before_sequence),
  };
  if (
    typeof riskPageValue.has_more !== "boolean"
    || riskPage.limit < 1
    || riskPage.limit > 100
    || riskRows.length > riskPage.limit
  ) {
    throw new LocalApiError("invalid");
  }
  if (beforeSequence !== undefined && riskPage.beforeSequence !== beforeSequence) {
    throw new LocalApiError("invalid");
  }
  if (riskPage.hasMore !== (riskPage.nextBeforeSequence !== null) || riskPage.hasMore && riskRows.length !== riskPage.limit) {
    throw new LocalApiError("invalid");
  }

  const riskRecords = riskRows.map((value) => {
    const row = asObject(value);
    return {
      sequence: asSequence(row.sequence),
      kind: asText(row.kind),
      reasonCode: optionalText(row.reason_code, "recorded"),
    };
  });

  return {
    portfolioId,
    mode,
    strategyIds: memberIds,
    fixtureLineage: asText(genesis.fixture_lineage),
    policyFingerprint: asText(genesis.policy_fingerprint, { allowEmpty: true }),
    schema: asText(genesis.schema),
    symbol: asText(genesis.symbol),
    summary: {
      cashUsdt: asDecimal(summaryObject.cash_usdt),
      btcQuantity: asDecimal(summaryObject.btc_quantity),
      markPrice: asDecimal(summaryObject.mark_price),
      realizedPnlUsdt: asDecimal(summaryObject.realized_pnl_usdt),
      totalFeesUsdt: asDecimal(summaryObject.total_fees_usdt),
      marketEventCount: asCount(summaryObject.market_event_count),
      openOrders: asCount(summaryObject.open_orders),
    },
    equityHistory: {
      points: equityPoints,
      minimumEquityUsdt,
      maximumEquityUsdt,
      page: equityPage,
    },
    reservations: {
      cashUsdt: asDecimal(reservations.cash_usdt),
      btcQuantity: asDecimal(reservations.btc_quantity),
      buyQuantity: asDecimal(reservations.buy_quantity),
      rows: reservationRows,
      page: reservationPage,
    },
    memberPage,
    orders,
    orderPage,
    riskRecords,
    riskPage,
  };
}
