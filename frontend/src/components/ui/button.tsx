import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const button = cva(
  "inline-flex cursor-pointer items-center justify-center gap-2 rounded-md text-sm font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-60",
  {
    variants: {
      variant: {
        primary: "bg-accent px-4 py-2 text-white hover:bg-accent-strong",
        quiet: "border border-rule-strong bg-surface px-3 py-1.5 text-ink hover:border-ink-faint",
      },
    },
    defaultVariants: { variant: "primary" },
  },
);

export function Button({ className, variant, ...props }: React.ComponentProps<"button"> & VariantProps<typeof button>) {
  return <button className={cn(button({ variant }), className)} {...props} />;
}
