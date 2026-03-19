"use client";

import { ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { PREFECT_UI_URL } from "./tabs";

export function PrefectUiEmbed() {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <div>
          <CardTitle>Prefect UI</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            Embedded local Prefect server UI for direct inspection and debugging.
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <a href={PREFECT_UI_URL} target="_blank" rel="noreferrer">
            Open standalone
            <ExternalLink className="ml-2 h-4 w-4" />
          </a>
        </Button>
      </CardHeader>
      <CardContent className="p-0">
        <iframe
          title="Prefect UI"
          src={PREFECT_UI_URL}
          className="h-[calc(100vh-18rem)] min-h-[640px] w-full border-0 bg-background"
        />
      </CardContent>
    </Card>
  );
}
