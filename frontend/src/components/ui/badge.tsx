import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badge = cva("inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium", {
  variants: {
    variant: {
      outline: "border border-rule-strong text-ink-soft",
      lower: "bg-band-lower text-band-lower-ink",
      middle: "bg-band-middle text-band-middle-ink",
      higher: "bg-band-higher text-band-higher-ink",
      flag: "border border-flag-rule bg-flag text-flag-ink",
      muted: "bg-rule/60 text-ink-soft",
    },
  },
  defaultVariants: { variant: "outline" },
});

export function Badge({ className, variant, ...props }: React.ComponentProps<"span"> & VariantProps<typeof badge>) {
  return <span className={cn(badge({ variant }), className)} {...props} />;
}
