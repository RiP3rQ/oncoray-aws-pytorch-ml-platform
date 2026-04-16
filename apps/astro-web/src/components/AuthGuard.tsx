import { useAuthContext } from "@/lib/auth";
import { useEffect, type ReactNode } from "react";

export default function AuthGuard({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuthContext();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      window.location.href = "/login";
    }
  }, [isAuthenticated, isLoading]);

  if (isLoading) {
    return (
      <div className="page-shell">
        <div className="frame auth-layout auth-layout--single">
          <div className="flat-card loading-card">
            <div className="skeleton loading-line loading-line--title" />
            <div className="skeleton loading-line loading-line--subtitle" />
          </div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return <div className="animate-fade-in">{children}</div>;
}
