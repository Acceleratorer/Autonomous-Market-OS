export const dynamic = "force-dynamic";

export function GET(): Response {
  return Response.json(
    {
      api_version: "market-os.next-health@v1",
      service: "market-os-next-operator",
      status: "ok",
    },
    {
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}
