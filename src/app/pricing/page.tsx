"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PRICING, OPENAI_PRICING } from "@/lib/constants";

const MODEL_DISPLAY: Record<string, string> = {
  "claude-opus-4-6": "Claude Opus 4.6",
  "claude-opus-4-5-20251101": "Claude Opus 4.5",
  "claude-opus-4-1": "Claude Opus 4.1",
  "claude-opus-4": "Claude Opus 4",
  "claude-sonnet-4-6": "Claude Sonnet 4.6",
  "claude-sonnet-4-5-20250929": "Claude Sonnet 4.5",
  "claude-sonnet-4": "Claude Sonnet 4",
  "claude-haiku-4-5-20251001": "Claude Haiku 4.5",
  "claude-haiku-3-5": "Claude Haiku 3.5",
  "claude-haiku-3": "Claude Haiku 3",
};

const OPENAI_MODEL_DISPLAY: Record<string, string> = {
  "gpt-5.4": "GPT-5.4",
  "gpt-5.4-mini": "GPT-5.4 mini",
  "gpt-5.4-nano": "GPT-5.4 nano",
  "gpt-5.2": "GPT-5.2",
  "gpt-5.1": "GPT-5.1",
  "gpt-5": "GPT-5",
  "gpt-5-mini": "GPT-5 Mini",
  "o3": "o3",
  "o4-mini": "o4-mini",
};

