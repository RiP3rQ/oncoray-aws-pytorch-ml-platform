import { useAuthContext } from "@/lib/auth";
import type { ReactNode } from "react";

export default function AuthGuard({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuthContext();

  if (isLoading) {
    return (
      <div className="page-shell">
        <div className="frame auth-layout single-column">
          <div className="glass-card loading-card">
            <div className="skeleton loading-line loading-line--title" />
            <div className="skeleton loading-line loading-line--subtitle" />
          </div>
        </div>
        <style>{`
          .single-column {
            grid-template-columns: 1fr;
            place-items: center;
          }
          .loading-card {
            padding: 32px 40px;
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 12px;
          }
          .loading-line {
            height: 12px;
            border-radius: 6px;
          }
          .loading-line--title {
            width: 120px;
            height: 16px;
          }
          .loading-line--subtitle {
            width: 80px;
          }
        `}</style>
      </div>
    );
  }

  if (!isAuthenticated) {
    window.location.href = "/login";
    return null;
  }

  return <div className="animate-fade-in">{children}</div>;
}
