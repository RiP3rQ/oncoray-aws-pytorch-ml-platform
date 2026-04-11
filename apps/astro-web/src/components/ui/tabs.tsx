import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Tabs as TabsPrimitive } from "radix-ui";

import { cn } from "@/lib/utils";

function Tabs({
  className,
  orientation = "horizontal",
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Root>) {
  return (
    <TabsPrimitive.Root
      data-slot="tabs"
      data-orientation={orientation}
      orientation={orientation}
      className={cn(
        "group/tabs flex gap-2 data-[orientation=horizontal]:flex-col",
        className,
      )}
      {...props}
    />
  );
}

const tabsListVariants = cva(
  "group/tabs-list inline-flex w-fit items-center justify-center p-0 font-mono",
  {
    variants: {
      variant: {
        default: "gap-0 border-b border-[var(--color-opencode-border-warm)]",
        line: "gap-1 bg-transparent border-b border-[var(--color-opencode-border-warm)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

function TabsList({
  className,
  variant = "default",
  ...props
}: React.ComponentProps<typeof TabsPrimitive.List> &
  VariantProps<typeof tabsListVariants>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      data-variant={variant}
      className={cn(tabsListVariants({ variant }), className)}
      {...props}
    />
  );
}

function TabsTrigger({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(
        "relative inline-flex items-center justify-center px-3 py-2 font-mono text-sm leading-none font-medium whitespace-nowrap text-[var(--color-opencode-mid-gray)] transition-colors duration-[var(--duration-fast)]",
        "hover:text-[var(--color-opencode-light)]",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-opencode-accent-blue)]",
        "data-[state=active]:font-bold data-[state=active]:text-[var(--color-opencode-light)]",
        /* OpenCode tab active indicator: 2px solid bottom border */
        "after:absolute after:right-0 after:bottom-0 after:left-0 after:h-0.5 after:scale-x-0 after:bg-[var(--color-opencode-border-tab)] after:transition-transform after:duration-[var(--duration-fast)]",
        "data-[state=active]:after:scale-x-100",
        "disabled:pointer-events-none disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

function TabsContent({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      className={cn("flex-1 outline-none", className)}
      {...props}
    />
  );
}

export { Tabs, TabsList, TabsTrigger, TabsContent, tabsListVariants };
