import Link from "next/link";
import { notFound } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { getAppDocsNavigation, loadAppDoc } from "@/lib/docs";

export default async function DocsPage({
  params,
}: {
  params: Promise<{ slug?: string[] }>;
}) {
  const { slug } = await params;
  const page = loadAppDoc(slug ?? []);
  if (!page) {
    notFound();
  }

  const navigation = getAppDocsNavigation().filter((entry) => entry.href !== "/docs");

  return (
    <div className="space-y-8">
      <PageHeader
        title={page.title}
        description={page.description ?? "App-native documentation sourced from the repo docs directory."}
      />
      <Container size="xl">
        <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
          <Card className="h-fit">
            <CardContent className="p-4">
              <div className="mb-3 text-sm font-semibold">Documentation</div>
              <div className="space-y-1">
                <Link
                  href="/docs"
                  className="block rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
                >
                  Overview
                </Link>
                {navigation.map((entry) => (
                  <Link
                    key={entry.href}
                    href={entry.href}
                    className="block rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
                  >
                    <div className="font-medium text-foreground">{entry.title}</div>
                    {entry.description ? (
                      <div className="mt-1 text-xs text-muted-foreground">{entry.description}</div>
                    ) : null}
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <article className="prose prose-slate max-w-none dark:prose-invert">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{page.body}</ReactMarkdown>
              </article>
            </CardContent>
          </Card>
        </div>
      </Container>
    </div>
  );
}
