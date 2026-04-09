import { useAuthContext } from "@/lib/auth";
import type { ReactNode } from "react";

export default function AuthGuard({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuthContext();

  if (isLoading) {
    return (
      <div className="page-shell">
        <div
          className="frame"
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            minHeight: "100vh",
          }}
        >
          <div
            className="glass-card"
            style={{ padding: "32px 40px", textAlign: "center" }}
          >
            <p
              style={{
                color: "var(--muted)",
                letterSpacing: "0.15em",
                textTransform: "uppercase",
                fontSize: "0.76rem",
              }}
            >
              Checking credentials…
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    window.location.href = "/login";
    return null;
  }

  return <>{children}</>;
}
