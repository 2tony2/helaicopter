import * as React from "react";
import { cn } from "@/lib/utils";

export type ContainerProps = React.HTMLAttributes<HTMLDivElement> & {
  size?: "md" | "lg" | "xl" | "2xl" | "full";
  padded?: boolean;
};

const sizeClass: Record<NonNullable<ContainerProps["size"]>, string> = {
  md: "max-w-3xl",
  lg: "max-w-5xl",
  xl: "max-w-7xl",
  "2xl": "max-w-screen-2xl",
  full: "max-w-none",
};

export function Container({
  className,
  size = "xl",
  padded = false,
  ...props
}: ContainerProps) {
  return (
    <div
      className={cn(
        "mx-auto w-full",
        sizeClass[size],
        padded ? "px-4 sm:px-6 lg:px-8" : undefined,
        className
      )}
      {...props}
    />
  );
}
