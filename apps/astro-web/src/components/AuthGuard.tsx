import { useAuthContext } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { useEffect, type ReactNode } from "react";

export default function AuthGuard({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuthContext();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      window.location.replace("/login");
    }
  }, [isAuthenticated, isLoading]);

  if (isLoading) {
    return (
      <div className="mx-auto flex min-h-dvh w-full max-w-[56rem] px-4 py-4 sm:px-6 lg:px-8">
        <div className="grid min-h-[calc(100dvh-2rem)] w-full place-items-center sm:min-h-[calc(100dvh-3rem)]">
          <div className="border-border bg-card flex w-full max-w-xs flex-col items-center gap-3 rounded-[4px] border px-8 py-8">
            <div
              aria-hidden="true"
              className="bg-muted h-4 w-32 animate-pulse rounded-[4px]"
            />
            <div
              aria-hidden="true"
              className="bg-muted h-3 w-20 animate-pulse rounded-[4px]"
            />
          </div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div
      className={cn(
        "motion-safe:animate-in motion-safe:fade-in motion-safe:duration-150",
      )}
    >
      {children}
    </div>
  );
}
