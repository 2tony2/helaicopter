import Link from "next/link";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";

const configuredApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim().replace(/\/+$/, "");

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
    href: configuredApiBaseUrl ? `${configuredApiBaseUrl}/openapi.json` : "/openapi/helaicopter-api.json",
    label: "Live backend schema",
    description: configuredApiBaseUrl
      ? "Runtime schema served by the configured backend origin."
      : "Set NEXT_PUBLIC_API_BASE_URL to expose the runtime schema from the active backend.",
  },
];

export default function SchemaPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="OpenAPI Artifacts"
        description={
          <span className="max-w-2xl block">
            Helaicopter publishes generated OpenAPI snapshots from the FastAPI backend into a
            stable repo-local directory so the contract is easy to inspect, diff, and download.
          </span>
        }
      />
      <Container size="lg">
        <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
          {artifactLinks.map((item) => {
            const isExternal = item.href.startsWith("http");
            return (
              <Link key={item.href} href={item.href} target={isExternal ? "_blank" : undefined}>
                <Card className="hover:bg-accent/30 transition-colors">
                  <CardContent className="p-5 space-y-2">
                    <h2 className="text-base font-semibold">{item.label}</h2>
                    <p className="text-sm text-muted-foreground">{item.description}</p>
                    <p className="text-xs text-muted-foreground">{item.href}</p>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>

        <Card className="mt-8">
          <CardContent className="p-6">
            <h2 className="text-lg font-semibold">Regenerate</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Run <code>npm run api:openapi</code> to overwrite the committed JSON and YAML
              artifacts under <code>public/openapi/</code>.
            </p>
          </CardContent>
        </Card>
      </Container>
    </div>
  );
}
