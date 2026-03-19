import Link from "next/link";

const artifactLinks = [
  {
    href: "/openapi/helaicopter-api.json",
    label: "OpenAPI JSON",
    description: "Generated machine-readable contract committed under public/openapi/.",
  },
  {
    href: "/openapi/helaicopter-api.yaml",
    label: "OpenAPI YAML",
    description: "Generated YAML variant for inspection, copy/paste, and downstream tooling.",
  },
  {
    href: "http://127.0.0.1:30000/openapi.json",
    label: "Live backend schema",
    description: "Runtime schema served directly by the FastAPI process during local development.",
  },
];

export default function SchemaPage() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-background via-background to-muted/30 px-6 py-10">
      <div className="mx-auto max-w-4xl space-y-8">
        <div className="space-y-3">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            API
          </p>
          <h1 className="text-4xl font-semibold tracking-tight">OpenAPI Artifacts</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Helaicopter publishes generated OpenAPI snapshots from the FastAPI backend into a
            stable repo-local directory so the contract is easy to inspect, diff, and download.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {artifactLinks.map((item) => {
            const isExternal = item.href.startsWith("http");
            return (
              <Link
                key={item.href}
                href={item.href}
                target={isExternal ? "_blank" : undefined}
                className="rounded-2xl border bg-card p-5 shadow-sm transition-colors hover:border-foreground/30 hover:bg-accent/30"
              >
                <div className="space-y-2">
                  <h2 className="text-base font-semibold">{item.label}</h2>
                  <p className="text-sm text-muted-foreground">{item.description}</p>
                  <p className="text-xs text-muted-foreground">{item.href}</p>
                </div>
              </Link>
            );
          })}
        </div>

        <section className="rounded-2xl border bg-card p-6 shadow-sm">
          <h2 className="text-lg font-semibold">Regenerate</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Run <code>npm run api:openapi</code> to overwrite the committed JSON and YAML
            artifacts under <code>public/openapi/</code>.
          </p>
        </section>
      </div>
    </main>
  );
}
