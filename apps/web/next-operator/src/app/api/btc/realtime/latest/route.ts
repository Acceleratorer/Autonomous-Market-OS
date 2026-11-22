import { getBtcRealtimeCapture, LocalApiError } from "@/lib/market-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  try {
    return Response.json(await getBtcRealtimeCapture(), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    const status = error instanceof LocalApiError
      ? { missing: 404, invalid: 400, rejected: 409, unavailable: 503 }[error.kind]
      : 503;
    return Response.json(
      { error: { code: error instanceof LocalApiError ? error.kind : "unavailable" } },
      { status, headers: { "Cache-Control": "no-store" } },
    );
  }
}