export default function PricingPage() {
  const claudeModels = Object.entries(PRICING);
  const openaiModels = Object.entries(OPENAI_PRICING);

  return (
    <div className="space-y-8 w-full max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">Pricing Reference</h1>
        <div className="mt-2">
          <Badge variant="secondary" className="text-sm">All cost estimates assume API pricing</Badge>
        </div>
        <p className="text-muted-foreground mt-2">
          Token pricing used for cost estimates in this viewer.
        </p>
      </div>

      {/* Claude API Pricing */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Claude API Pricing</CardTitle>
          <CardDescription>
            All prices in USD per million tokens (MTok).{" "}
            Source:{" "}
            <a
              href="https://platform.claude.com/docs/en/about-claude/pricing"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-foreground"
            >
              platform.claude.com/docs/en/about-claude/pricing
            </a>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left">
                  <th className="pb-2 pr-4 font-medium">Model</th>
                  <th className="pb-2 pr-4 font-medium text-right text-blue-500">Input</th>
                  <th className="pb-2 pr-4 font-medium text-right text-green-500">Output</th>
                  <th className="pb-2 pr-4 font-medium text-right text-yellow-500">Cache Write (5m)</th>
                  <th className="pb-2 pr-4 font-medium text-right text-yellow-600">Cache Write (1h)</th>
                  <th className="pb-2 font-medium text-right text-purple-500">Cache Read</th>
                </tr>
              </thead>
              <tbody>
                {claudeModels.map(([id, p]) => (
                  <tr key={id} className="border-b border-border/50">
                    <td className="py-2 pr-4">
                      <span className="font-medium">{MODEL_DISPLAY[id] || id}</span>
                      <span className="text-xs text-muted-foreground block font-mono">{id}</span>
                    </td>
                    <td className="py-2 pr-4 text-right font-mono">${p.input}</td>
                    <td className="py-2 pr-4 text-right font-mono">${p.output}</td>
                    <td className="py-2 pr-4 text-right font-mono">${p.cacheWrite5m}</td>
                    <td className="py-2 pr-4 text-right font-mono">${p.cacheWrite1h}</td>
                    <td className="py-2 text-right font-mono">${p.cacheRead}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* OpenAI API Pricing */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">OpenAI / Codex API Pricing</CardTitle>
          <CardDescription>
            All prices in USD per million tokens (MTok).{" "}
            Sources:{" "}
            <a
              href="https://openai.com/api/pricing/"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-foreground"
            >
              openai.com/api/pricing
            </a>
            {", "}
            <a
              href="https://developers.openai.com/codex/pricing/"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-foreground"
            >
              developers.openai.com/codex/pricing
            </a>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left">
                  <th className="pb-2 pr-4 font-medium">Model</th>
                  <th className="pb-2 pr-4 font-medium text-right text-blue-500">Input</th>
                  <th className="pb-2 pr-4 font-medium text-right text-green-500">Output</th>
                  <th className="pb-2 font-medium text-right text-purple-500">Cached Input</th>
                </tr>
              </thead>
              <tbody>
                {openaiModels.map(([id, p]) => (
                  <tr key={id} className="border-b border-border/50">
                    <td className="py-2 pr-4">
                      <span className="font-medium">{OPENAI_MODEL_DISPLAY[id] || id}</span>
                      <span className="text-xs text-muted-foreground block font-mono">{id}</span>
                    </td>
                    <td className="py-2 pr-4 text-right font-mono">${p.input}</td>
                    <td className="py-2 pr-4 text-right font-mono">${p.output}</td>
                    <td className="py-2 text-right font-mono">${p.cacheRead}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Prompt caching explanation */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Prompt Caching</CardTitle>
          <CardDescription>Cache multipliers relative to base input price</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-yellow-500/10 rounded-lg p-3">
              <div className="font-medium text-yellow-600 dark:text-yellow-400">5-minute Cache Write</div>
              <div className="text-2xl font-bold mt-1">1.25x</div>
              <div className="text-muted-foreground text-xs mt-1">Default duration. Tokens written to cache cost 1.25x the base input price.</div>
            </div>
            <div className="bg-yellow-600/10 rounded-lg p-3">
              <div className="font-medium text-yellow-700 dark:text-yellow-300">1-hour Cache Write</div>
              <div className="text-2xl font-bold mt-1">2.0x</div>
              <div className="text-muted-foreground text-xs mt-1">Extended duration. Tokens written to cache cost 2x the base input price.</div>
            </div>
            <div className="bg-purple-500/10 rounded-lg p-3">
              <div className="font-medium text-purple-600 dark:text-purple-400">Cache Read (Hit)</div>
              <div className="text-2xl font-bold mt-1">0.1x</div>
              <div className="text-muted-foreground text-xs mt-1">Reading from cache costs just 10% of the base input price.</div>
            </div>
          </div>
          <p className="text-muted-foreground">
            Claude Code uses 5-minute prompt caching by default, so Claude estimates include a separate cache-write line item. OpenAI/Codex bills cache fills as normal input and only discounts cached input on reuse.
          </p>
        </CardContent>
      </Card>

      {/* Claude 1M context */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Claude 1M Context</CardTitle>
          <CardDescription>
            Opus 4.6 and Sonnet 4.6 now use standard pricing across the full 1M context window
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left">
                <th className="pb-2 pr-4 font-medium">Model</th>
                <th className="pb-2 pr-4 font-medium text-right">Input</th>
                <th className="pb-2 pr-4 font-medium text-right">Output</th>
                <th className="pb-2 font-medium text-right">Long-Context Policy</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-border/50">
                <td className="py-2 pr-4 font-medium">Opus 4.6</td>
                <td className="py-2 pr-4 text-right font-mono">$5/MTok</td>
                <td className="py-2 pr-4 text-right font-mono">$25/MTok</td>
                <td className="py-2 text-right text-muted-foreground">Standard pricing through 1M tokens</td>
              </tr>
              <tr className="border-b border-border/50">
                <td className="py-2 pr-4 font-medium">Sonnet 4.6</td>
                <td className="py-2 pr-4 text-right font-mono">$3/MTok</td>
                <td className="py-2 pr-4 text-right font-mono">$15/MTok</td>
                <td className="py-2 text-right text-muted-foreground">Standard pricing through 1M tokens</td>
              </tr>
            </tbody>
          </table>
          </div>
          <p className="text-xs text-muted-foreground">
            Anthropic announced on March 13, 2026 that Opus 4.6 and Sonnet 4.6 use one price across the full 1M window with no long-context premium. This viewer still preserves legacy Sonnet 4 / 4.5 premium handling for historical runs whose model IDs predate the 4.6 rollout.
          </p>
        </CardContent>
      </Card>

      {/* Tool overhead */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Tool-Specific Overhead</CardTitle>
          <CardDescription>Additional input tokens added per tool invocation</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left">
                <th className="pb-2 pr-4 font-medium">Tool</th>
                <th className="pb-2 pr-4 font-medium text-right">Overhead Tokens</th>
                <th className="pb-2 font-medium">Notes</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-border/50">
                <td className="py-2 pr-4">Tool use system prompt</td>
                <td className="py-2 pr-4 text-right font-mono">346</td>
                <td className="py-2 text-muted-foreground">Added once per request when any tools are defined (auto/none mode)</td>
              </tr>
              <tr className="border-b border-border/50">
                <td className="py-2 pr-4">Bash tool</td>
                <td className="py-2 pr-4 text-right font-mono">245</td>
                <td className="py-2 text-muted-foreground">Per invocation, plus stdout/stderr output tokens</td>
              </tr>
              <tr className="border-b border-border/50">
                <td className="py-2 pr-4">Text editor tool</td>
                <td className="py-2 pr-4 text-right font-mono">700</td>
                <td className="py-2 text-muted-foreground">Per invocation (text_editor_20250429)</td>
              </tr>
              <tr className="border-b border-border/50">
                <td className="py-2 pr-4">Web search</td>
                <td className="py-2 pr-4 text-right font-mono">-</td>
                <td className="py-2 text-muted-foreground">$10 per 1,000 searches + standard token costs</td>
              </tr>
              <tr className="border-b border-border/50">
                <td className="py-2 pr-4">Web fetch</td>
                <td className="py-2 pr-4 text-right font-mono">-</td>
                <td className="py-2 text-muted-foreground">No additional cost, only standard token costs for fetched content</td>
              </tr>
              <tr className="border-b border-border/50">
                <td className="py-2 pr-4">Computer use</td>
                <td className="py-2 pr-4 text-right font-mono">735</td>
                <td className="py-2 text-muted-foreground">Plus 466-499 system prompt tokens + screenshot image tokens</td>
              </tr>
            </tbody>
          </table>
          </div>
          <p className="text-xs text-muted-foreground mt-3">
            Tool overhead tokens are included in the <code>input_tokens</code> count in API responses.
            They are already reflected in the token counts shown throughout this viewer.
          </p>
        </CardContent>
      </Card>

      {/* Other pricing modifiers */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Other Pricing Modifiers</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <div className="flex items-start gap-3">
            <Badge variant="outline" className="shrink-0 mt-0.5">Fast Mode</Badge>
            <p className="text-muted-foreground">
              6x standard rates for Opus 4.6 research preview. Input: $30/MTok, Output: $150/MTok. Includes full 1M context at no additional long-context charge.
            </p>
          </div>
          <div className="flex items-start gap-3">
            <Badge variant="outline" className="shrink-0 mt-0.5">Batch API</Badge>
            <p className="text-muted-foreground">
              50% discount on both input and output tokens for asynchronous batch processing. Stacks with prompt caching and standard or legacy long-context pricing as applicable.
            </p>
          </div>
          <div className="flex items-start gap-3">
            <Badge variant="outline" className="shrink-0 mt-0.5">Data Residency</Badge>
            <p className="text-muted-foreground">
              1.1x multiplier on all token categories when specifying US-only inference via <code>inference_geo</code> parameter (Opus 4.6+ only). Global routing uses standard pricing.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* How this viewer calculates costs */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">How This Viewer Calculates Costs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>
            Cost estimates in this viewer are calculated using:
          </p>
          <ul className="list-disc pl-5 space-y-1">
            <li>Per-model pricing matched from the conversation&apos;s model identifier</li>
            <li><strong>5-minute</strong> prompt cache write rates (the default for Claude Code)</li>
            <li>Standard cache read rates (0.1x base input)</li>
            <li>Global routing pricing (no data residency or fast mode premium)</li>
            <li>Standard 1M context pricing for Claude 4.6 and standard context pricing for OpenAI/Codex models</li>
            <li>Legacy Sonnet 4 / 4.5 long-context premium only when the model ID indicates it</li>
          </ul>
          <p>
            Actual costs may differ due to: fast mode usage, data residency settings, web search charges,
            batch API discounts, or historical Sonnet 4 / 4.5 conversations that crossed the legacy
            long-context threshold.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
